"""Tests for configuration loading."""

import pytest
import tempfile
from pathlib import Path

from skullport_generator.config import load_config, GeneratorConfig


class TestLoadConfig:
    """Test load_config function."""

    def test_load_default_config(self):
        """load_config should load config.yaml and return GeneratorConfig."""
        config = load_config("config.yaml")
        assert isinstance(config, GeneratorConfig)
        assert config.num_labels == 5000
        assert config.random_seed == 42
        assert config.catalog_name == "skullport"

    def test_config_type_hints(self):
        """GeneratorConfig fields should have correct types."""
        config = load_config("config.yaml")
        assert isinstance(config.num_labels, int)
        assert isinstance(config.random_seed, int)
        assert isinstance(config.catalog_name, str)
        assert isinstance(config.carrier_distribution, dict)
        assert isinstance(config.changed_labels_proportion, float)

    def test_load_nonexistent_file(self):
        """load_config should raise FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError):
            load_config("nonexistent.yaml")

    def test_load_empty_file(self):
        """load_config should raise ValueError for empty file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("")
            temp_path = f.name

        try:
            with pytest.raises(ValueError, match="empty"):
                load_config(temp_path)
        finally:
            Path(temp_path).unlink()
