import os
import sys
import time
import socket
import traceback
import subprocess
import logging
from pathlib import Path
import httpx

# Configure paths
ROOT_DIR = Path(__file__).resolve().parent
LOG_FILE = ROOT_DIR / "launcher.log"
VENV_PYTHON = ROOT_DIR / ".venv" / "Scripts" / "python.exe"
if not VENV_PYTHON.exists():
    VENV_PYTHON = sys.executable

BACKEND_DIR = ROOT_DIR / "backend"

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
    
    logger.info("Starting Jarvis FastAPI backend server on http://127.0.0.1:8000 ...")
    proc = subprocess.Popen(
        [
            str(VENV_PYTHON),
            "-m", "uvicorn",
            "app.main:app",
            "--host", "127.0.0.1",
            "--port", "8000",
            "--reload"
        ],
        cwd=str(ROOT_DIR),
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
        logger.warning("Another instance of Jarvis Desktop is already running. Focusing existing instance.")
        return None


def main():
    lock_socket = acquire_single_instance_lock()
    if lock_socket is None:
        logger.info("Exiting duplicate launch attempt.")
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
        launch_desktop()

    except Exception as e:
        logger.error("Error in Jarvis launcher: %s\n%s", e, traceback.format_exc())
        raise e
    finally:
        if backend_proc:
            logger.info("Stopping background backend process...")
            try:
                backend_proc.terminate()
            except Exception:
                pass


if __name__ == "__main__":
    main()
