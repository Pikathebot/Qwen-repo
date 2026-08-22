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
    web_search,
    fetch_url,
    write_file,
    patch_file,
    find_files,
    grep_in_files,
]



from pydantic import BaseModel, Field
from typing import Optional


class ReadFileArgs(BaseModel):
    file_path: str = Field(..., description="Path to the file to read")


class ListDirectoryArgs(BaseModel):
    path: str = Field(default=".", description="Path of directory to list")


class ExecuteCommandArgs(BaseModel):
    command: str = Field(..., description="Shell command string to execute")


class DeleteFileArgs(BaseModel):
    file_path: str = Field(..., description="Path of file to delete")


class WebSearchArgs(BaseModel):
    query: str = Field(..., description="Search query string")
    max_results: int = Field(default=5, ge=1, le=10, description="Max results")


class FetchUrlArgs(BaseModel):
    url: str = Field(..., description="Web URL to fetch")
    max_chars: int = Field(default=8000, ge=500, le=25000, description="Max character budget")


class WriteFileArgs(BaseModel):
    file_path: str = Field(..., description="Target file path")
    content: str = Field(..., description="Content to write")
    overwrite: bool = Field(default=True, description="Overwrite if exists")


class PatchFileArgs(BaseModel):
    file_path: str = Field(..., description="Target file path")
    search_block: str = Field(..., description="Exact code block to replace")
    replacement_block: str = Field(..., description="New code block")


class FindFilesArgs(BaseModel):
    pattern: str = Field(..., description="File pattern or extension")
    root_dir: str = Field(default=".", description="Root search directory")


class GrepInFilesArgs(BaseModel):
    pattern: str = Field(..., description="Regex pattern or keyword")
    path: str = Field(default=".", description="Directory path")
    max_matches: int = Field(default=50, ge=1, le=200, description="Max match count")
    case_sensitive: bool = Field(default=True, description="Case sensitivity")


TOOL_SCHEMAS: dict[str, type[BaseModel]] = {
    "read_file": ReadFileArgs,
    "list_directory": ListDirectoryArgs,
    "execute_command": ExecuteCommandArgs,
    "delete_file": DeleteFileArgs,
    "web_search": WebSearchArgs,
    "fetch_url": FetchUrlArgs,
    "write_file": WriteFileArgs,
    "patch_file": PatchFileArgs,
    "find_files": FindFilesArgs,
    "grep_in_files": GrepInFilesArgs,
}


def get_tool_schema(tool_name: str) -> Optional[type[BaseModel]]:
    """Retrieve Pydantic validation schema for a registered tool."""
    return TOOL_SCHEMAS.get(tool_name)





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
