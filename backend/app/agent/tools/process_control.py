import logging
import os
import time
from typing import Optional, Any
import psutil

logger = logging.getLogger("jarvis.agent.tools.process_control")


def list_processes(filter_name: Optional[str] = None) -> str:
    """
    List running operating system processes with PID, process name, CPU usage %, and Memory (MB).
    Read-only operation.

    Args:
        filter_name: Optional process name substring to filter results (case-insensitive).
    """
    filter_clean = (filter_name or "").strip().lower()
    results: list[dict[str, Any]] = []

    try:
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_info']):
            try:
                pinfo = proc.info
                pname = pinfo.get('name') or "unknown"
                if filter_clean and filter_clean not in pname.lower():
                    continue

                mem_mb = 0.0
                mem_info = pinfo.get('memory_info')
                if mem_info:
                    mem_mb = round(mem_info.rss / (1024 * 1024), 1)

                results.append({
                    "pid": pinfo.get('pid'),
                    "name": pname,
                    "cpu_percent": pinfo.get('cpu_percent') or 0.0,
                    "memory_mb": mem_mb
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
    except Exception as e:
        logger.error("Error listing processes: %s", e)
        return f"Error listing processes: {str(e)}"

    if not results:
        if filter_clean:
            return f"No running processes found matching '{filter_name}'."
        return "No running processes found."

    # Sort by memory descending
    results.sort(key=lambda x: x["memory_mb"], reverse=True)

    lines = [f"{'PID':<8} {'Name':<35} {'Memory (MB)':<14} {'CPU %':<8}", "-" * 68]
    for r in results[:50]:  # Cap at 50 to prevent excessive token output
        lines.append(f"{r['pid']:<8} {r['name']:<35} {r['memory_mb']:<14.1f} {r['cpu_percent']:<8.1f}")

    if len(results) > 50:
        lines.append(f"... and {len(results) - 50} more processes.")

    return "\n".join(lines)


def kill_process(pid_or_name: str) -> str:
    """
    Terminate a running operating system process by PID or process name.
    Attempts graceful termination (terminate) with a grace period fallback to forced kill.
    Hard-blocks any attempt to terminate Jarvis's own backend process.

    Args:
        pid_or_name: Target process PID (e.g. '1234') or process name (e.g. 'notepad.exe', 'notepad').
    """
    target = str(pid_or_name or "").strip()
    if not target:
        return "Error: No process PID or name provided to terminate."

    current_pid = os.getpid()
    parent_pid = os.getppid() if hasattr(os, "getppid") else None

    # 1. Hard-block self-termination
    if target.isdigit():
        target_pid = int(target)
        if target_pid in (current_pid, parent_pid):
            logger.warning("Blocked attempt to kill Jarvis self backend process (PID: %d)", target_pid)
            return f"Error: Cannot terminate Jarvis backend or launcher process (PID: {target_pid}). Self-protection enforced."

    procs_to_terminate: list[psutil.Process] = []

    # 2. Locate target processes
    if target.isdigit():
        try:
            p = psutil.Process(int(target))
            procs_to_terminate.append(p)
        except psutil.NoSuchProcess:
            return f"Error: No running process found with PID {target}."
        except psutil.AccessDenied:
            return f"Error: Access denied accessing process with PID {target}."
    else:
        target_lower = target.lower()
        target_exe = target_lower if target_lower.endswith(".exe") else f"{target_lower}.exe"

        skipped_self_count = 0
        for p in psutil.process_iter(['pid', 'name']):
            try:
                p_name = (p.info.get('name') or "").lower()
                if p_name in (target_lower, target_exe):
                    # Check if matching process is Jarvis self PID
                    if p.pid in (current_pid, parent_pid):
                        logger.warning("Skipping Jarvis self process in name-matched kill: %d", p.pid)
                        skipped_self_count += 1
                        continue
                    procs_to_terminate.append(p)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        if not procs_to_terminate:
            if skipped_self_count > 0:
                return f"Error: Cannot terminate Jarvis backend or launcher process ('{target}'). Self-protection enforced."
            return f"Error: No running processes found matching '{target}'."

    # 3. Graceful termination with timeout fallback to force kill
    terminated_details: list[str] = []
    errors: list[str] = []

    for proc in procs_to_terminate:
        try:
            pid = proc.pid
            name = proc.name()
            proc.terminate()
            terminated_details.append(f"{name} (PID {pid})")
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            errors.append(f"PID {proc.pid}: {str(e)}")

    # Wait up to 3.0 seconds for processes to exit
    gone, alive = psutil.wait_procs(procs_to_terminate, timeout=3.0)

    # Force kill any lingering processes
    for proc in alive:
        try:
            logger.warning("Process PID %d did not terminate gracefully; force killing.", proc.pid)
            proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            errors.append(f"PID {proc.pid} force kill failed: {str(e)}")

    success_msg = f"Successfully terminated {len(terminated_details)} process instance(s): {', '.join(terminated_details)}."
    if errors:
        success_msg += f" Warnings/Errors: {'; '.join(errors)}"

    logger.info("kill_process completed: %s", success_msg)
    return success_msg
