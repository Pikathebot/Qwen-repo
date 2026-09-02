import pytest
from unittest.mock import patch
from app.main import governor


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
