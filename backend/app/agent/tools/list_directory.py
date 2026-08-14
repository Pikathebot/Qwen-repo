import os
from pathlib import Path

def list_directory(directory_path: str = ".") -> str:
    """
    List files and folders in a directory. Always use this tool when the user asks to list, view, or explore directory contents.

    Args:
        directory_path: Relative directory path within the project (e.g. '.', 'docs', 'backend'). Defaults to '.'.
    """
    raw_path = directory_path.strip()
    path = Path(raw_path)

    # Robust path resolution for small models
    if not path.exists():
        # Try stripping leading dots/slashes (e.g. .docs -> docs)
        stripped = raw_path.lstrip("./\\")
        if stripped and Path(stripped).exists():
            path = Path(stripped)
        elif not os.path.isabs(raw_path):
            base_candidate = Path(".") / Path(raw_path).name
            if base_candidate.exists():
                path = base_candidate

    if not path.exists():
        return f"Error: Directory not found at '{directory_path}'."
    if not path.is_dir():
        return f"Error: '{directory_path}' is a file, not a directory."
    
    try:
        entries = sorted(os.listdir(path))
        if not entries:
            return f"Directory '{directory_path}' is empty."
        
        result_lines = [f"Contents of '{directory_path}':"]
        for entry in entries:
            full_item = path / entry
            marker = "[DIR]" if full_item.is_dir() else "[FILE]"
            result_lines.append(f"  {marker} {entry}")
        
        return "\n".join(result_lines)
    except Exception as e:
        return f"Error listing directory '{directory_path}': {str(e)}"
