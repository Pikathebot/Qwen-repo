import os
import sys
import time
import socket
import traceback
import subprocess
import logging
from pathlib import Path
import httpx

# Configure paths reliably across direct python execution, batch launcher, and PyInstaller exe
if getattr(sys, "frozen", False):
    exe_dir = Path(sys.executable).resolve().parent
    if (exe_dir / "backend").exists():
        ROOT_DIR = exe_dir
    elif (exe_dir.parent / "backend").exists():
        ROOT_DIR = exe_dir.parent
    else:
        ROOT_DIR = exe_dir
else:
    ROOT_DIR = Path(__file__).resolve().parent

LOG_FILE = ROOT_DIR / "launcher.log"
BACKEND_DIR = ROOT_DIR / "backend"

# Locate virtualenv python
VENV_PYTHON = ROOT_DIR / ".venv" / "Scripts" / "python.exe"
if not VENV_PYTHON.exists():
    if (ROOT_DIR.parent / ".venv" / "Scripts" / "python.exe").exists():
        VENV_PYTHON = ROOT_DIR.parent / ".venv" / "Scripts" / "python.exe"
    else:
        import shutil
        found = shutil.which("python.exe")
        VENV_PYTHON = Path(found) if found else Path(sys.executable)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("jarvis.launcher")


def is_backend_running(url: str = "http://127.0.0.1:8000/health") -> bool:
    try:
        r = httpx.get(url, timeout=1.5)
        return r.status_code == 200
    except Exception:
        return False


def start_backend() -> subprocess.Popen:
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{BACKEND_DIR};{ROOT_DIR}"
    backend_log = open(ROOT_DIR / "backend.log", "a", encoding="utf-8")
    
    logger.info("Starting Jarvis FastAPI backend server on http://127.0.0.1:8000 ... (Python: %s)", VENV_PYTHON)
    proc = subprocess.Popen(
        [
            str(VENV_PYTHON),
            "-m", "uvicorn",
            "app.main:app",
            "--host", "127.0.0.1",
            "--port", "8000"
        ],
        cwd=str(BACKEND_DIR),
        env=env,
        stdout=backend_log,
        stderr=backend_log,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    )

    return proc


def acquire_single_instance_lock(port: int = 57321):
    """
    Ensure only one instance of the Jarvis Desktop app runs at a time.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", port))
        return s
    except socket.error:
        logger.warning("Another instance of Jarvis Desktop is already running. Signaling existing instance to show...")
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_sock:
                client_sock.settimeout(2.0)
                client_sock.connect(("127.0.0.1", port))
                client_sock.sendall(b"SHOW\n")
            logger.info("Sent focus/show signal to running Jarvis instance.")
        except Exception as e:
            logger.debug("Could not signal existing instance: %s", e)
        return None


def main():
    lock_socket = acquire_single_instance_lock()
    if lock_socket is None:
        logger.info("Exiting duplicate launch attempt (focus signal sent).")
        sys.exit(0)

    backend_proc = None
    try:
        if not is_backend_running():
            backend_proc = start_backend()
            for _ in range(40):
                if is_backend_running():
                    logger.info("Jarvis backend is online and healthy.")
                    break
                time.sleep(0.3)
        else:
            logger.info("Jarvis backend is already running.")

        # Launch Desktop UI
        sys.path.insert(0, str(ROOT_DIR))
        sys.path.insert(0, str(BACKEND_DIR))
        
        logger.info("Launching Jarvis Desktop UI (Spotlight & System Tray)...")
        from desktop.app import launch_desktop
        launch_desktop(lock_socket)

    except Exception as e:
        logger.error("Error in Jarvis launcher: %s\n%s", e, traceback.format_exc())
        raise e
    finally:
        if backend_proc:
            logger.info("Stopping background backend process...")
            try:
                backend_proc.terminate()
                backend_proc.wait(timeout=2.0)
            except Exception:
                pass
        if lock_socket:
            try:
                lock_socket.close()
            except Exception:
                pass


if __name__ == "__main__":
    main()

