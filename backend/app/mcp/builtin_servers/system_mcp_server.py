import json
import os
import shutil
import sys
import time

try:
    import psutil
except ImportError:
    psutil = None


def handle_initialize(params: dict) -> dict:
    return {
        "protocolVersion": "2024-11-05",
        "capabilities": {
            "tools": {}
        },
        "serverInfo": {
            "name": "system_diagnostics_server",
            "version": "1.0.0"
        }
    }


def handle_tools_list(params: dict) -> dict:
    return {
        "tools": [
            {
                "name": "get_disk_usage",
                "description": "Get disk storage usage (total, used, free) for a specific mount or path.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path or drive to check disk usage for (e.g. '.', 'C:', 'D:'). Defaults to '.'."
                        }
                    },
                    "required": []
                }
            },
            {
                "name": "get_system_uptime",
                "description": "Get the system uptime in human-readable format.",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        ]
    }


def handle_tools_call(params: dict) -> dict:
    tool_name = params.get("name")
    args = params.get("arguments", {})

    if tool_name == "get_disk_usage":
        target_path = args.get("path", ".")
        try:
            total, used, free = shutil.disk_usage(target_path)
            total_gb = total / (1024 ** 3)
            used_gb = used / (1024 ** 3)
            free_gb = free / (1024 ** 3)
            percent_used = (used / total) * 100
            
            output = (
                f"Disk Usage for '{target_path}':\n"
                f"- Total: {total_gb:.2f} GB\n"
                f"- Used:  {used_gb:.2f} GB ({percent_used:.1f}%)\n"
                f"- Free:  {free_gb:.2f} GB"
            )
            return {
                "content": [{"type": "text", "text": output}],
                "isError": False
            }
        except Exception as e:
            return {
                "content": [{"type": "text", "text": f"Error retrieving disk usage: {str(e)}"}],
                "isError": True
            }

    elif tool_name == "get_system_uptime":
        try:
            if psutil:
                boot_time = psutil.boot_time()
                uptime_secs = time.time() - boot_time
                hours, remainder = divmod(int(uptime_secs), 3600)
                minutes, seconds = divmod(remainder, 60)
                uptime_str = f"{hours}h {minutes}m {seconds}s"
            else:
                uptime_str = "Available"

            return {
                "content": [{"type": "text", "text": f"System Uptime: {uptime_str}"}],
                "isError": False
            }
        except Exception as e:
            return {
                "content": [{"type": "text", "text": f"Error checking uptime: {str(e)}"}],
                "isError": True
            }

    return {
        "content": [{"type": "text", "text": f"Error: Tool '{tool_name}' not found."}],
        "isError": True
    }


def main():
    """
    Standard stdio JSON-RPC 2.0 loop.
    """
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            req = json.loads(line)
        except Exception:
            continue

        method = req.get("method")
        req_id = req.get("id")
        params = req.get("params", {})

        if method == "initialize":
            result = handle_initialize(params)
            res = {"jsonrpc": "2.0", "id": req_id, "result": result}
            sys.stdout.write(json.dumps(res) + "\n")
            sys.stdout.flush()

        elif method == "notifications/initialized":
            pass

        elif method == "tools/list":
            result = handle_tools_list(params)
            res = {"jsonrpc": "2.0", "id": req_id, "result": result}
            sys.stdout.write(json.dumps(res) + "\n")
            sys.stdout.flush()

        elif method == "tools/call":
            result = handle_tools_call(params)
            res = {"jsonrpc": "2.0", "id": req_id, "result": result}
            sys.stdout.write(json.dumps(res) + "\n")
            sys.stdout.flush()

        elif req_id is not None:
            res = {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Method '{method}' not found"}
            }
            sys.stdout.write(json.dumps(res) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
