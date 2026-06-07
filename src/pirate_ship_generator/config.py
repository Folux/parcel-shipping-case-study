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
    event_duplicates_proportion: float
    event_late_arrivals_proportion: float
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

    return GeneratorConfig(**config_dict)
