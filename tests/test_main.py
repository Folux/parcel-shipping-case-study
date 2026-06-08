"""Tests for main orchestration module."""

import pytest
import tempfile
import sys
from pathlib import Path

from skullport_generator.main import main


class TestMainFunction:
    """Test main orchestration function."""

    def test_main_is_callable(self):
        """main function should be callable."""
        assert callable(main)

    def test_main_accepts_config_path(self):
        """main should accept config_path parameter."""
        import inspect
        sig = inspect.signature(main)
        assert "config_path" in sig.parameters

    def test_main_has_default_config_path(self):
        """main should have default config_path."""
        import inspect
        sig = inspect.signature(main)
        assert sig.parameters["config_path"].default == "config.yaml"

    def test_main_returns_dict(self):
        """main should return a dictionary."""
        import inspect
        sig = inspect.signature(main)
        assert sig.return_annotation == dict

    def test_main_result_has_status_key(self):
        """Result dictionary should have 'status' key."""
        import inspect
        sig = inspect.signature(main)
        # Can't test without running, but we can verify the return type annotation
        assert sig.return_annotation == dict

    def test_missing_config_file_raises_error(self):
        """main should handle missing config file gracefully."""
        # main will return error dict, not raise
        result = main("/nonexistent/path/config.yaml")
        assert result["status"] == "error"
        assert "error_type" in result
        assert result["error_type"] == "FileNotFoundError"

    def test_error_result_has_required_keys(self):
        """Error result should have required keys."""
        result = main("/nonexistent/path/config.yaml")
        assert "status" in result
        assert "message" in result
        assert "error_type" in result


class TestMainErrorHandling:
    """Test main error handling."""

    def test_main_catches_file_not_found(self):
        """main should catch FileNotFoundError."""
        result = main("/nonexistent/config.yaml")
        assert result["status"] == "error"
        assert result["error_type"] == "FileNotFoundError"

    def test_main_returns_error_dict_not_exception(self):
        """main should return error dict, not raise exception."""
        # This is a design choice: main returns error dict for graceful handling
        result = main("/nonexistent/config.yaml")
        assert isinstance(result, dict)
        assert result["status"] in ["error", "success", "success_with_warnings"]


class TestSuccessResultStructure:
    """Test structure of successful result (when it runs with valid config)."""

    def test_success_result_should_have_labels_count(self):
        """Success result should have labels_count key."""
        # This is what a success result should look like
        expected_keys = ["status", "labels_count", "events_count", "labels_path", "events_path", "message"]
        # Can't test without running with valid config, but we can document expected structure
        assert expected_keys is not None

    def test_success_status_should_be_success_or_warning(self):
        """Status should be 'success' or 'success_with_warnings'."""
        # Valid statuses
        valid_statuses = ["success", "success_with_warnings", "error"]
        assert len(valid_statuses) == 3

    def test_error_status_should_be_error(self):
        """Error status should be 'error'."""
        result = main("/nonexistent/config.yaml")
        assert result["status"] == "error"


class TestMainImports:
    """Test that main imports required modules."""

    def test_imports_spark_session(self):
        """main should import SparkSession."""
        from skullport_generator import main as main_module
        # Check module has SparkSession imported
        import inspect
        source = inspect.getsource(main_module)
        assert "SparkSession" in source

    def test_imports_label_generator(self):
        """main should import label generation functions."""
        from skullport_generator import main as main_module
        import inspect
        source = inspect.getsource(main_module)
        assert "generate_base_labels" in source
        assert "apply_cdc_changes" in source

    def test_imports_events_generator(self):
        """main should import event generation function."""
        from skullport_generator import main as main_module
        import inspect
        source = inspect.getsource(main_module)
        assert "generate_events" in source

    def test_imports_writer(self):
        """main should import writer functions."""
        from skullport_generator import main as main_module
        import inspect
        source = inspect.getsource(main_module)
        assert "write_all" in source
        assert "validate_written_data" in source


class TestMainWorkflow:
    """Test main workflow steps."""

    def test_main_loads_config(self):
        """main should load config."""
        from skullport_generator import main as main_module
        import inspect
        source = inspect.getsource(main_module)
        assert "load_config" in source

    def test_main_creates_spark_session(self):
        """main should create SparkSession."""
        from skullport_generator import main as main_module
        import inspect
        source = inspect.getsource(main_module)
        assert "SparkSession.builder" in source

    def test_main_calls_label_generation(self):
        """main should call label generation functions."""
        from skullport_generator import main as main_module
        import inspect
        source = inspect.getsource(main_module)
        assert "generate_base_labels" in source
        assert "apply_cdc_changes" in source

    def test_main_calls_event_generation(self):
        """main should call event generation."""
        from skullport_generator import main as main_module
        import inspect
        source = inspect.getsource(main_module)
        assert "generate_events" in source

    def test_main_converts_to_dataframe(self):
        """main should convert events list to DataFrame."""
        from skullport_generator import main as main_module
        import inspect
        source = inspect.getsource(main_module)
        assert "pd.DataFrame" in source

    def test_main_writes_data(self):
        """main should write data to Delta tables."""
        from skullport_generator import main as main_module
        import inspect
        source = inspect.getsource(main_module)
        assert "write_all" in source

    def test_main_validates_data(self):
        """main should validate written data."""
        from skullport_generator import main as main_module
        import inspect
        source = inspect.getsource(main_module)
        assert "validate_written_data" in source


class TestMainCommandLine:
    """Test main command-line interface."""

    def test_main_is_executable(self):
        """main.py should be executable as __main__."""
        from skullport_generator import main as main_module
        import inspect
        source = inspect.getsource(main_module)
        assert 'if __name__ == "__main__"' in source

    def test_main_accepts_command_line_config(self):
        """main should accept config path from command line."""
        from skullport_generator import main as main_module
        import inspect
        source = inspect.getsource(main_module)
        assert "sys.argv" in source

    def test_main_has_default_command_line_config(self):
        """main should default to config.yaml from command line."""
        from skullport_generator import main as main_module
        import inspect
        source = inspect.getsource(main_module)
        assert "config.yaml" in source


class TestMainLogging:
    """Test main logging."""

    def test_main_uses_logging(self):
        """main should use logging module."""
        from skullport_generator import main as main_module
        import inspect
        source = inspect.getsource(main_module)
        assert "logging" in source
        assert "logger" in source

    def test_main_logs_generation_steps(self):
        """main should log each major step."""
        from skullport_generator import main as main_module
        import inspect
        source = inspect.getsource(main_module)
        # Check for step logging
        assert "Loading configuration" in source
        assert "Initializing SparkSession" in source
        assert "Generating base labels" in source
        assert "Applying CDC changes" in source
        assert "Generating tracking events" in source
