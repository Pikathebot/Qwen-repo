import os
from pathlib import Path
from typing import Optional
from app.config import settings

def list_directory(directory_path: str = ".", workspace_path: Optional[str] = None) -> str:
    """
    List files and folders in a directory inside the project workspace.
    Always use this tool when the user asks to list, view, or explore directory contents.

    Args:
        directory_path: Relative directory path within the project (e.g. '.', 'docs', 'backend'). Defaults to '.'.
        workspace_path: Optional active project workspace root boundary.
    """
    raw_path = str(directory_path or ".").strip()
    ws_root = Path(workspace_path or settings.workspace_path).resolve()

    if not raw_path or raw_path == ".":
        resolved_path = ws_root
    else:
        p = Path(raw_path)
        if p.is_absolute():
            resolved_path = p.resolve()
        else:
            resolved_path = (ws_root / p).resolve()

    # Anti-traversal security check: ensure path is inside active workspace boundary
    if resolved_path != ws_root and ws_root not in resolved_path.parents:
        return f"Error: Access denied. Directory '{directory_path}' resolves outside the active project workspace boundary ('{ws_root}')."

    path = resolved_path

    if not path.exists():
        return f"Error: Directory not found at '{directory_path}' within workspace '{ws_root}'."
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
