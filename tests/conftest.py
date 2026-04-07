"""Pytest configuration and fixtures for Kyromesh SDK tests."""

import pytest
import os


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "integration: mark test as an integration test requiring local docker-compose stack"
    )


@pytest.fixture(scope="session")
def integration_config():
    """Provide integration test configuration from environment variables."""
    return {
        "api_url": os.getenv("KYROMESH_API_URL", "http://localhost:8080"),
        "api_key": os.getenv("KYROMESH_API_KEY", "km_live_test_integration"),
        "timeout": int(os.getenv("KYROMESH_INTEGRATION_TIMEOUT", "60")),
        "poll_interval": int(os.getenv("KYROMESH_POLL_INTERVAL", "2")),
    }


def pytest_collection_modifyitems(config, items):
    """Mark integration tests based on file location."""
    for item in items:
        if "test_integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
