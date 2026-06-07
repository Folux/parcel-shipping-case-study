"""Generate synthetic tracking events."""

import random
import uuid
from datetime import datetime, timedelta, timezone
from typing import TypedDict

import pandas as pd
from dateutil import parser as dateutil_parser


class LabelRow(TypedDict):
    """Label data from the labels DataFrame."""

    label_id: str
    carrier: str
    voided_at: datetime | None
    label_created_at: datetime
    carrier_promised_delivery_at: datetime


class TrackingEventSequence(TypedDict):
    """Tracking events for a label."""

    num_events: int
    sequence: list[str]


class EventRow(TypedDict):
    """A single tracking event row."""

    event_id: str
    label_id: str
    carrier: str
    event_code: str | None
    event_type: str | None
    event_at: str
    event_received_at: datetime
    location_zip: str | None
    raw_payload: str | None

# Domain logic: Event codes/types per carrier
EVENT_CODES = {
    "USPS": {
        "picked_up": "0300",
        "in_transit": "0301",
        "out_for_delivery": "0310",
        "delivered": "0320",
    },
    "UPS": {
        "picked_up": "PICKUP",
        "in_transit": "IN_TRANSIT",
        "out_for_delivery": "OUT_FOR_DELIVERY",
        "delivered": "DELIVERED",
    },
    "FEDEX": {
        "picked_up": "PICKUP",
        "in_transit": "IN_TRANSIT",
        "out_for_delivery": "OUT_FOR_DELIVERY",
        "delivered": "DELIVERED",
    },
    "DHL_ECOM": {
        "picked_up": "PU",
        "in_transit": "IT",
        "out_for_delivery": "OFD",
        "delivered": "DL",
    },
}

# Domain logic: Event timing as percentage of SLA window
EVENT_TIMING = {
    "picked_up": 0.15,           # 15% of SLA
    "in_transit": 0.40,          # 40% of SLA
    "out_for_delivery": 0.75,    # 75% of SLA
    "delivered": 0.95,           # 95% of SLA
}

# Standard 4-event sequence (all carriers follow same sequence)
EVENT_SEQUENCE = ["picked_up", "in_transit", "out_for_delivery", "delivered"]

# Domain logic: Event sequence decision rules
EVENT_SEQUENCE_RULES = {
    "immediately_voided_events": 0,        # Voided < 1 hour → 0 events
    "late_voided_min_events": 0,           # Voided 2-5 days → 0-3 events
    "late_voided_max_events": 3,
    "incomplete_events": 2,                # Incomplete → 2 events (picked_up, in_transit)
    "complete_events": 4,                  # Normal → 4 events (full sequence)
    "incomplete_labels_proportion": 0.01,  # 1% of non-voided labels stuck at in_transit
    "late_voided_event_proportion": 0.50,  # 50% of late-voided get events before voiding
}

# Domain logic: Event generation constants (not configurable)
EVENT_GENERATION = {
    "timestamp_randomness_hours": 2,  # ± hours of randomness in event timing
    "location_zip_null_proportion": 0.20,  # 20% of events have NULL location_zip
}

# Domain logic: Timezone formatting per carrier
TIMEZONE_FORMAT = {
    "USPS": "offset",      # ISO 8601 with offset (e.g., 2026-06-06T10:30:00-05:00)
    "UPS": "utc_z",        # ISO 8601 with Z (e.g., 2026-06-06T10:30:00Z)
    "FEDEX": "plain",      # ISO 8601 plain (e.g., 2026-06-06T10:30:00)
    "DHL_ECOM": "tz_abbr", # ISO 8601 with timezone abbreviation (e.g., 2026-06-06T10:30:00 EST)
}

# US timezone abbreviations for DHL events
US_TIMEZONE_ABBRS = ["EST", "CST", "MST", "PST", "EDT", "CDT", "MDT", "PDT"]


def generate_events(labels_df: pd.DataFrame, config: dict) -> list[EventRow]:
    """
    Generate synthetic tracking events for all labels.

    Generates realistic tracking event data including:
    - Event sequences based on label state (voided, incomplete, complete)
    - SLA-proportional event timing
    - Carrier-specific timestamp formatting
    - Data quality issues (duplicates, late arrivals, malformed timestamps, missing fields, etc.)
    - Voided label tracking (late scans after voiding)

    Args:
        labels_df: DataFrame with label data (from generate_base_labels + apply_cdc_changes)
        config: Config dict with random_seed and proportion settings

    Returns:
        List of EventRow dicts representing synthetic tracking events
    """
    random.seed(config["random_seed"])

    all_events = []

    # Group labels by label_id to get unique labels (ignore CDC rows)
    # We only generate events for the final state of each label
    unique_labels = labels_df.drop_duplicates(subset=["label_id"], keep="last")

    # Convert to list of dicts for easy iteration (one dict per row)
    labels_list = unique_labels.to_dict('records')

    for label_dict in labels_list:

        # Decide event sequence for this label
        tracking_event_sequence = _get_tracking_events(label_dict)

        # Generate events for this label
        label_events: list[EventRow] = []

        # Generate each tracking event in the sequence
        for event_name in tracking_event_sequence["sequence"]:
            # Calculate event timestamp based on SLA proportion
            sla_proportion = _get_event_sla_proportion(event_name)
            sla_days = (
                label_dict["carrier_promised_delivery_at"]
                - label_dict["label_created_at"]
            ).days

            # Base timestamp: label_created_at + (proportion * SLA)
            event_at = label_dict["label_created_at"] + timedelta(
                days=sla_proportion * sla_days
            )

            # Add randomness (± 2 hours)
            randomness_hours = random.randint(
                -EVENT_GENERATION["timestamp_randomness_hours"],
                EVENT_GENERATION["timestamp_randomness_hours"],
            )
            event_at = event_at + timedelta(hours=randomness_hours)

            # Get event code/type based on carrier
            event_code, event_type = _get_event_code_and_type(
                label_dict["carrier"], event_name
            )

            # Generate location ZIP (20% NULL)
            if random.random() < EVENT_GENERATION["location_zip_null_proportion"]:
                location_zip = None
            else:
                location_zip = _generate_zip_code()

            # Format event_at with carrier-specific timezone
            event_at_formatted = _format_event_at(event_at, label_dict["carrier"])

            # Create event row
            event: EventRow = {
                "event_id": _generate_event_id(),
                "label_id": label_dict["label_id"],
                "carrier": label_dict["carrier"],
                "event_code": event_code,
                "event_type": event_type,
                "event_at": event_at_formatted,  # Carrier-specific formatted string
                "event_received_at": event_at,  # Same as event_at (normal case)
                "location_zip": location_zip,
                "raw_payload": None,  # NULL for now
            }

            label_events.append(event)

        # Apply out-of-order shuffling
        label_events = _shuffle_out_of_order_events(
            label_events,
            config.get("event_out_of_order_proportion", EVENT_GENERATION["out_of_order_events_proportion"])
        )

        # Add this label's events to the all events list
        all_events.extend(label_events)

    # Apply duplicates to all events
    all_events = _apply_duplicates(
        all_events,
        config.get("event_duplicates_proportion", 0.04)
    )

    # Apply late arrivals to some events
    all_events = _apply_late_arrivals(
        all_events,
        config.get("event_late_arrivals_proportion", 0.075),
        config.get("event_late_arrival_min_days", 2),
        config.get("event_late_arrival_max_days", 8),
    )

    # Apply missing fields to some events
    all_events = _apply_missing_fields(
        all_events,
        config.get("event_missing_fields_proportion", 0.01),
    )

    # Apply timestamp issues (malformed or timezone weirdness, mutually exclusive per event)
    all_events = _apply_timestamp_issues(
        all_events,
        config.get("event_malformed_proportion", 0.01),
        config.get("timezone_weirdness_proportion", 0.03),
    )

    # Apply voided label tracking (add events to some voided labels)
    all_events = _apply_voided_label_tracking(
        all_events,
        labels_df,
        config.get("voided_label_tracking_proportion", 0.05),
    )

    return all_events


def _generate_event_id() -> str:
    """
    Generate a unique event ID in UUID-style hex format.

    Returns:
        Event ID string (e.g., "a1b2c3d4e5f6...")
    """
    return uuid.uuid4().hex


def _get_event_code_and_type(carrier: str, event_name: str) -> tuple[str | None, str | None]:
    """
    Get event code and type for a carrier and event.

    Returns code for USPS/DHL_ECOM carriers, type for UPS/FEDEX carriers.

    Args:
        carrier: Carrier name (USPS, UPS, FEDEX, DHL_ECOM)
        event_name: Event name (picked_up, in_transit, out_for_delivery, delivered)

    Returns:
        Tuple of (event_code, event_type) where one is the value and one is None
    """
    value = EVENT_CODES.get(carrier, {}).get(event_name)

    if carrier in ("USPS", "DHL_ECOM"):
        return (value, None)  # Code-based carrier
    elif carrier in ("UPS", "FEDEX"):
        return (None, value)  # Type-based carrier
    else:
        return (None, None)  # Unknown carrier


def _get_event_sla_proportion(event_name: str) -> float:
    """
    Get the SLA proportion for an event (timing within SLA window).

    Args:
        event_name: Event name (picked_up, in_transit, out_for_delivery, delivered)

    Returns:
        Proportion of SLA (0.15 for picked_up, 0.40 for in_transit, etc.)
    """
    return EVENT_TIMING.get(event_name, 0.0)


def _get_tracking_events(label_row: LabelRow) -> TrackingEventSequence:
    """
    Decide event sequence for a single label.

    Rules:
    - Voided < 1 hour: 0 events (carrier never scanned)
    - Voided 2-5 days: 0-3 events (50% get some events before voiding, 50% get none)
    - Not voided, 1% incomplete: 2 events (stuck at in_transit)
    - Not voided, 99% complete: 4 events (full sequence)

    Args:
        label_row: Dict with label data (label_id, voided_at, label_created_at)

    Returns:
        Dict with:
        - num_events: int (0-4)
        - sequence: list of event names
    """
    voided_at = label_row.get("voided_at")
    label_created_at = label_row.get("label_created_at")

    # Case 1: Label is voided
    if voided_at is not None:
        # Check if immediately voided (< 1 hour)
        time_delta_hours = (voided_at - label_created_at).total_seconds() / 3600

        if time_delta_hours <= 1:
            # Immediately voided: 0 events
            return {"num_events": 0, "sequence": []}
        else:
            # Late voided (2-5 days): 0-3 events depending on rule
            if random.random() < EVENT_SEQUENCE_RULES["late_voided_event_proportion"]:
                # 50%: get random 1-3 events before voiding
                num_events = random.randint(
                    EVENT_SEQUENCE_RULES["late_voided_min_events"] + 1,
                    EVENT_SEQUENCE_RULES["late_voided_max_events"],
                )
            else:
                # 50%: get 0 events
                num_events = EVENT_SEQUENCE_RULES["late_voided_min_events"]

            return {
                "num_events": num_events,
                "sequence": EVENT_SEQUENCE[:num_events],
            }

    # Case 2: Label is not voided
    else:
        # Check if 1% incomplete (stuck at in_transit)
        if random.random() < EVENT_SEQUENCE_RULES["incomplete_labels_proportion"]:
            return {
                "num_events": EVENT_SEQUENCE_RULES["incomplete_events"],
                "sequence": EVENT_SEQUENCE[
                    : EVENT_SEQUENCE_RULES["incomplete_events"]
                ],
            }
        else:
            # 99%: full sequence
            return {
                "num_events": EVENT_SEQUENCE_RULES["complete_events"],
                "sequence": EVENT_SEQUENCE,
            }


def _generate_zip_code() -> str:
    """Generate a random 5-digit ZIP code."""
    return f"{random.randint(1, 99999):05d}"


def _format_event_at(event_at: datetime, carrier: str) -> str:
    """
    Format event_at timestamp according to carrier-specific timezone format.

    Args:
        event_at: Datetime object (in UTC)
        carrier: Carrier name (USPS, UPS, FEDEX, DHL_ECOM)

    Returns:
        Formatted ISO 8601 string per carrier timezone format
    """
    format_type = TIMEZONE_FORMAT.get(carrier, "plain")

    if format_type == "offset":
        # USPS: ISO 8601 with offset (e.g., 2026-06-06T10:30:00-05:00)
        # Use a fixed offset for simplicity (EST = -05:00)
        offset_tz = timezone(timedelta(hours=-5))
        localized = event_at.astimezone(offset_tz)
        # Format: 2026-06-06T10:30:00-05:00
        return localized.strftime("%Y-%m-%dT%H:%M:%S%z")[:-2] + ":00"

    elif format_type == "utc_z":
        # UPS: ISO 8601 with Z (e.g., 2026-06-06T10:30:00Z)
        return event_at.strftime("%Y-%m-%dT%H:%M:%SZ")

    elif format_type == "plain":
        # FEDEX: ISO 8601 plain (e.g., 2026-06-06T10:30:00)
        return event_at.strftime("%Y-%m-%dT%H:%M:%S")

    elif format_type == "tz_abbr":
        # DHL_ECOM: ISO 8601 with timezone abbreviation (e.g., 2026-06-06T10:30:00 EST)
        tz_abbr = random.choice(US_TIMEZONE_ABBRS)
        return event_at.strftime("%Y-%m-%dT%H:%M:%S") + f" {tz_abbr}"

    else:
        # Default to plain format
        return event_at.strftime("%Y-%m-%dT%H:%M:%S")


def _shuffle_out_of_order_events(
    label_events: list[EventRow], shuffle_probability: float
) -> list[EventRow]:
    """
    Shuffle all event rows for a label into random order.

    For realistic late-arriving data: events may arrive out of chronological sequence.
    Example: [picked_up, in_transit, out_for_delivery, delivered]
    Becomes: [out_for_delivery, picked_up, delivered, in_transit]

    Args:
        label_events: List of events for a single label (in original order)
        shuffle_probability: Probability to shuffle this label (0-1)

    Returns:
        Label events, possibly shuffled into random order
    """
    # Only shuffle if 2+ events and random < probability
    if len(label_events) < 2 or random.random() > shuffle_probability:
        return label_events

    # Shuffle all events
    shuffled = label_events.copy()
    random.shuffle(shuffled)

    return shuffled


def _apply_duplicates(all_events: list[EventRow], duplicate_proportion: float) -> list[EventRow]:
    """
    Add duplicate event rows (same event, different event_id).

    For realistic data quality: some scans land twice in the raw feed.
    Example: [ev1, ev2, ev3] → [ev1, ev2_dup, ev2, ev3]

    Args:
        all_events: List of all event rows
        duplicate_proportion: Probability for each event to be duplicated (0-1)

    Returns:
        List of events with duplicates appended
    """
    duplicates_to_add = []

    for event in all_events:
        # Random chance to duplicate this event
        if random.random() < duplicate_proportion:
            # Create duplicate with new event_id, all other fields identical
            duplicate: EventRow = {
                "event_id": _generate_event_id(),  # New ID
                "label_id": event["label_id"],
                "carrier": event["carrier"],
                "event_code": event["event_code"],
                "event_type": event["event_type"],
                "event_at": event["event_at"],
                "event_received_at": event["event_received_at"],
                "location_zip": event["location_zip"],
                "raw_payload": event["raw_payload"],
            }
            duplicates_to_add.append(duplicate)

    # Append all duplicates to the events list
    return all_events + duplicates_to_add


def _apply_late_arrivals(
    all_events: list[EventRow],
    late_arrival_proportion: float,
    min_days: int,
    max_days: int,
) -> list[EventRow]:
    """
    Apply late arrivals to events (event_received_at much later than event_at).

    For realistic data quality: some carrier scans arrive days after the actual event.
    Example: event_at = June 5, event_received_at = June 8 (3 days late)

    Args:
        all_events: List of all event rows
        late_arrival_proportion: Probability for each event to be late (0-1)
        min_days: Minimum days late
        max_days: Maximum days late

    Returns:
        List of events with some event_received_at delayed
    """
    modified_events = []

    for event in all_events:
        # Random chance to make this event arrive late
        if random.random() < late_arrival_proportion:
            # Add random delay (min to max days)
            delay_days = random.randint(min_days, max_days)
            new_received_at = event["event_received_at"] + timedelta(days=delay_days)

            # Create modified event with delayed event_received_at
            modified_event: EventRow = {
                "event_id": event["event_id"],
                "label_id": event["label_id"],
                "carrier": event["carrier"],
                "event_code": event["event_code"],
                "event_type": event["event_type"],
                "event_at": event["event_at"],
                "event_received_at": new_received_at,  # Delayed
                "location_zip": event["location_zip"],
                "raw_payload": event["raw_payload"],
            }
            modified_events.append(modified_event)
        else:
            # Keep event as-is
            modified_events.append(event)

    return modified_events


def _apply_missing_fields(all_events: list[EventRow], missing_fields_proportion: float) -> list[EventRow]:
    """
    Apply missing fields to events (both event_code and event_type set to NULL).

    For realistic data quality: some carrier payloads have missing event identifiers.

    Args:
        all_events: List of all event rows
        missing_fields_proportion: Probability for each event to have missing fields (0-1)

    Returns:
        List of events with some missing code/type fields
    """
    modified_events = []

    for event in all_events:
        # Random chance to remove both code and type
        if random.random() < missing_fields_proportion:
            # Create modified event with NULL code and type
            modified_event: EventRow = {
                "event_id": event["event_id"],
                "label_id": event["label_id"],
                "carrier": event["carrier"],
                "event_code": None,  # Set to NULL
                "event_type": None,  # Set to NULL
                "event_at": event["event_at"],
                "event_received_at": event["event_received_at"],
                "location_zip": event["location_zip"],
                "raw_payload": event["raw_payload"],
            }
            modified_events.append(modified_event)
        else:
            # Keep event as-is
            modified_events.append(event)

    return modified_events


def _corrupt_timestamp(event_at: str) -> str:
    """
    Corrupt an ISO 8601 timestamp string in one of three ways.

    Corruption types:
    - No separators: 20260606T103000 (remove dashes and colons)
    - Missing time: 2026-06-06 (remove T and time portion)
    - Wrong separators: 2026/06/06T10:30:00 (replace dashes with slashes)

    Args:
        event_at: ISO 8601 timestamp string (with or without timezone info)

    Returns:
        Corrupted timestamp string
    """
    # Parse the timestamp using dateutil (handles all ISO 8601 variations)
    try:
        dt = dateutil_parser.isoparse(event_at)
    except (ValueError, TypeError):
        # Fallback: if parsing fails, try to extract base timestamp manually
        # This handles edge cases like timezone abbreviations
        base = event_at.split("-05")[0] if "-05" in event_at else event_at
        base = base.split("Z")[0] if "Z" in base else base
        base = base.split(" ")[0] if " " in base else base
        dt = dateutil_parser.parse(base)

    # Format base timestamp: YYYY-MM-DDTHH:MM:SS
    base_timestamp = dt.strftime("%Y-%m-%dT%H:%M:%S")

    # Choose corruption type randomly
    corruption_type = random.choice(["no_separators", "missing_time", "wrong_separators"])

    if corruption_type == "no_separators":
        # Remove all dashes and colons: 2026-06-06T10:30:00 → 20260606T103000
        return base_timestamp.replace("-", "").replace(":", "")

    elif corruption_type == "missing_time":
        # Keep only date part: 2026-06-06T10:30:00 → 2026-06-06
        return base_timestamp.split("T")[0]

    else:  # wrong_separators
        # Replace dashes with slashes: 2026-06-06T10:30:00 → 2026/06/06T10:30:00
        return base_timestamp.replace("-", "/")


def _apply_voided_label_tracking(
    all_events: list[EventRow],
    labels_df: pd.DataFrame,
    voided_tracking_proportion: float,
) -> list[EventRow]:
    """
    Add tracking events to voided labels (late carrier scans after voiding).

    For realistic data quality: some voided labels receive 1-2 events after being voided
    (carrier scanned the package, but the label was already cancelled).

    Args:
        all_events: List of all event rows
        labels_df: DataFrame with label data (to identify voided labels)
        voided_tracking_proportion: Probability for a voided label to get events (0-1)

    Returns:
        List of events with some added to voided labels
    """
    events_to_add = []

    # Get unique voided labels (keep="last" to get the final state of each label)
    unique_labels = labels_df.drop_duplicates(subset=["label_id"], keep="last")
    voided_labels = unique_labels[unique_labels["voided_at"].notna()]

    # For each voided label, potentially add 1-2 events
    for _, label_row in voided_labels.iterrows():
        # Random chance to add events to this voided label
        if random.random() < voided_tracking_proportion:
            # Add 1-2 events
            num_events_to_add = random.randint(1, 2)

            for _ in range(num_events_to_add):
                # Generate event similar to normal events but for voided label
                # Event timestamp should be after label was voided (late arrival)
                voided_at = label_row["voided_at"]
                event_at = voided_at + timedelta(hours=random.randint(1, 24))

                # Get event code/type based on carrier
                event_name = random.choice(EVENT_SEQUENCE)
                event_code, event_type = _get_event_code_and_type(
                    label_row["carrier"], event_name
                )

                # Generate location ZIP (20% NULL)
                if random.random() < EVENT_GENERATION["location_zip_null_proportion"]:
                    location_zip = None
                else:
                    location_zip = _generate_zip_code()

                # Format event_at with carrier-specific timezone
                event_at_formatted = _format_event_at(event_at, label_row["carrier"])

                # Create event row
                event: EventRow = {
                    "event_id": _generate_event_id(),
                    "label_id": label_row["label_id"],
                    "carrier": label_row["carrier"],
                    "event_code": event_code,
                    "event_type": event_type,
                    "event_at": event_at_formatted,
                    "event_received_at": event_at,
                    "location_zip": location_zip,
                    "raw_payload": None,
                }
                events_to_add.append(event)

    # Append voided label events to the events list
    return all_events + events_to_add


def _apply_timestamp_issues(
    all_events: list[EventRow],
    malformed_proportion: float,
    weirdness_proportion: float,
) -> list[EventRow]:
    """
    Apply timestamp data quality issues to events (malformed OR timezone weirdness).

    For each event, apply at most one type of issue:
    - Malformed timestamps (unparseable format) - corrupts event_at format
    - Timezone weirdness - reformats event_at using carrier's assigned timezone format

    These are mutually exclusive per event.

    Args:
        all_events: List of all event rows
        malformed_proportion: Probability for each event to have malformed timestamp (0-1)
        weirdness_proportion: Probability for each event to have timezone weirdness (0-1)

    Returns:
        List of events with some timestamp issues applied
    """
    modified_events = []

    for event in all_events:
        malformed_timestamp_roll = random.random()
        timezone_weirdness_roll = random.random()

        # Check if this event gets malformed (highest priority)
        if malformed_timestamp_roll < malformed_proportion:
            # Apply malformed timestamp corruption
            modified_event: EventRow = {
                "event_id": event["event_id"],
                "label_id": event["label_id"],
                "carrier": event["carrier"],
                "event_code": event["event_code"],
                "event_type": event["event_type"],
                "event_at": _corrupt_timestamp(event["event_at"]),  # Corrupted format
                "event_received_at": event["event_received_at"],
                "location_zip": event["location_zip"],
                "raw_payload": event["raw_payload"],
            }
            modified_events.append(modified_event)

        # Else check if this event gets timezone weirdness
        elif timezone_weirdness_roll < weirdness_proportion:
            # Reformat event_received_at using the carrier's assigned timezone format
            # and store the formatted string in event_at
            carrier = event["carrier"]
            reformatted_at = _format_event_at(event["event_received_at"], carrier)

            modified_event: EventRow = {
                "event_id": event["event_id"],
                "label_id": event["label_id"],
                "carrier": event["carrier"],
                "event_code": event["event_code"],
                "event_type": event["event_type"],
                "event_at": reformatted_at,  # Reformatted using carrier's timezone format
                "event_received_at": event["event_received_at"],
                "location_zip": event["location_zip"],
                "raw_payload": event["raw_payload"],
            }
            modified_events.append(modified_event)
        else:
            # Keep event as-is (no timestamp issues)
            modified_events.append(event)

    return modified_events


