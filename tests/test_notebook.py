"""Tests for Databricks notebook wrapper."""

import pytest
from pathlib import Path


class TestNotebookExists:
    """Test that notebook file exists and is properly structured."""

    def test_notebook_file_exists(self):
        """Notebook file should exist."""
        notebook_path = Path("/Users/felix/projects/parcel-shipping-case-study/notebooks/pirate_ship_generator.py")
        assert notebook_path.exists(), f"Notebook file not found at {notebook_path}"

    def test_notebook_is_readable(self):
        """Notebook file should be readable."""
        notebook_path = Path("/Users/felix/projects/parcel-shipping-case-study/notebooks/pirate_ship_generator.py")
        with open(notebook_path, "r") as f:
            content = f.read()
        assert len(content) > 0, "Notebook file is empty"

    def test_notebook_has_databricks_header(self):
        """Notebook should have Databricks notebook source header."""
        notebook_path = Path("/Users/felix/projects/parcel-shipping-case-study/notebooks/pirate_ship_generator.py")
        with open(notebook_path, "r") as f:
            content = f.read()
        assert "# Databricks notebook source" in content


class TestNotebookDocumentation:
    """Test that notebook is properly documented."""

    def test_notebook_has_docstring(self):
        """Notebook should have a docstring."""
        notebook_path = Path("/Users/felix/projects/parcel-shipping-case-study/notebooks/pirate_ship_generator.py")
        with open(notebook_path, "r") as f:
            content = f.read()
        assert '"""' in content, "Notebook should have docstring"

    def test_notebook_describes_purpose(self):
        """Notebook docstring should describe its purpose."""
        notebook_path = Path("/Users/felix/projects/parcel-shipping-case-study/notebooks/pirate_ship_generator.py")
        with open(notebook_path, "r") as f:
            content = f.read()
        assert "synthetic" in content.lower(), "Should describe synthetic data generation"
        assert "parcel" in content.lower() or "shipping" in content.lower(), "Should mention parcel/shipping"

    def test_notebook_mentions_generated_tables(self):
        """Notebook should document which tables it generates."""
        notebook_path = Path("/Users/felix/projects/parcel-shipping-case-study/notebooks/pirate_ship_generator.py")
        with open(notebook_path, "r") as f:
            content = f.read()
        assert "raw.labels" in content, "Should mention raw.labels table"
        assert "raw.tracking_events" in content, "Should mention raw.tracking_events table"


class TestNotebookImports:
    """Test that notebook imports required modules."""

    def test_notebook_imports_pandas(self):
        """Notebook should import pandas."""
        notebook_path = Path("/Users/felix/projects/parcel-shipping-case-study/notebooks/pirate_ship_generator.py")
        with open(notebook_path, "r") as f:
            content = f.read()
        assert "import pandas" in content

    def test_notebook_imports_spark(self):
        """Notebook should import PySpark."""
        notebook_path = Path("/Users/felix/projects/parcel-shipping-case-study/notebooks/pirate_ship_generator.py")
        with open(notebook_path, "r") as f:
            content = f.read()
        assert "SparkSession" in content

    def test_notebook_imports_generators(self):
        """Notebook should import generator functions."""
        notebook_path = Path("/Users/felix/projects/parcel-shipping-case-study/notebooks/pirate_ship_generator.py")
        with open(notebook_path, "r") as f:
            content = f.read()
        assert "generate_base_labels" in content
        assert "apply_cdc_changes" in content
        assert "generate_events" in content

    def test_notebook_imports_writer(self):
        """Notebook should import writer functions."""
        notebook_path = Path("/Users/felix/projects/parcel-shipping-case-study/notebooks/pirate_ship_generator.py")
        with open(notebook_path, "r") as f:
            content = f.read()
        assert "write_all" in content
        assert "validate_written_data" in content


class TestNotebookWidgets:
    """Test that notebook defines proper widgets."""

    def test_notebook_defines_config_path_widget(self):
        """Notebook should define config_path widget."""
        notebook_path = Path("/Users/felix/projects/parcel-shipping-case-study/notebooks/pirate_ship_generator.py")
        with open(notebook_path, "r") as f:
            content = f.read()
        assert "config_path" in content
        assert "dbutils.widgets" in content

    def test_notebook_defines_labels_path_widget(self):
        """Notebook should define labels_path widget."""
        notebook_path = Path("/Users/felix/projects/parcel-shipping-case-study/notebooks/pirate_ship_generator.py")
        with open(notebook_path, "r") as f:
            content = f.read()
        assert "labels_path" in content

    def test_notebook_defines_events_path_widget(self):
        """Notebook should define events_path widget."""
        notebook_path = Path("/Users/felix/projects/parcel-shipping-case-study/notebooks/pirate_ship_generator.py")
        with open(notebook_path, "r") as f:
            content = f.read()
        assert "events_path" in content


class TestNotebookWorkflow:
    """Test that notebook implements full workflow."""

    def test_notebook_loads_config(self):
        """Notebook should load configuration."""
        notebook_path = Path("/Users/felix/projects/parcel-shipping-case-study/notebooks/pirate_ship_generator.py")
        with open(notebook_path, "r") as f:
            content = f.read()
        assert "load_config" in content

    def test_notebook_generates_labels(self):
        """Notebook should call generate_base_labels."""
        notebook_path = Path("/Users/felix/projects/parcel-shipping-case-study/notebooks/pirate_ship_generator.py")
        with open(notebook_path, "r") as f:
            content = f.read()
        assert "generate_base_labels" in content

    def test_notebook_applies_cdc_changes(self):
        """Notebook should apply CDC changes."""
        notebook_path = Path("/Users/felix/projects/parcel-shipping-case-study/notebooks/pirate_ship_generator.py")
        with open(notebook_path, "r") as f:
            content = f.read()
        assert "apply_cdc_changes" in content

    def test_notebook_generates_events(self):
        """Notebook should generate events."""
        notebook_path = Path("/Users/felix/projects/parcel-shipping-case-study/notebooks/pirate_ship_generator.py")
        with open(notebook_path, "r") as f:
            content = f.read()
        assert "generate_events" in content

    def test_notebook_writes_data(self):
        """Notebook should write data to Delta tables."""
        notebook_path = Path("/Users/felix/projects/parcel-shipping-case-study/notebooks/pirate_ship_generator.py")
        with open(notebook_path, "r") as f:
            content = f.read()
        assert "write_all" in content

    def test_notebook_validates_data(self):
        """Notebook should validate written data."""
        notebook_path = Path("/Users/felix/projects/parcel-shipping-case-study/notebooks/pirate_ship_generator.py")
        with open(notebook_path, "r") as f:
            content = f.read()
        assert "validate_written_data" in content


class TestNotebookLogging:
    """Test that notebook has comprehensive logging."""

    def test_notebook_uses_logging(self):
        """Notebook should use logging module."""
        notebook_path = Path("/Users/felix/projects/parcel-shipping-case-study/notebooks/pirate_ship_generator.py")
        with open(notebook_path, "r") as f:
            content = f.read()
        assert "logging" in content
        assert "logger" in content

    def test_notebook_logs_major_steps(self):
        """Notebook should log each major step."""
        notebook_path = Path("/Users/felix/projects/parcel-shipping-case-study/notebooks/pirate_ship_generator.py")
        with open(notebook_path, "r") as f:
            content = f.read()
        # Check for logged steps
        assert "Loading configuration" in content or "load_config" in content
        assert "base labels" in content
        assert "CDC" in content
        assert "events" in content

    def test_notebook_logs_results(self):
        """Notebook should log results."""
        notebook_path = Path("/Users/felix/projects/parcel-shipping-case-study/notebooks/pirate_ship_generator.py")
        with open(notebook_path, "r") as f:
            content = f.read()
        assert "COMPLETE" in content or "Complete" in content


class TestNotebookDisplays:
    """Test that notebook displays sample data."""

    def test_notebook_displays_data(self):
        """Notebook should display sample data."""
        notebook_path = Path("/Users/felix/projects/parcel-shipping-case-study/notebooks/pirate_ship_generator.py")
        with open(notebook_path, "r") as f:
            content = f.read()
        assert "display(" in content, "Should display sample data using display()"

    def test_notebook_displays_labels(self):
        """Notebook should display sample labels."""
        notebook_path = Path("/Users/felix/projects/parcel-shipping-case-study/notebooks/pirate_ship_generator.py")
        with open(notebook_path, "r") as f:
            content = f.read()
        assert "labels" in content.lower()

    def test_notebook_displays_events(self):
        """Notebook should display sample events."""
        notebook_path = Path("/Users/felix/projects/parcel-shipping-case-study/notebooks/pirate_ship_generator.py")
        with open(notebook_path, "r") as f:
            content = f.read()
        assert "events" in content.lower()


class TestNotebookErrorHandling:
    """Test that notebook has error handling."""

    def test_notebook_has_try_except(self):
        """Notebook should have try-except blocks."""
        notebook_path = Path("/Users/felix/projects/parcel-shipping-case-study/notebooks/pirate_ship_generator.py")
        with open(notebook_path, "r") as f:
            content = f.read()
        assert "try:" in content
        assert "except" in content

    def test_notebook_checks_config_exists(self):
        """Notebook should check if config file exists."""
        notebook_path = Path("/Users/felix/projects/parcel-shipping-case-study/notebooks/pirate_ship_generator.py")
        with open(notebook_path, "r") as f:
            content = f.read()
        assert "exists" in content or "FileNotFoundError" in content
