import os
import logging
from pathlib import Path

logger = logging.getLogger("jarvis.agent.tools.write_file")


def write_file(file_path: str, content: str, overwrite: bool = True) -> str:
    """
    Create or overwrite a file on disk with the provided text content.
    Automatically creates any missing parent directories. Always use this tool when the user asks to create, write, or generate a new file or script.

    Args:
        file_path: Relative path of the file to create (e.g. 'scripts/run.py', 'docs/notes.md').
        content: The text/code content to write into the file.
        overwrite: Whether to overwrite the file if it already exists (default True).
    """
    clean_path_str = str(file_path or "").strip()
    if not clean_path_str:
        return "Error: File path cannot be empty."

    path = Path(clean_path_str)

    if path.exists() and path.is_dir():
        return f"Error: Cannot write to '{file_path}' because it is a directory."

    if path.exists() and not overwrite:
        return f"Error: File '{file_path}' already exists and overwrite is set to False."

    try:
        # Automatically ensure parent directory exists
        if path.parent and not path.parent.exists():
            path.parent.mkdir(parents=True, exist_ok=True)

        content_str = str(content or "")
        path.write_text(content_str, encoding="utf-8")
        
        line_count = len(content_str.splitlines()) if content_str else 0
        char_count = len(content_str)
        
        logger.info("Successfully wrote %d chars (%d lines) to '%s'", char_count, line_count, file_path)
        return f"Successfully wrote {char_count} characters ({line_count} lines) to '{file_path}'."
    except Exception as e:
        logger.error("Failed to write file '%s': %s", file_path, e)
        return f"Error writing file '{file_path}': {str(e)}"
