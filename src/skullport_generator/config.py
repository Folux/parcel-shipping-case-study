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

    def validate(self) -> None:
        """
        Validate all configuration values.

        Raises:
            ValueError: If any config value is invalid
        """
        errors = []

        # Validate proportions are between 0 and 1
        proportion_fields = [
            "changed_labels_proportion", "changed_voided_proportion",
            "voided_fraud_proportion", "late_arriving_updates_proportion",
            "service_class_express_proportion", "insurance_proportion",
            "insurance_0_value_proportion", "late_delivery_proportion",
            "event_out_of_order_proportion", "event_duplicates_proportion",
            "event_late_arrivals_proportion", "event_missing_fields_proportion",
            "event_malformed_proportion", "timezone_weirdness_proportion",
            "voided_label_tracking_proportion", "incomplete_labels_proportion",
        ]

        for field in proportion_fields:
            value = getattr(self, field)
            if not (0 <= value <= 1):
                errors.append(f"{field} must be between 0 and 1, got {value}")

        # Validate positive integers
        if self.num_labels <= 0:
            errors.append(f"num_labels must be positive, got {self.num_labels}")
        if self.date_range_days <= 0:
            errors.append(f"date_range_days must be positive, got {self.date_range_days}")
        if self.event_late_arrival_min_days <= 0:
            errors.append(f"event_late_arrival_min_days must be positive, got {self.event_late_arrival_min_days}")
        if self.event_late_arrival_max_days <= 0:
            errors.append(f"event_late_arrival_max_days must be positive, got {self.event_late_arrival_max_days}")

        # Validate late arrival days
        if self.event_late_arrival_min_days > self.event_late_arrival_max_days:
            errors.append(
                f"event_late_arrival_min_days ({self.event_late_arrival_min_days}) "
                f"must be <= event_late_arrival_max_days ({self.event_late_arrival_max_days})"
            )

        # Validate carrier distribution
        if not self.carrier_distribution:
            errors.append("carrier_distribution cannot be empty")
        else:
            total = sum(self.carrier_distribution.values())
            if not (0.99 <= total <= 1.01):  # Allow small floating point errors
                errors.append(f"carrier_distribution values must sum to 1.0, got {total}")

        # Validate dicts are not empty
        if not self.event_schema_drift_by_carrier:
            errors.append("event_schema_drift_by_carrier cannot be empty")
        if not self.event_timezone_format_by_carrier:
            errors.append("event_timezone_format_by_carrier cannot be empty")

        # Validate strings are not empty
        if not self.catalog_name:
            errors.append("catalog_name cannot be empty")
        if not self.schema_name:
            errors.append("schema_name cannot be empty")

        if errors:
            error_msg = "Configuration validation failed:\n" + "\n".join(f"  • {e}" for e in errors)
            raise ValueError(error_msg)


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

    # Check for key mismatches against the dataclass for a clear error message
    config_keys = set(config_dict.keys())
    expected_keys = set(GeneratorConfig.__dataclass_fields__.keys())
    extra = config_keys - expected_keys
    missing = expected_keys - config_keys
    if extra or missing:
        problems = []
        if missing:
            problems.append(f"missing keys: {sorted(missing)}")
        if extra:
            problems.append(f"unexpected keys: {sorted(extra)}")
        raise ValueError(f"Config does not match GeneratorConfig — {'; '.join(problems)}")

    config = GeneratorConfig(**config_dict)
    config.validate()
    return config
