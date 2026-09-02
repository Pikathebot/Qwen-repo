import pytest
from sqlmodel import create_engine, SQLModel
from app.tools.base import PermissionLevel
from app.tools.patch_tools import (
    ApplyPatchTool,
    ReplaceRangeTool,
    InsertTool,
    DeleteRangeTool,
)
from app.services.patch_validator import PatchValidator
from app.services.file_version_service import FileVersionService


@pytest.fixture
def patch_env(tmp_path):
    """Provides isolated patch tools and file version service in a sandbox tmp_path."""
    db_file = tmp_path / "test_patch_tools.db"
    engine = create_engine(f"sqlite:///{db_file}")
    SQLModel.metadata.create_all(engine)

    file_ver_service = FileVersionService(db_engine=engine)
    validator = PatchValidator()

    apply_tool = ApplyPatchTool(patch_validator=validator, file_version_service=file_ver_service)
    replace_tool = ReplaceRangeTool(file_version_service=file_ver_service)
    insert_tool = InsertTool(file_version_service=file_ver_service)
    delete_tool = DeleteRangeTool(file_version_service=file_ver_service)

    return {
        "tmp_path": tmp_path,
        "file_ver_service": file_ver_service,
        "validator": validator,
        "apply_tool": apply_tool,
        "replace_tool": replace_tool,
        "insert_tool": insert_tool,
        "delete_tool": delete_tool,
    }


def test_tools_permission_levels(patch_env):
    """Verify all 4 patch editing tools require explicit user confirmation (§16)."""
    assert patch_env["apply_tool"].permission_level == PermissionLevel.CONFIRMATION_REQUIRED
    assert patch_env["replace_tool"].permission_level == PermissionLevel.CONFIRMATION_REQUIRED
    assert patch_env["insert_tool"].permission_level == PermissionLevel.CONFIRMATION_REQUIRED
    assert patch_env["delete_tool"].permission_level == PermissionLevel.CONFIRMATION_REQUIRED


@pytest.mark.asyncio
async def test_apply_patch_tool_success(patch_env):
    tmp = patch_env["tmp_path"]
    target = tmp / "calc.py"
    target.write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")

    patch = (
        "@@ -1,2 +1,3 @@\n"
        " def add(a, b):\n"
        "+    # Added docstring\n"
        "     return a + b\n"
    )

    res = await patch_env["apply_tool"].execute(
        file_path=str(target),
        patch=patch,
        session_id="s1",
        allowed_folders=[tmp]
    )

    assert res.status == "success"
    assert "Applied 1 hunk(s)" in res.summary
    updated_content = target.read_text(encoding="utf-8")
    assert "# Added docstring" in updated_content

    # Check that a version snapshot was recorded
    versions = patch_env["file_ver_service"].get_versions(str(target), "s1")
    assert len(versions) == 1


@pytest.mark.asyncio
async def test_apply_patch_tool_invalid_patch_rejection(patch_env):
    tmp = patch_env["tmp_path"]
    target = tmp / "service.py"
    target.write_text("def serve():\n    pass\n", encoding="utf-8")

    bad_patch = (
        "@@ -1,2 +1,2 @@\n"
        " def non_matching_header():\n"
        "-    pass\n"
        "+    return 42\n"
    )

    res = await patch_env["apply_tool"].execute(
        file_path=str(target),
        patch=bad_patch,
        session_id="s1",
        allowed_folders=[tmp]
    )

    assert res.status == "error"
    assert "Patch validation failed" in res.error
    # Original file must remain untouched
    assert target.read_text(encoding="utf-8") == "def serve():\n    pass\n"


@pytest.mark.asyncio
async def test_replace_range_tool(patch_env):
    tmp = patch_env["tmp_path"]
    target = tmp / "data.txt"
    target.write_text("line1\nline2\nline3\nline4\n", encoding="utf-8")

    # Replace lines 2-3
    res = await patch_env["replace_tool"].execute(
        file_path=str(target),
        start_line=2,
        end_line=3,
        new_content="new_line2\nnew_line3_extra",
        session_id="s1",
        allowed_folders=[tmp]
    )

    assert res.status == "success"
    updated = target.read_text(encoding="utf-8")
    assert updated == "line1\nnew_line2\nnew_line3_extra\nline4\n"


@pytest.mark.asyncio
async def test_replace_range_out_of_bounds(patch_env):
    tmp = patch_env["tmp_path"]
    target = tmp / "short.txt"
    target.write_text("only_one_line\n", encoding="utf-8")

    res = await patch_env["replace_tool"].execute(
        file_path=str(target),
        start_line=2,
        end_line=5,
        new_content="invalid",
        allowed_folders=[tmp]
    )
    assert res.status == "error"
    assert "Invalid start_line" in res.error


@pytest.mark.asyncio
async def test_insert_tool(patch_env):
    tmp = patch_env["tmp_path"]
    target = tmp / "app.py"
    target.write_text("import sys\n\ndef run():\n    pass\n", encoding="utf-8")

    # Insert import at line 2
    res = await patch_env["insert_tool"].execute(
        file_path=str(target),
        line_number=2,
        content="import os",
        session_id="s1",
        allowed_folders=[tmp]
    )

    assert res.status == "success"
    updated = target.read_text(encoding="utf-8")
    assert "import sys\nimport os\n\ndef run():" in updated


@pytest.mark.asyncio
async def test_delete_range_tool(patch_env):
    tmp = patch_env["tmp_path"]
    target = tmp / "clean.py"
    target.write_text("line1\n# DEBUG LOG\n# DEBUG LOG 2\nline4\n", encoding="utf-8")

    # Delete debug lines 2-3
    res = await patch_env["delete_tool"].execute(
        file_path=str(target),
        start_line=2,
        end_line=3,
        session_id="s1",
        allowed_folders=[tmp]
    )

    assert res.status == "success"
    updated = target.read_text(encoding="utf-8")
    assert updated == "line1\nline4\n"


@pytest.mark.asyncio
async def test_patch_tools_sandbox_boundary_enforcement(patch_env, tmp_path):
    """Verify patch tools reject files outside the allowed sandbox roots (Amendment 3)."""
    sandbox_dir = tmp_path / "sandbox"
    sandbox_dir.mkdir()
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()

    outside_file = outside_dir / "secret.txt"
    outside_file.write_text("secret_data\n", encoding="utf-8")

    res = await patch_env["apply_tool"].execute(
        file_path=str(outside_file),
        patch="@@ -1,1 +1,1 @@\n-secret_data\n+hacked\n",
        allowed_folders=[sandbox_dir]
    )
    assert res.status == "error"
    assert "Access denied" in res.error or "outside the allowed project sandbox" in res.error
