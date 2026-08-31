import os
import pytest
from pathlib import Path
from sqlmodel import create_engine, SQLModel, Session, select

from app.database.models import Artifact, ArtifactVersion, Project
from app.tools.base import BaseTool, ToolResult, PermissionLevel, PermissionDeniedError
from app.tools.registry import ToolRegistry
from app.tools.filesystem import (
    ReadFileTool,
    WriteFileTool,
    EditFileTool,
    CreateDirectoryTool,
    ListDirectoryTool,
    validate_path
)
from app.agent.tool_result_truncator import truncate_tool_result


@pytest.fixture
def sandbox_env(tmp_path):
    """Create isolated sandbox directory structure with local test DB."""
    test_db = tmp_path / "test_tool_system.db"
    test_engine = create_engine(f"sqlite:///{test_db}", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(test_engine)

    import app.tools.filesystem
    orig_engine = app.tools.filesystem.engine
    app.tools.filesystem.engine = test_engine

    proj_dir = tmp_path / "workspace" / "projects" / "test_proj"
    proj_dir.mkdir(parents=True, exist_ok=True)

    # Create test files
    sample_file = proj_dir / "sample.py"
    sample_file.write_text("line 1\nline 2\nline 3\nline 4\nline 5\n", encoding="utf-8")

    sub_dir = proj_dir / "subfolder"
    sub_dir.mkdir(parents=True, exist_ok=True)
    sub_file = sub_dir / "nested.txt"
    sub_file.write_text("nested content", encoding="utf-8")

    # Outside forbidden file
    outside_dir = tmp_path / "forbidden_system"
    outside_dir.mkdir(parents=True, exist_ok=True)
    outside_file = outside_dir / "secret.txt"
    outside_file.write_text("CONFIDENTIAL", encoding="utf-8")

    # Create project record
    with Session(test_engine) as session:
        p = Project(id="test_proj", name="Test Project", workspace_path=str(proj_dir))
        session.add(p)
        session.commit()

    yield {
        "engine": test_engine,
        "proj_dir": proj_dir,
        "sample_file": sample_file,
        "sub_dir": sub_dir,
        "outside_dir": outside_dir,
        "outside_file": outside_file,
        "allowed_folders": [proj_dir]
    }

    app.tools.filesystem.engine = orig_engine


def test_validate_path_allowed_inside_sandbox(sandbox_env):
    allowed = sandbox_env["allowed_folders"]
    sample_path = str(sandbox_env["sample_file"])

    res = validate_path(sample_path, allowed_folders=allowed)
    assert res == sandbox_env["sample_file"].resolve()


def test_validate_path_blocks_relative_traversal(sandbox_env):
    allowed = sandbox_env["allowed_folders"]
    traversal_path = str(sandbox_env["proj_dir"] / ".." / ".." / "forbidden_system" / "secret.txt")

    with pytest.raises(PermissionDeniedError):
        validate_path(traversal_path, allowed_folders=allowed)


def test_validate_path_blocks_symlink_escape(sandbox_env):
    """Amendment 1: Assert symlink pointing outside sandbox is caught and rejected."""
    allowed = sandbox_env["allowed_folders"]
    symlink_path = sandbox_env["proj_dir"] / "symlink_to_outside"

    try:
        os.symlink(sandbox_env["outside_dir"], symlink_path, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Symlink creation not permitted in current OS environment")

    escaped_file = str(symlink_path / "secret.txt")
    with pytest.raises(PermissionDeniedError):
        validate_path(escaped_file, allowed_folders=allowed)


@pytest.mark.anyio
async def test_read_file_tool(sandbox_env):
    tool = ReadFileTool()
    allowed = sandbox_env["allowed_folders"]

    # Read full file
    res = await tool.execute(path=str(sandbox_env["sample_file"]), allowed_folders=allowed)
    assert res.status == "success"
    assert "line 1" in res.result
    assert "line 5" in res.result

    # Read with line ranges (lines 2 to 4)
    range_res = await tool.execute(
        path=str(sandbox_env["sample_file"]),
        start_line=2,
        end_line=4,
        allowed_folders=allowed
    )
    assert range_res.status == "success"
    assert "line 2\nline 3\nline 4\n" == range_res.result


@pytest.mark.anyio
async def test_write_file_tool_and_version_snapshot(sandbox_env):
    tool = WriteFileTool()
    allowed = sandbox_env["allowed_folders"]
    engine = sandbox_env["engine"]

    # 1. Write a new file
    new_file = sandbox_env["proj_dir"] / "created.py"
    res = await tool.execute(
        path=str(new_file),
        content="print('Hello World')",
        project_id="test_proj",
        allowed_folders=allowed
    )
    assert res.status == "success"
    assert new_file.read_text(encoding="utf-8") == "print('Hello World')"

    # 2. Overwrite file and check version snapshot recorded
    res_overwrite = await tool.execute(
        path=str(new_file),
        content="print('Updated World')",
        project_id="test_proj",
        allowed_folders=allowed
    )
    assert res_overwrite.status == "success"
    assert new_file.read_text(encoding="utf-8") == "print('Updated World')"

    with Session(engine) as session:
        artifacts = session.exec(select(Artifact).where(Artifact.name == "created.py")).all()
        assert len(artifacts) == 1
        versions = session.exec(select(ArtifactVersion).where(ArtifactVersion.artifact_id == artifacts[0].id)).all()
        assert len(versions) >= 1
        assert "Hello World" in versions[0].content


@pytest.mark.anyio
async def test_edit_file_tool_targeted_diff(sandbox_env):
    tool = EditFileTool()
    allowed = sandbox_env["allowed_folders"]
    sample_file = sandbox_env["sample_file"]

    # Targeted replacement
    res = await tool.execute(
        path=str(sample_file),
        old_text="line 3",
        new_text="line THREE (REPLACED)",
        project_id="test_proj",
        allowed_folders=allowed
    )
    assert res.status == "success"
    updated_content = sample_file.read_text(encoding="utf-8")
    assert "line THREE (REPLACED)" in updated_content
    assert "line 1" in updated_content
    assert "line 5" in updated_content

    # Error when old_text not found
    err_res = await tool.execute(
        path=str(sample_file),
        old_text="NON_EXISTENT_TEXT",
        new_text="replacement",
        project_id="test_proj",
        allowed_folders=allowed
    )
    assert err_res.status == "error"
    assert "not found" in err_res.error


@pytest.mark.anyio
async def test_create_directory_tool(sandbox_env):
    tool = CreateDirectoryTool()
    allowed = sandbox_env["allowed_folders"]

    new_dir = sandbox_env["proj_dir"] / "deep" / "nested" / "dir"
    res = await tool.execute(path=str(new_dir), allowed_folders=allowed)
    assert res.status == "success"
    assert new_dir.exists()
    assert new_dir.is_dir()


@pytest.mark.anyio
async def test_list_directory_tool(sandbox_env):
    tool = ListDirectoryTool()
    allowed = sandbox_env["allowed_folders"]

    res = await tool.execute(path=str(sandbox_env["proj_dir"]), allowed_folders=allowed)
    assert res.status == "success"
    names = [entry["name"] for entry in res.result]
    assert "sample.py" in names
    assert "subfolder" in names


def test_tool_result_truncation():
    # Small text not truncated
    short_text = "short log output"
    res, was_trunc = truncate_tool_result(short_text, max_chars=100)
    assert res == short_text
    assert was_trunc is False

    # Large text truncated
    long_text = "A" * 500
    res, was_trunc = truncate_tool_result(long_text, max_chars=100)
    assert was_trunc is True
    assert len(res) > 100
    assert "[Content truncated" in res


@pytest.mark.anyio
async def test_tool_registry():
    registry = ToolRegistry()
    tool = ReadFileTool()
    registry.register(tool)

    assert registry.get_tool("filesystem.read") is tool
    schema = registry.get_tools_schema()
    assert len(schema) == 1
    assert schema[0]["function"]["name"] == "filesystem.read"

    # Execution through registry
    non_existent = await registry.execute_tool("unknown.tool", {})
    assert non_existent.status == "error"
    assert "Unrecognized tool" in non_existent.error
