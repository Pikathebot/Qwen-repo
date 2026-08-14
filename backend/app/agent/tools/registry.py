import inspect
import logging
from typing import Callable, Any
from app.agent.tools.read_file import read_file
from app.agent.tools.list_directory import list_directory
from app.agent.tools.sample_tools import execute_command, delete_file
from app.agent.tools.web_search import web_search
from app.agent.tools.fetch_url import fetch_url
from app.agent.tools.write_file import write_file
from app.agent.tools.patch_file import patch_file
from app.agent.tools.file_search import find_files, grep_in_files

logger = logging.getLogger("jarvis.agent.tools")

TOOL_FUNCTIONS: dict[str, Callable[..., Any]] = {
    "read_file": read_file,
    "list_directory": list_directory,
    "execute_command": execute_command,
    "delete_file": delete_file,
    "web_search": web_search,
    "fetch_url": fetch_url,
    "write_file": write_file,
    "patch_file": patch_file,
    "find_files": find_files,
    "grep_in_files": grep_in_files,
}

AVAILABLE_TOOLS: list[Callable[..., Any]] = [
    read_file,
    list_directory,
    execute_command,
    delete_file,
    web_search,
    fetch_url,
    write_file,
    patch_file,
    find_files,
    grep_in_files,
]




def execute_tool(tool_name: str, arguments: dict[str, Any]) -> str:
    """
    Execute a registered tool by name with provided arguments, automatically
    filtering any extra hallucinated keyword arguments from smaller LLMs.
    """
    if tool_name not in TOOL_FUNCTIONS:
        logger.warning("Attempted to execute unregistered tool: '%s'", tool_name)
        return f"Error: Tool '{tool_name}' is not registered."
    
    func = TOOL_FUNCTIONS[tool_name]
    try:
        # Filter arguments based on function signature
        sig = inspect.signature(func)
        valid_params = set(sig.parameters.keys())
        filtered_args = {k: v for k, v in arguments.items() if k in valid_params}

        logger.info("Executing tool '%s' with filtered args: %s", tool_name, filtered_args)
        result = func(**filtered_args)
        return str(result)
    except TypeError as te:
        logger.error("Argument error calling '%s': %s", tool_name, te)
        return f"Error invalid arguments for '{tool_name}': {str(te)}"
    except Exception as e:
        logger.error("Unhandled error in tool '%s': %s", tool_name, e)
        return f"Error executing tool '{tool_name}': {str(e)}"
