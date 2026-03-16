"""Placeholder tests for Pass 1 — real tests will be added in Pass 2 and Pass 3."""

from app.main import app  # noqa: F401 — verifies the app module imports cleanly


def test_app_imports():
    """Verify the FastAPI app can be imported without errors."""
    assert app is not None


def test_health(client=None):
    """Placeholder health test — full HTTP tests added in Pass 3."""
    assert True
