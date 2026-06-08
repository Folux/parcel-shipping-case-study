"""Tests for the main orchestration entry point.

We only unit-test what's meaningful without a Spark session and a live catalog:
graceful error handling (main returns an error dict instead of raising). The
happy path is exercised end-to-end when the generator runs on Databricks.
"""

import os
import tempfile

from skullport_generator.main import main


def test_missing_config_returns_error_dict():
    """A missing config file yields a clean error dict, not an exception."""
    result = main("/nonexistent/path/config.yaml")

    assert result["status"] == "error"
    assert result["error_type"] == "FileNotFoundError"
    assert result["message"]


def test_invalid_config_returns_error_dict():
    """A malformed (empty) config is caught and reported, not crashed on."""
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
        f.write("")  # empty → invalid config
        path = f.name
    try:
        result = main(path)
        assert result["status"] == "error"
        assert result["error_type"] == "ValueError"
    finally:
        os.unlink(path)
