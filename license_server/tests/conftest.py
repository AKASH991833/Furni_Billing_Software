import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.rate_limit import rate_limiter


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Clear the in-memory rate limiter so tests don't affect each other."""
    rate_limiter._calls.clear()
    yield
    rate_limiter._calls.clear()