import os
from pathlib import Path

def read_file(file_path: str) -> str:
    """
    Read and return the text contents of a LOCAL file on disk. Do NOT use this tool for web URLs (http/https); use fetch_url instead.

    Args:
        file_path: Relative path of the local file to read (e.g. 'docs/PLAN.md', 'test.txt').
    """
    raw_path = str(file_path or "").strip()
    if raw_path.startswith("http://") or raw_path.startswith("https://"):
        return f"Error: '{file_path}' is a web URL, not a local file on disk. Please invoke the 'fetch_url(url=\"{file_path}\")' tool to read this web page."

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
