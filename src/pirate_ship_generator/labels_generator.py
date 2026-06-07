"""Generate base shipping labels."""

import random
from datetime import datetime, timedelta, timezone
from typing import Dict, Any

import pandas as pd

# Domain logic: Carrier-specific service classes
SERVICE_CLASSES = {
    "USPS": ("USPS_PRIORITY", "USPS_STANDARD"),
    "UPS": ("UPS_2ND_DAY", "UPS_GROUND"),
    "FEDEX": ("FEDEX_2_DAY", "FEDEX_NORMAL"),
    "DHL_ECOM": ("DHL_ECOM_EXPRESS", "DHL_ECOM_FLEX"),
}

# Domain logic: Service class SLA in days
SLA_DAYS = {
    "USPS_PRIORITY": 3,
    "USPS_STANDARD": 5,
    "UPS_2ND_DAY": 2,
    "UPS_GROUND": 7,
    "FEDEX_2_DAY": 2,
    "FEDEX_NORMAL": 7,
    "DHL_ECOM_EXPRESS": 3,
    "DHL_ECOM_FLEX": 5,
}

# Domain logic: Void timing rules
VOID_TIMING = {
    "fraud_days_min": 2,
    "fraud_days_max": 5,
}

# Domain logic: Field change rules
FIELD_CHANGES = {
    "num_changes_min": 1,
    "num_changes_max": 2,
    "hours_between_min": 1,
    "hours_between_max": 24,
}

# Domain logic: Weight fraud detection and evasion
WEIGHT_FRAUD = {
    "system_limit_oz": 1120,  # Max weight allowed by system
    "fraud_min_oz": 1000,     # Min weight when evading
    "fraud_max_oz": 1120,     # Max weight when evading
}

# Domain logic: Insurance edge cases
INSURANCE = {
    "min_value_cents": 5000,      # $50 minimum for insured labels
    "max_value_cents": 50000,     # $500 maximum for insured labels
    "edge_case_proportion": 0.05, # 5% of insured labels have value = 0
}


def generate_base_labels(config: Dict[str, Any]) -> pd.DataFrame:
    """
    Generate base shipping labels.

    Args:
        config: Configuration dict with:
            - num_labels: number of labels to generate
            - carrier_distribution: dict of carrier -> proportion
            - service_class_express_proportion: proportion that are express
            - insurance_proportion: proportion that are insured
            - date_range_days: days back to generate labels
            - random_seed: seed for reproducibility

    Returns:
        Pandas DataFrame with one row per label (12 columns)
    """
    random.seed(config.random_seed)

    labels = []
    num_labels = config.num_labels
    carrier_dist = config.carrier_distribution
    express_prop = config.service_class_express_proportion
    insurance_prop = config.insurance_proportion
    date_range = config.date_range_days

    now = datetime.now(timezone.utc)

    for _ in range(num_labels):
        # Generate timestamps
        days_back = random.randint(0, date_range)
        created_at = now - timedelta(days=days_back)

        # Select carrier and service class
        carrier = _select_carrier(carrier_dist)
        service_class = _select_service_class(carrier, express_prop)

        # Generate weight and apply weight fraud
        weight = _generate_weight()
        if weight > WEIGHT_FRAUD["system_limit_oz"]:
            # Weight exceeds system limit; adjust to evade detection
            weight = random.randint(
                WEIGHT_FRAUD["fraud_min_oz"],
                WEIGHT_FRAUD["fraud_max_oz"]
            )

        # Generate insurance and apply edge case
        declared_value = _generate_insurance(insurance_prop)
        if declared_value is not None and random.random() < INSURANCE["edge_case_proportion"]:
            # Insured label has zero value (inconsistency)
            declared_value = 0

        # Create label
        label = {
            "label_id": _generate_label_id(),
            "customer_id": _generate_customer_id(),
            "carrier": carrier,
            "service_class": service_class,
            "origin_zip": _generate_zip_code(),
            "dest_zip": _generate_zip_code(),
            "weight_oz": weight,
            "declared_value_cents": declared_value,
            "label_created_at": created_at,
            "carrier_promised_delivery_at": _calculate_promised_delivery_date(created_at, service_class),
            "voided_at": None,
            "last_updated_at": created_at,
        }
        labels.append(label)

    return pd.DataFrame(labels)


def apply_cdc_changes(df: pd.DataFrame, config: Dict[str, Any]) -> pd.DataFrame:
    """
    Apply CDC changes to base labels (30% of labels get updates/voiding).

    Adds multiple rows per label:
    - 30% of labels marked for changes
    - Of changed: 30% get voided (1 void row, then stop)
    - Of changed: 70% get field updates (1-2 update rows)

    Args:
        df: Base labels DataFrame (1 row per label)
        config: Configuration dict with:
            - changed_labels_proportion: fraction marked for changes (0.30)
            - changed_voided_proportion: of changed, fraction voided (0.30)
            - voided_fraud_proportion: of voided, fraction 2-5 days late (0.10)

    Returns:
        Expanded DataFrame with multiple rows per changed label
    """
    changed_prop = config.changed_labels_proportion
    voided_prop = config.changed_voided_proportion
    fraud_prop = config.voided_fraud_proportion
    carrier_dist = config.carrier_distribution
    express_prop = config.service_class_express_proportion

    rows = df.to_dict("records")
    new_rows = []

    # Sample 30% of label IDs for changes
    label_ids = df["label_id"].unique()
    num_to_change = max(1, int(len(label_ids) * changed_prop))
    labels_to_change = set(random.sample(list(label_ids), num_to_change))

    for label_dict in rows:
        label_id = label_dict["label_id"]
        # Keep original row
        new_rows.append(label_dict.copy())

        if label_id in labels_to_change:
            # Decide: void (30%) or field changes (70%)?
            if random.random() < voided_prop:
                # This label gets voided
                void_row = label_dict.copy()

                void_at = _get_void_timestamp(label_dict["label_created_at"], fraud_prop)
                void_row["voided_at"] = void_at
                void_row["last_updated_at"] = void_at

                new_rows.append(void_row)
                # STOP - no more updates for voided labels
            else:
                # This label gets field changes (1-2 changes per label)
                # Each change adds a new row with updated state (CDC-style)
                num_changes = random.randint(
                    FIELD_CHANGES["num_changes_min"],
                    FIELD_CHANGES["num_changes_max"]
                )

                current_timestamp = label_dict["last_updated_at"]
                latest_state = label_dict.copy()  # Track latest state for chaining changes

                for _ in range(num_changes):
                    # Create new row based on latest state (not original)
                    updated_row = latest_state.copy()

                    # Change a field: carrier (50%) or service_class (50%)
                    if random.random() < 0.5:
                        # Change carrier, update service_class to match
                        new_carrier = _select_carrier(carrier_dist, current_carrier=updated_row["carrier"])
                        updated_row["carrier"] = new_carrier
                        updated_row["service_class"] = _select_service_class(
                            new_carrier, express_prop
                        )
                    else:
                        # Change service_class only
                        updated_row["service_class"] = _select_service_class(
                            updated_row["carrier"], express_prop, current_class=updated_row["service_class"]
                        )

                    # Advance timestamp (must be later than previous)
                    hours_later = random.randint(
                        FIELD_CHANGES["hours_between_min"],
                        FIELD_CHANGES["hours_between_max"]
                    )
                    current_timestamp = current_timestamp + timedelta(hours=hours_later)
                    updated_row["last_updated_at"] = current_timestamp

                    # Add new row to result
                    new_rows.append(updated_row)

                    # Update latest state for next change (if any)
                    latest_state = updated_row

    return pd.DataFrame(new_rows)


# Private helper functions


def _generate_label_id() -> str:
    """Generate a label ID in format lbl_<24 hex chars>."""
    hex_chars = "".join(f"{random.randint(0, 15):x}" for _ in range(24))
    return f"lbl_{hex_chars}"


def _generate_customer_id() -> str:
    """Generate a customer ID in format cust_<12 hex chars>."""
    hex_chars = "".join(f"{random.randint(0, 15):x}" for _ in range(12))
    return f"cust_{hex_chars}"


def _select_carrier(carrier_distribution: Dict[str, float], current_carrier: str | None = None) -> str:
    """
    Select a carrier based on distribution proportions.

    Args:
        carrier_distribution: Dict of carrier -> proportion (e.g., {'USPS': 0.50, ...})
        current_carrier: Carrier name to exclude from selection (optional)

    Returns:
        Selected carrier name (different from current_carrier if provided)
    """
    carriers = list(carrier_distribution.keys())
    weights = list(carrier_distribution.values())

    # Filter out current carrier if provided
    if current_carrier and current_carrier in carriers:
        idx = carriers.index(current_carrier)
        carriers.pop(idx)
        weights.pop(idx)

    return random.choices(carriers, weights=weights, k=1)[0]


def _select_service_class(carrier: str, express_proportion: float, current_class: str | None = None) -> str:
    """
    Select a service class based on carrier and express proportion.

    Args:
        carrier: Carrier name (USPS, UPS, FEDEX, DHL_ECOM)
        express_proportion: Proportion that are express (vs standard)
        current_class: Service class to exclude from selection (optional)

    Returns:
        Service class name for the carrier (different from current_class if provided)
    """
    express_class, standard_class = SERVICE_CLASSES[carrier]

    # If current class provided, pick the other one
    if current_class:
        if current_class == express_class:
            return standard_class
        else:
            return express_class

    # Otherwise use proportion-based selection
    return express_class if random.random() < express_proportion else standard_class


def _generate_zip_code() -> str:
    """Generate a 5-digit ZIP code (00001-99999)."""
    return f"{random.randint(1, 99999):05d}"


def _generate_weight() -> int:
    """Generate a weight in ounces (1-1180)."""
    return random.randint(1, 1180)


def _generate_insurance(insurance_proportion: float) -> int | None:
    """
    Generate insurance value in cents.

    Args:
        insurance_proportion: Proportion of labels that are insured

    Returns:
        Insurance value in cents ($50-$500), or None if uninsured
    """
    if random.random() < insurance_proportion:
        # Insured: $50-$500 in cents
        return random.randint(5000, 50000)
    return None


def _calculate_promised_delivery_date(
    created_at: datetime, service_class: str
) -> datetime:
    """
    Calculate promised delivery date based on service class SLA.

    Args:
        created_at: Label creation timestamp
        service_class: Service class name

    Returns:
        Promised delivery datetime
    """
    days = SLA_DAYS[service_class]
    return created_at + timedelta(days=days)


def _get_void_timestamp(created_at: datetime, fraud_prop: float) -> datetime:
    """
    Calculate void timestamp based on fraud likelihood.

    Timing logic:
    - Immediate void: within 1 hour of creation
    - Fraud void: 2-5 days after creation

    Args:
        created_at: Label creation timestamp
        fraud_prop: Proportion of voids that are fraud (2-5 days later)

    Returns:
        Void timestamp
    """
    if random.random() < fraud_prop:
        # Fraud void: 2-5 days later
        days_to_void = random.randint(
            VOID_TIMING["fraud_days_min"],
            VOID_TIMING["fraud_days_max"]
        )
    else:
        # Immediate void: within 1 hour
        minutes_to_void = random.randint(1, 60)
        days_to_void = minutes_to_void / (24 * 60)

    return created_at + timedelta(days=days_to_void)
