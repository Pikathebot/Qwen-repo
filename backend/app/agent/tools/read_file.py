import os
from pathlib import Path
from typing import Optional
from app.config import settings

def read_file(file_path: str, workspace_path: Optional[str] = None) -> str:
    """
    Read and return the text contents of a LOCAL file on disk inside the project workspace.
    Do NOT use this tool for web URLs (http/https); use fetch_url instead.

    Args:
        file_path: Relative path or name of the local file to read (e.g. 'docs/PLAN.md', 'script.py', 'test.txt').
        workspace_path: Optional active project workspace root boundary.
    """
    raw_path = str(file_path or "").strip()
    if not raw_path:
        return "Error: File path cannot be empty."

    if raw_path.startswith("http://") or raw_path.startswith("https://"):
        return f"Error: '{file_path}' is a web URL, not a local file on disk. Please invoke the 'fetch_url(url=\"{file_path}\")' tool to read this web page."

    ws_root = Path(workspace_path or settings.workspace_path).resolve()

    # Resolve target path relative to workspace root if not absolute
    p = Path(raw_path)
    if p.is_absolute():
        resolved_path = p.resolve()
    else:
        resolved_path = (ws_root / p).resolve()

    # Anti-traversal security check: ensure path is inside active workspace boundary
    if resolved_path != ws_root and ws_root not in resolved_path.parents:
        return f"Error: Access denied. Path '{file_path}' resolves outside the active project workspace boundary ('{ws_root}')."

    path = resolved_path

    # Fallback resolution inside workspace if not found directly
    if not path.exists():
        candidates = [
            ws_root / "files" / Path(raw_path).name,
            ws_root / Path(raw_path).name,
        ]
        for cand in candidates:
            cand_res = cand.resolve()
            if (cand_res == ws_root or ws_root in cand_res.parents) and cand_res.exists() and cand_res.is_file():
                path = cand_res
                break

    # Recursive search inside workspace if still not found
    if not path.exists() and ws_root.exists() and ws_root.is_dir():
        target_name = Path(raw_path).name
        for found_file in ws_root.rglob(target_name):
            if found_file.is_file():
                cand_res = found_file.resolve()
                if cand_res == ws_root or ws_root in cand_res.parents:
                    path = cand_res
                    break

    if not path.exists():
        return f"Error: File not found at '{file_path}' within workspace '{ws_root}'."
    if path.is_dir():
        return f"Error: '{file_path}' is a directory, not a file."

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception as e:
        return f"Error reading file '{file_path}': {str(e)}"
