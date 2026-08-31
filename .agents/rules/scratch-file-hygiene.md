# Scratch File & Tool Testing Hygiene Rule

## 1. Scratch & Temporary Artifact Locations
- All tool self-tests, experimental executions, and temporary artifacts (such as `write_file`, `patch_file`, or script executions) MUST write their scratch files into the isolated `workspace/` directory or a system temp directory (`tempfile` / `tmp_path`).
- NEVER create, leave, or commit scratch test files directly into the repository source tree (`backend/`, `desktop-app/`, `desktop/`, etc.).

## 2. Mandatory Cleanup
- Any scratch file, mock script, or temporary artifact generated during tool verification or trial runs MUST be deleted before reporting completion of the task.
- Ensure that no untracked syntax-broken scripts or dangling scratch modules pollute the backend codebase or break Python package imports.
