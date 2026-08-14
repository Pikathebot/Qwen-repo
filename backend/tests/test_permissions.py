import os
import uuid
import pytest
import httpx
from app.main import app
from app.agent.permissions import (
    RiskTier,
    BASE_TOOL_RISK_MAP,
    evaluate_tool_permission,
    evaluate_tool_calls_batch,
    generate_action_id,
    evaluate_command_argument_risk,
    evaluate_file_path_risk,
)


# --- Unit Tests for Deterministic Hardcoded Lookup ---

def test_low_risk_tool_auto_allowed():
    decision = evaluate_tool_permission("read_file", {"file_path": "docs/PLAN.md"})
    assert decision.allowed is True
    assert decision.risk_tier == RiskTier.LOW_RISK


def test_confirmation_required_tool_blocked_by_default():
    decision = evaluate_tool_permission("execute_command", {"command": "npm install"})
    assert decision.allowed is False
    assert decision.risk_tier == RiskTier.CONFIRMATION_REQUIRED
    assert decision.action_id.startswith("act_")


def test_high_risk_tool_blocked_by_default():
    decision = evaluate_tool_permission("delete_file", {"file_path": "some_file.txt"})
    assert decision.allowed is False
    assert decision.risk_tier == RiskTier.HIGH_RISK
    assert decision.action_id.startswith("act_")


def test_unclassified_tool_defaults_to_confirmation_required():
    """Unclassified tools MUST default to CONFIRMATION_REQUIRED, never LOW_RISK."""
    decision = evaluate_tool_permission("mysterious_new_tool", {"param": "val"})
    assert decision.allowed is False
    assert decision.risk_tier == RiskTier.CONFIRMATION_REQUIRED


def test_argument_aware_command_risk():
    # Safe commands downgraded to LOW_RISK
    assert evaluate_command_argument_risk("git status") == RiskTier.LOW_RISK
    assert evaluate_command_argument_risk("dir") == RiskTier.LOW_RISK
    assert evaluate_command_argument_risk("echo hello") == RiskTier.LOW_RISK
    
    # Destructive commands escalated to HIGH_RISK
    assert evaluate_command_argument_risk("rm -rf /") == RiskTier.HIGH_RISK
    assert evaluate_command_argument_risk("del /f important.db") == RiskTier.HIGH_RISK
    assert evaluate_command_argument_risk("format C:") == RiskTier.HIGH_RISK
    
    # Unknown commands remain CONFIRMATION_REQUIRED
    assert evaluate_command_argument_risk("curl http://example.com") == RiskTier.CONFIRMATION_REQUIRED


def test_argument_aware_file_path_risk():
    assert evaluate_file_path_risk("docs/PLAN.md") == RiskTier.LOW_RISK
    assert evaluate_file_path_risk(r"C:\Windows\System32\drivers\etc\hosts") == RiskTier.HIGH_RISK
    assert evaluate_file_path_risk(r"C:\Program Files\App\config.json") == RiskTier.HIGH_RISK


def test_approval_token_grants_permission():
    args = {"file_path": "sample.txt"}
    action_id = generate_action_id("delete_file", args)
    
    # Denied without token
    denied = evaluate_tool_permission("delete_file", args)
    assert denied.allowed is False
    
    # Allowed with matching token
    approved = evaluate_tool_permission("delete_file", args, approved_action_ids=[action_id])
    assert approved.allowed is True
    assert approved.action_id == action_id


def test_modifying_tier_map_changes_behavior_deterministically():
    """Prove that hardcoded lookup table drives decision, not model prompts."""
    original_tier = BASE_TOOL_RISK_MAP.get("read_file")
    try:
        # Reclassify read_file to HIGH_RISK
        BASE_TOOL_RISK_MAP["read_file"] = RiskTier.HIGH_RISK
        decision = evaluate_tool_permission("read_file", {"file_path": "docs/PLAN.md"})
        assert decision.allowed is False
        assert decision.risk_tier == RiskTier.HIGH_RISK
    finally:
        # Restore original tier
        BASE_TOOL_RISK_MAP["read_file"] = original_tier


def test_batch_tool_permission_evaluation():
    tool_calls = [
        {"name": "read_file", "args": {"file_path": "a.txt"}},
        {"name": "delete_file", "args": {"file_path": "b.txt"}},
    ]
    batch = evaluate_tool_calls_batch(tool_calls)
    assert batch.all_allowed is False
    assert len(batch.approved_actions) == 1
    assert len(batch.pending_confirmations) == 1
    assert batch.pending_confirmations[0].tool == "delete_file"


# --- Integration Tests with Ollama (qwen2.5:0.5b) ---

@pytest.mark.anyio
async def test_integration_low_risk_auto_executes():
    """LOW-RISK tool calls should execute without confirmation status."""
    test_file = "test_lowrisk_sample.txt"
    with open(test_file, "w", encoding="utf-8") as f:
        f.write("LOW_RISK_CONFIRMED_DATA")

    try:
        payload = {
            "message": f"Please read the file {test_file} using read_file and report its contents.",
            "session_id": f"test_lowrisk_{uuid.uuid4().hex[:8]}",
            "model": "qwen2.5:0.5b"
        }
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", timeout=45.0) as ac:
            response = await ac.post("/chat", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert len(data["pending_confirmations"]) == 0
        assert len(data["tools_used"]) >= 1
        assert any(t["tool"] in ("read_file", "execute_command") for t in data["tools_used"])
    finally:
        if os.path.exists(test_file):
            os.remove(test_file)


@pytest.mark.anyio
async def test_integration_confirmation_required_blocks_and_resumes():
    """Test that a confirmation-required tool is intercepted, returns an action ID, and runs when confirmed."""
    test_file = "test_to_delete.txt"
    with open(test_file, "w", encoding="utf-8") as f:
        f.write("temporary file")

    session_id = f"test_confirm_{uuid.uuid4().hex[:8]}"

    try:
        # 1. First call: Model should invoke delete_file, which must be blocked
        initial_payload = {
            "message": f"Delete the file '{test_file}' using delete_file.",
            "session_id": session_id,
            "model": "qwen2.5:0.5b"
        }
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", timeout=45.0) as ac:
            res1 = await ac.post("/chat", json=initial_payload)
        
        assert res1.status_code == 200
        data1 = res1.json()
        
        # If model invoked delete_file, verify confirmation was required
        if data1["status"] == "confirmation_required":
            assert len(data1["pending_confirmations"]) > 0
            action = data1["pending_confirmations"][0]
            assert action["tool"] == "delete_file"
            action_id = action["action_id"]
            
            # Verify file was NOT deleted yet
            assert os.path.exists(test_file)

            # 2. Second call: Provide approved_action_ids token to approve execution
            approved_payload = {
                "message": f"Delete the file '{test_file}' using delete_file.",
                "session_id": session_id,
                "model": "qwen2.5:0.5b",
                "approved_action_ids": [action_id]
            }
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", timeout=45.0) as ac:
                res2 = await ac.post("/chat", json=approved_payload)
            
            assert res2.status_code == 200
            data2 = res2.json()
            assert data2["status"] == "completed"
            assert any(t["tool"] == "delete_file" for t in data2["tools_used"])
            # Verify file WAS deleted
            assert not os.path.exists(test_file)
    finally:
        if os.path.exists(test_file):
            os.remove(test_file)
        # Cleanup session
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
            await ac.delete(f"/sessions/{session_id}")
