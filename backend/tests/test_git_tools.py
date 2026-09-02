import os
import shutil
import subprocess
import pytest
from pathlib import Path

from app.tools.base import PermissionLevel
from app.tools.git_tools import (
    GitStatusTool,
    GitDiffTool,
    GitLogTool,
    GitCheckoutTool,
    GitCommitTool,
)

git_available = shutil.which("git") is not None
pytestmark = pytest.mark.skipif(not git_available, reason="git executable not found in PATH")


@pytest.fixture
def git_repo(tmp_path):
    """Initializes a local git repository in tmp_path with an initial commit."""
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir(parents=True, exist_ok=True)

    # Initialize repository
    subprocess.run(["git", "init"], cwd=str(repo_dir), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Jarvis Tester"], cwd=str(repo_dir), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "tester@jarvis.ai"], cwd=str(repo_dir), check=True, capture_output=True)

    # Initial commit
    init_file = repo_dir / "README.md"
    init_file.write_text("# Initial Repo\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=str(repo_dir), check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=str(repo_dir), check=True, capture_output=True)

    return repo_dir


def test_git_tools_permission_levels():
    """Verify read-only Git tools are LOW_RISK and mutation tools are CONFIRMATION_REQUIRED (§11)."""
    assert GitStatusTool().permission_level == PermissionLevel.LOW_RISK
    assert GitDiffTool().permission_level == PermissionLevel.LOW_RISK
    assert GitLogTool().permission_level == PermissionLevel.LOW_RISK
    assert GitCheckoutTool().permission_level == PermissionLevel.CONFIRMATION_REQUIRED
    assert GitCommitTool().permission_level == PermissionLevel.CONFIRMATION_REQUIRED


@pytest.mark.anyio
async def test_git_status_tool(git_repo):
    tool = GitStatusTool()

    # 1. Clean working tree
    res_clean = await tool.execute(cwd=str(git_repo), allowed_folders=[git_repo])
    assert res_clean.status == "success"
    assert "clean" in res_clean.result.lower()

    # 2. Add modified file
    test_file = git_repo / "new_file.txt"
    test_file.write_text("hello", encoding="utf-8")

    res_mod = await tool.execute(cwd=str(git_repo), allowed_folders=[git_repo])
    assert res_mod.status == "success"
    assert "new_file.txt" in res_mod.result


@pytest.mark.anyio
async def test_git_diff_tool(git_repo):
    tool = GitDiffTool()

    # Modify existing file
    readme = git_repo / "README.md"
    readme.write_text("# Initial Repo\nAdded line\n", encoding="utf-8")

    # Unstaged diff
    res_unstaged = await tool.execute(cwd=str(git_repo), staged=False, allowed_folders=[git_repo])
    assert res_unstaged.status == "success"
    assert "+Added line" in res_unstaged.result

    # Stage changes
    subprocess.run(["git", "add", "README.md"], cwd=str(git_repo), check=True, capture_output=True)

    # Staged diff
    res_staged = await tool.execute(cwd=str(git_repo), staged=True, allowed_folders=[git_repo])
    assert res_staged.status == "success"
    assert "+Added line" in res_staged.result


@pytest.mark.anyio
async def test_git_log_tool(git_repo):
    tool = GitLogTool()
    res = await tool.execute(cwd=str(git_repo), limit=5, allowed_folders=[git_repo])

    assert res.status == "success"
    assert "Initial commit" in res.result
    assert res.metadata["count"] >= 1


@pytest.mark.anyio
async def test_git_commit_tool_success_and_empty_guards(git_repo):
    tool = GitCommitTool()

    # 1. Empty message rejection
    res_empty_msg = await tool.execute(message="", cwd=str(git_repo), allowed_folders=[git_repo])
    assert res_empty_msg.status == "error"
    assert "cannot be empty" in res_empty_msg.error

    # 2. Empty working tree rejection
    res_clean_commit = await tool.execute(message="Should fail", cwd=str(git_repo), allowed_folders=[git_repo])
    assert res_clean_commit.status == "error"
    assert "Nothing to commit" in res_clean_commit.error

    # 3. Valid commit
    new_file = git_repo / "app.py"
    new_file.write_text("print('nexus')", encoding="utf-8")

    res_success = await tool.execute(message="Add app.py module", cwd=str(git_repo), allowed_folders=[git_repo])
    assert res_success.status == "success"
    assert "Add app.py module" in res_success.summary


@pytest.mark.anyio
async def test_git_checkout_tool_branch_and_file_restore(git_repo):
    tool = GitCheckoutTool()

    # 1. Create and switch to new branch
    subprocess.run(["git", "branch", "feature-x"], cwd=str(git_repo), check=True, capture_output=True)
    res_branch = await tool.execute(target="feature-x", cwd=str(git_repo), allowed_folders=[git_repo])
    assert res_branch.status == "success"

    # 2. Modify file then restore it with checkout
    readme = git_repo / "README.md"
    readme.write_text("corrupted content", encoding="utf-8")

    res_restore = await tool.execute(target="README.md", cwd=str(git_repo), allowed_folders=[git_repo])
    assert res_restore.status == "success"
    assert readme.read_text(encoding="utf-8") == "# Initial Repo\n"


@pytest.mark.anyio
async def test_git_tools_sandbox_boundary_enforcement(tmp_path):
    """Verify Git tools reject directories outside the allowed project sandbox (Amendment 2)."""
    sandbox_dir = tmp_path / "sandbox_workspace"
    sandbox_dir.mkdir()

    outside_dir = tmp_path / "forbidden_outside"
    outside_dir.mkdir()

    tool = GitStatusTool()
    res = await tool.execute(cwd=str(outside_dir), allowed_folders=[sandbox_dir])

    assert res.status == "error"
    assert "Access denied" in res.error or "outside the allowed project sandbox" in res.error
