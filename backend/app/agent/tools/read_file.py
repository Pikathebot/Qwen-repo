import os
from pathlib import Path

def read_file(file_path: str) -> str:
    """
    Read and return the text contents of a file on disk. Always use this tool when the user asks to read, inspect, view, or check what is written inside a file.

    Args:
        file_path: Relative path of the file to read (e.g. 'docs/PLAN.md', 'test.txt').
    """
    raw_path = file_path.strip()
    path = Path(raw_path)

    if not path.exists():
        base_candidate = Path(".") / Path(raw_path).name
        if base_candidate.exists() and base_candidate.is_file():
            path = base_candidate
        else:
            stripped = raw_path.lstrip("./\\")
            if stripped and Path(stripped).exists():
                path = Path(stripped)

    if not path.exists():
        return f"Error: File not found at '{file_path}'."
    if path.is_dir():
        return f"Error: '{file_path}' is a directory, not a file."
    
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception as e:
        return f"Error reading file '{file_path}': {str(e)}"
