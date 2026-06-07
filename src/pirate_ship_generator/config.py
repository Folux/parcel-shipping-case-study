"""Configuration loading for the data generator."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

import yaml


@dataclass
class GeneratorConfig:
    """Configuration for synthetic data generator."""

    # Volume
    num_labels: int

    # Label generation proportions
    changed_labels_proportion: float
    changed_voided_proportion: float
    voided_fraud_proportion: float
    late_arriving_updates_proportion: float
    service_class_express_proportion: float
    insurance_proportion: float
    insurance_0_value_proportion: float

    # Event generation proportions
    late_delivery_proportion: float
    event_out_of_order_proportion: float
    event_duplicates_proportion: float
    event_late_arrivals_proportion: float
    event_late_arrival_min_days: int
    event_late_arrival_max_days: int
    event_missing_fields_proportion: float
    event_malformed_proportion: float
    timezone_weirdness_proportion: float
    voided_label_tracking_proportion: float
    incomplete_labels_proportion: float

    # Date range
    date_range_days: int

    # Carrier configuration
    carrier_distribution: Dict[str, float]
    event_schema_drift_by_carrier: Dict[str, str]
    event_timezone_format_by_carrier: Dict[str, str]

    # Databricks configuration
    catalog_name: str
    schema_name: str

    # Reproducibility
    random_seed: int


def load_config(config_path: str) -> GeneratorConfig:
    """
    Load configuration from YAML file into a dataclass.

    Args:
        config_path: Path to YAML config file

    Returns:
        GeneratorConfig dataclass instance

    Raises:
        FileNotFoundError: If config file not found
        ValueError: If config file is empty
    """
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(path, "r") as f:
        config_dict = yaml.safe_load(f)

    if config_dict is None:
        raise ValueError("Config file is empty")

    # DEBUG: Show what we're loading
    print("\n" + "=" * 70)
    print("DEBUG: CONFIG LOADING")
    print("=" * 70)
    print(f"Config path: {path.absolute()}")
    print(f"\nKeys in config file ({len(config_dict)} total):")
    for key in sorted(config_dict.keys()):
        print(f"  - {key}")

    # Show expected fields
    print(f"\nFields expected by GeneratorConfig ({len(GeneratorConfig.__dataclass_fields__)} total):")
    for field_name in sorted(GeneratorConfig.__dataclass_fields__.keys()):
        print(f"  - {field_name}")

    # Find mismatches
    config_keys = set(config_dict.keys())
    expected_keys = set(GeneratorConfig.__dataclass_fields__.keys())

    extra_in_config = config_keys - expected_keys
    missing_in_config = expected_keys - config_keys

    if extra_in_config:
        print(f"\n⚠️  EXTRA keys in config (not expected by class):")
        for key in sorted(extra_in_config):
            print(f"  - {key}")

    if missing_in_config:
        print(f"\n⚠️  MISSING keys in config (expected by class):")
        for key in sorted(missing_in_config):
            print(f"  - {key}")

    if not extra_in_config and not missing_in_config:
        print(f"\n✓ All keys match!")

    print("=" * 70 + "\n")

    return GeneratorConfig(**config_dict)
