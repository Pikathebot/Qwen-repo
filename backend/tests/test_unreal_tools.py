import json
import pytest
from pathlib import Path

from app.tools.base import PermissionLevel
from app.tools.unreal_tools import (
    UnrealDetectProjectTool,
    UnrealReadLogsTool,
    UnrealBuildTool,
)
from app.sandbox.base import ExecutionBackend, ExecutionResult
from app.sandbox.manager import SandboxManager


@pytest.fixture
def mock_ue_project(tmp_path):
    """Creates a mock Unreal Engine project directory structure inside tmp_path."""
    proj_dir = tmp_path / "MyProject"
    proj_dir.mkdir(parents=True, exist_ok=True)

    # Mock .uproject file
    uproject_content = {
        "FileVersion": 3,
        "EngineAssociation": "5.4",
        "Category": "Games",
        "Description": "Test Nexus Game",
        "Modules": [
            {
                "Name": "MyProject",
                "Type": "Runtime",
                "LoadingPhase": "Default"
            }
        ],
        "Plugins": [
            {
                "Name": "ModelingToolsEditorMode",
                "Enabled": True,
                "TargetAllowList": ["Editor"]
            }
        ]
    }
    uproject_file = proj_dir / "MyProject.uproject"
    uproject_file.write_text(json.dumps(uproject_content, indent=2), encoding="utf-8")

    # Mock Source and Config
    (proj_dir / "Source" / "MyProject").mkdir(parents=True, exist_ok=True)
    (proj_dir / "Config").mkdir(parents=True, exist_ok=True)

    # Mock Saved/Logs
    logs_dir = proj_dir / "Saved" / "Logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / "MyProject.log"
    log_file.write_text(
        "[2026.09.02-12.00.00:000][  0]LogInit: Engine Version: 5.4.0\n"
        "[2026.09.02-12.00.01:000][  0]LogInit: Project: MyProject\n"
        "[2026.09.02-12.00.02:000][  0]LogInit: Initializing Subsystems...\n"
        "[2026.09.02-12.00.03:000][  0]LogWorld: Bringing World /Game/Maps/MainMap.MainMap up for play\n",
        encoding="utf-8"
    )

    return {
        "proj_dir": proj_dir,
        "uproject_file": uproject_file,
        "log_file": log_file,
        "tmp_path": tmp_path,
    }


def test_unreal_tools_permission_levels():
    """Verify read-only inspection tools are LOW_RISK and build tool is CONFIRMATION_REQUIRED (§14)."""
    assert UnrealDetectProjectTool().permission_level == PermissionLevel.LOW_RISK
    assert UnrealReadLogsTool().permission_level == PermissionLevel.LOW_RISK
    assert UnrealBuildTool().permission_level == PermissionLevel.CONFIRMATION_REQUIRED


@pytest.mark.anyio
async def test_unreal_detect_project_valid_uproject(mock_ue_project):
    tool = UnrealDetectProjectTool()
    proj_dir = mock_ue_project["proj_dir"]

    res = await tool.execute(search_path=str(proj_dir), allowed_folders=[proj_dir])
    assert res.status == "success"
    data = res.result

    assert data["project_name"] == "MyProject"
    assert data["engine_version"] == "5.4"
    assert data["modules_count"] == 1
    assert data["modules"][0]["Name"] == "MyProject"
    assert data["plugins_count"] == 1
    assert data["has_source"] is True


@pytest.mark.anyio
async def test_unreal_detect_project_missing_uproject(tmp_path):
    empty_dir = tmp_path / "empty_folder"
    empty_dir.mkdir()

    tool = UnrealDetectProjectTool()
    res = await tool.execute(search_path=str(empty_dir), allowed_folders=[empty_dir])
    assert res.status == "error"
    assert "No Unreal Engine" in res.error


@pytest.mark.anyio
async def test_unreal_read_logs_latest_tail(mock_ue_project):
    tool = UnrealReadLogsTool()
    proj_dir = mock_ue_project["proj_dir"]

    res = await tool.execute(project_path=str(proj_dir), lines_count=2, allowed_folders=[proj_dir])
    assert res.status == "success"
    assert "Bringing World" in res.result
    assert res.metadata["retrieved_lines"] == 2


@pytest.mark.anyio
async def test_unreal_read_logs_no_logs_directory(tmp_path):
    no_log_proj = tmp_path / "RawProject"
    no_log_proj.mkdir()
    (no_log_proj / "Raw.uproject").write_text("{}", encoding="utf-8")

    tool = UnrealReadLogsTool()
    res = await tool.execute(project_path=str(no_log_proj), allowed_folders=[no_log_proj])
    assert res.status == "error"
    assert "logs directory not found" in res.error.lower()


@pytest.mark.anyio
async def test_unreal_build_tool_dispatch(mock_ue_project):
    class MockBuildBackend(ExecutionBackend):
        async def execute(self, command, cwd=".", env=None, timeout=None):
            return ExecutionResult(stdout="UBT Build Successful. 0 errors, 0 warnings.", exit_code=0, latency_ms=1200)
        async def cancel(self):
            pass

    mock_mgr = SandboxManager(backend=MockBuildBackend())
    tool = UnrealBuildTool(sandbox_manager=mock_mgr)
    proj_dir = mock_ue_project["proj_dir"]

    res = await tool.execute(
        project_path=str(mock_ue_project["uproject_file"]),
        target="Editor",
        config="Development",
        platform="Win64",
        allowed_folders=[proj_dir]
    )

    assert res.status == "success"
    assert res.result["exit_code"] == 0
    assert "Build Successful" in res.result["stdout"]
    assert "MyProject" in res.result["command"]


@pytest.mark.anyio
async def test_unreal_tools_sandbox_boundary_enforcement(tmp_path):
    sandbox_dir = tmp_path / "sandbox"
    sandbox_dir.mkdir()
    outside_dir = tmp_path / "forbidden_outside"
    outside_dir.mkdir()

    tool = UnrealDetectProjectTool()
    res = await tool.execute(search_path=str(outside_dir), allowed_folders=[sandbox_dir])

    assert res.status == "error"
    assert "Access denied" in res.error or "outside the allowed project sandbox" in res.error


@pytest.mark.anyio
async def test_unreal_detect_project_with_explicit_uproject_file(mock_ue_project):
    tool = UnrealDetectProjectTool()
    uproject_file = mock_ue_project["uproject_file"]
    proj_dir = mock_ue_project["proj_dir"]

    res = await tool.execute(search_path=str(uproject_file), allowed_folders=[proj_dir])
    assert res.status == "success"
    assert res.result["project_name"] == "MyProject"


@pytest.mark.anyio
async def test_unreal_read_logs_tail_longer_than_file(mock_ue_project):
    tool = UnrealReadLogsTool()
    proj_dir = mock_ue_project["proj_dir"]

    # Request 500 lines when file has 4 lines
    res = await tool.execute(project_path=str(proj_dir), lines_count=500, allowed_folders=[proj_dir])
    assert res.status == "success"
    assert res.metadata["retrieved_lines"] == 4
