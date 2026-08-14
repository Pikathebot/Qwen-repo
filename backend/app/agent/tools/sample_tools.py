import os
import subprocess
from pathlib import Path

def execute_command(command: str) -> str:
    """
    Execute a shell command locally in the terminal. Use only when terminal commands or CLI execution is requested.

    Args:
        command: The shell command string to execute (e.g. 'git status', 'python --version').
    """
    try:
        cmd_to_run = f'powershell -NoProfile -NonInteractive -Command "{command}"' if os.name == "nt" else command
        result = subprocess.run(
            cmd_to_run,
            shell=True,
            capture_output=True,
            text=True,
            timeout=10
        )
        output = result.stdout.strip()
        if result.stderr:
            output += ("\n" if output else "") + f"[Stderr]: {result.stderr.strip()}"
        return output or f"[Process exited with code {result.returncode}]"
    except subprocess.TimeoutExpired:
        return "Error: Command execution timed out (10s limit)."
    except Exception as e:
        return f"Error executing command '{command}': {str(e)}"


def delete_file(file_path: str) -> str:
    """
    Permanently delete or remove a file from disk. Use ONLY when the user explicitly requests deleting or removing a file.

    Args:
        file_path: Relative or absolute path of the file to delete.
    """
    raw_path = file_path.strip().lstrip("./\\")
    path = Path(raw_path)
    
    if not path.exists():
        return f"Error: File '{file_path}' does not exist."
    if path.is_dir():
        return f"Error: '{file_path}' is a directory, not a file."
    
    try:
        os.remove(path)
        return f"Successfully deleted file '{file_path}'."
    except Exception as e:
        return f"Error deleting file '{file_path}': {str(e)}"
