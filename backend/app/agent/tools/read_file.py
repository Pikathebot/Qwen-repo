import os
from pathlib import Path
from app.config import settings

def read_file(file_path: str) -> str:
    """
    Read and return the text contents of a LOCAL file on disk. Do NOT use this tool for web URLs (http/https); use fetch_url instead.

    Args:
        file_path: Relative path or name of the local file to read (e.g. 'docs/PLAN.md', 'script.py', 'test.txt').
    """
    raw_path = str(file_path or "").strip()
    if raw_path.startswith("http://") or raw_path.startswith("https://"):
        return f"Error: '{file_path}' is a web URL, not a local file on disk. Please invoke the 'fetch_url(url=\"{file_path}\")' tool to read this web page."

    path = Path(raw_path)

    if not path.exists():
        # 1. Check current working directory
        base_candidate = Path(".") / Path(raw_path).name
        if base_candidate.exists() and base_candidate.is_file():
            path = base_candidate
        else:
            stripped = raw_path.lstrip("./\\")
            if stripped and Path(stripped).exists():
                path = Path(stripped)

    # 2. Check workspace directories and project folders
    if not path.exists():
        ws_root = Path(settings.workspace_path).resolve()
        candidates = [
            ws_root / raw_path,
            ws_root / "files" / Path(raw_path).name,
            ws_root / Path(raw_path).name,
        ]
        for cand in candidates:
            if cand.exists() and cand.is_file():
                path = cand
                break

    # 3. Search inside workspace recursively if still not found
    if not path.exists():
        ws_root = Path(settings.workspace_path).resolve()
        if ws_root.exists() and ws_root.is_dir():
            target_name = Path(raw_path).name
            for found_file in ws_root.rglob(target_name):
                if found_file.is_file():
                    path = found_file
                    break

    if not path.exists():
        return f"Error: File not found at '{file_path}'."
    if path.is_dir():
        return f"Error: '{file_path}' is a directory, not a file."

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception as e:
        return f"Error reading file '{file_path}': {str(e)}"
