import sys
import socket
import pytest
from unittest.mock import patch
from app.main import governor

# Windows socketpair retry patch to prevent transient [WinError 10013] ephemeral port exhaustion
if sys.platform == "win32":
    import random
    def _robust_windows_socketpair(family=socket.AF_INET, type=socket.SOCK_STREAM, proto=0):
        if family == socket.AF_INET:
            host = "127.0.0.1"
        elif family == socket.AF_INET6:
            host = "::1"
        else:
            raise ValueError("Only AF_INET and AF_INET6 socket address families are supported")

        import time
        # Try port 0 first, then random unreserved ports across multiple ranges
        candidate_ports = [0] * 20 + [random.randint(20000, 65000) for _ in range(60)]

        for p in candidate_ports:
            lsock = socket.socket(family, type, proto)
            try:
                lsock.bind((host, p))
                lsock.listen(1)
                actual_port = lsock.getsockname()[1]

                csock = socket.socket(family, type, proto)
                csock.setblocking(False)
                try:
                    csock.connect((host, actual_port))
                except (BlockingIOError, InterruptedError):
                    pass

                ssock, _ = lsock.accept()
                csock.setblocking(True)
                lsock.close()
                return (ssock, csock)
            except (PermissionError, OSError):
                try:
                    lsock.close()
                except Exception:
                    pass
                time.sleep(0.01)

        # Fallback to standard socketpair with retry
        for _ in range(10):
            try:
                if hasattr(socket, "_orig_socketpair"):
                    return socket._orig_socketpair(family, type, proto)
            except (PermissionError, OSError):
                time.sleep(0.02)
        return socket._orig_socketpair(family, type, proto) if hasattr(socket, "_orig_socketpair") else (None, None)

    if not hasattr(socket, "_orig_socketpair"):
        socket._orig_socketpair = socket.socketpair
    socket.socketpair = _robust_windows_socketpair


@pytest.fixture(autouse=True)
def ensure_test_healthy_governor(request):
    """
    Ensure the governor allows test HTTP requests through without getting throttled
    by background GPU/CPU spikes on the host developer machine during test runs,
    except for governor-specific unit tests in test_governor.py.
    """
    if "test_governor" in request.node.nodeid:
        yield
        return

    with patch("app.main.governor.wait_until_healthy", return_value=(True, None)), \
         patch("app.main.governor.is_throttled", return_value=(False, None)):
        yield
