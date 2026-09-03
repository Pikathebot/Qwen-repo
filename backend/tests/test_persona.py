import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.persona.manager import PersonaManager
from app.persona.profiles import BUILTIN_PERSONAS, JARVIS, OPERATOR
from app.persona.speech import condense_for_speech, sanitize_markdown_for_speech


@pytest.fixture
def manager(tmp_path):
    return PersonaManager(state_path=tmp_path / "persona.json")


@pytest.fixture
def client(monkeypatch, tmp_path):
    """A client whose persona state is isolated from the real data directory."""
    import app.routers.persona as persona_router

    isolated = PersonaManager(state_path=tmp_path / "api_persona.json")
    monkeypatch.setattr(persona_router, "persona_manager", isolated)
    return TestClient(app)


# ------------------------------------------------------------------ speech


def test_sanitize_strips_markdown_code_and_decoration():
    raw = "# Report\n- **Done**: see `main.py`\n```python\nprint(1)\n```\n[docs](http://x.dev) ✓"
    clean = sanitize_markdown_for_speech(raw)

    assert "#" not in clean
    assert "**" not in clean
    assert "`" not in clean
    assert "print(1)" not in clean
    assert "[code block omitted]" in clean
    assert "docs" in clean and "http" not in clean
    assert "✓" not in clean


def test_condense_caps_sentences_and_defers_to_screen():
    text = "One. Two. Three. Four. Five."

    assert condense_for_speech(text, max_sentences=0) == text
    capped = condense_for_speech(text, max_sentences=2)
    assert capped.startswith("One. Two.")
    assert "Three" not in capped
    assert "on screen" in capped


def test_condense_leaves_short_text_untouched():
    assert condense_for_speech("All clear.", max_sentences=4) == "All clear."


def test_persona_speech_cap_differs_by_profile():
    long_reply = "One. Two. Three. Four. Five. Six."

    assert "Five" not in OPERATOR.shape_for_speech(long_reply)
    assert "Four" in JARVIS.shape_for_speech(long_reply)


# ----------------------------------------------------------------- prompts


def test_prompt_preamble_carries_address_and_tone():
    preamble = JARVIS.build_prompt_preamble()

    assert preamble.startswith("PERSONA:")
    assert "'sir'" in preamble
    for directive in JARVIS.tone_directives:
        assert directive in preamble


def test_neutral_persona_omits_address_instruction():
    preamble = BUILTIN_PERSONAS["assistant"].build_prompt_preamble()
    assert "Address the user as" not in preamble


def test_system_prompt_is_persona_plus_invariant_tool_rules(manager):
    from app.agent.orchestrator import TOOL_PROTOCOL_RULES, build_system_prompt

    for persona in BUILTIN_PERSONAS.values():
        prompt = build_system_prompt(persona)
        assert prompt.startswith("PERSONA:")
        # The tool protocol is invariant across personas.
        assert TOOL_PROTOCOL_RULES in prompt


# ---------------------------------------------------------------- manager


def test_manager_defaults_to_jarvis(manager):
    assert manager.active_id == "jarvis"
    assert manager.get_active().address_term == "sir"


def test_set_active_persists_across_instances(manager, tmp_path):
    manager.set_active("operator")

    reloaded = PersonaManager(state_path=manager.state_path)
    assert reloaded.active_id == "operator"
    assert reloaded.get_active().max_speech_sentences == 2


def test_set_active_rejects_unknown_persona(manager):
    with pytest.raises(ValueError):
        manager.set_active("ultron")
    assert manager.active_id == "jarvis"


def test_overrides_apply_without_mutating_builtin(manager):
    manager.set_overrides({"address_term": "boss", "max_speech_sentences": 1})
    active = manager.get_active()

    assert active.address_term == "boss"
    assert active.max_speech_sentences == 1
    # The shared builtin profile must be untouched.
    assert BUILTIN_PERSONAS["jarvis"].address_term == "sir"

    manager.clear_overrides()
    assert manager.get_active().address_term == "sir"


def test_overrides_ignore_unknown_and_malformed_fields(manager):
    manager.set_overrides({"name": "Ultron", "id": "evil", "max_speech_sentences": "many"})
    active = manager.get_active()

    assert active.name == "Jarvis"
    assert active.id == "jarvis"
    assert active.max_speech_sentences == JARVIS.max_speech_sentences


def test_corrupt_state_file_falls_back_to_default(tmp_path):
    state = tmp_path / "persona.json"
    state.write_text("{not json", encoding="utf-8")

    assert PersonaManager(state_path=state).active_id == "jarvis"


def test_state_file_is_written_as_json(manager):
    manager.set_active("assistant")
    data = json.loads(manager.state_path.read_text(encoding="utf-8"))

    assert data["active_id"] == "assistant"


# --------------------------------------------------------------------- API


def test_get_persona_returns_active_and_available(client):
    res = client.get("/api/persona")
    assert res.status_code == 200

    body = res.json()
    assert body["active_id"] == "jarvis"
    assert {p["id"] for p in body["available"]} == set(BUILTIN_PERSONAS)
    assert "jarvis-british" in body["available_voices"]


def test_switch_persona_via_api(client):
    res = client.post("/api/persona", json={"persona_id": "operator"})
    assert res.status_code == 200
    assert res.json()["active_id"] == "operator"

    assert client.get("/api/persona").json()["active"]["max_speech_sentences"] == 2


def test_switch_to_unknown_persona_returns_400(client):
    res = client.post("/api/persona", json={"persona_id": "ultron"})
    assert res.status_code == 400
    assert "ultron" in res.json()["detail"]


def test_override_and_clear_via_api(client):
    res = client.patch("/api/persona/overrides", json={"address_term": "boss"})
    assert res.status_code == 200
    assert res.json()["active"]["address_term"] == "boss"

    res = client.delete("/api/persona/overrides")
    assert res.status_code == 200
    assert res.json()["active"]["address_term"] == "sir"


def test_speech_preview_shapes_markdown(client):
    res = client.post(
        "/api/persona/speech-preview",
        json={"text": "**Done.** ```py\nx=1\n``` One. Two. Three. Four. Five."},
    )
    assert res.status_code == 200

    body = res.json()
    assert "**" not in body["spoken_text"]
    assert "x=1" not in body["spoken_text"]
    assert body["spoken_chars"] == len(body["spoken_text"])
