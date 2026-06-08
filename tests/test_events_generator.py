"""Business-logic tests for the events generator — one focused check per behavior.

Covers the event model (id, carrier code/type schema drift, SLA timing, sequence)
and each injected data-quality "weirdness": out-of-order events, duplicates,
late arrivals, missing fields, malformed/timezone-weird timestamps, carrier
timestamp formats, and voided-label tracking.
"""

import random
from collections import Counter
from datetime import datetime, timedelta, timezone

import pandas as pd

from skullport_generator.events_generator import (
    _generate_event_id,
    _get_event_code_and_type,
    _get_event_sla_proportion,
    _get_tracking_events,
    _format_event_at,
    _corrupt_timestamp,
    _shuffle_out_of_order_events,
    _apply_duplicates,
    _apply_late_arrivals,
    _apply_missing_fields,
    _apply_timestamp_issues,
    _apply_voided_label_tracking,
    EVENT_SEQUENCE,
    US_TIMEZONE_OFFSETS,
)

UTC = timezone.utc


def _event(event_id="ev_1", *, label_id="lbl_test", carrier="USPS",
           event_code="0300", event_type=None,
           event_at="2026-06-06T10:30:00-05:00", received_at=None):
    return {
        "event_id": event_id,
        "label_id": label_id,
        "carrier": carrier,
        "event_code": event_code,
        "event_type": event_type,
        "event_at": event_at,
        "event_received_at": received_at or datetime(2026, 6, 6, 10, 30, 0, tzinfo=UTC),
        "location_zip": "12345",
        "raw_payload": None,
    }


def _labels_df():
    """Two voided labels (lbl_1 USPS, lbl_3 FEDEX) and two active ones."""
    return pd.DataFrame({
        "label_id": ["lbl_1", "lbl_2", "lbl_3", "lbl_4"],
        "carrier": ["USPS", "UPS", "FEDEX", "DHL_ECOM"],
        "voided_at": [
            datetime(2026, 6, 5, 10, 0, 0, tzinfo=UTC),
            None,
            datetime(2026, 6, 4, 14, 30, 0, tzinfo=UTC),
            None,
        ],
        "label_created_at": [
            datetime(2026, 6, 5, 9, 0, 0, tzinfo=UTC),
            datetime(2026, 6, 6, 8, 0, 0, tzinfo=UTC),
            datetime(2026, 6, 4, 13, 0, 0, tzinfo=UTC),
            datetime(2026, 6, 6, 7, 0, 0, tzinfo=UTC),
        ],
    })


# --- Event model -----------------------------------------------------------

def test_event_id_is_32_char_hex_and_unique():
    ids = {_generate_event_id() for _ in range(100)}
    assert len(ids) == 100
    sample = next(iter(ids))
    assert len(sample) == 32 and all(c in "0123456789abcdef" for c in sample)


def test_carrier_code_type_schema_drift():
    # USPS & DHL emit numeric/short codes; UPS & FEDEX emit type strings.
    assert _get_event_code_and_type("USPS", "delivered") == ("0320", None)
    assert _get_event_code_and_type("DHL_ECOM", "delivered") == ("DL", None)
    assert _get_event_code_and_type("UPS", "delivered") == (None, "DELIVERED")
    assert _get_event_code_and_type("FEDEX", "picked_up") == (None, "PICKUP")
    assert _get_event_code_and_type("USPS", "not_a_real_event") == (None, None)


def test_event_timing_is_ascending_fraction_of_sla():
    proportions = [_get_event_sla_proportion(e) for e in EVENT_SEQUENCE]
    assert proportions == sorted(proportions)
    assert proportions[0] == 0.15 and proportions[-1] == 0.95


# --- Event sequence per label ----------------------------------------------

def test_immediately_voided_label_has_no_events():
    created = datetime(2026, 6, 1, 10, 0, 0, tzinfo=UTC)
    label = {"label_id": "l", "label_created_at": created,
             "voided_at": created + timedelta(minutes=30)}
    assert _get_tracking_events(label)["num_events"] == 0


def test_late_voided_label_has_zero_to_three_prefix_events():
    created = datetime(2026, 6, 1, 10, 0, 0, tzinfo=UTC)
    label = {"label_id": "l", "label_created_at": created,
             "voided_at": created + timedelta(days=3)}
    for _ in range(30):
        result = _get_tracking_events(label)
        assert 0 <= result["num_events"] <= 3
        # Whatever events exist are a prefix of the standard sequence.
        assert result["sequence"] == EVENT_SEQUENCE[: result["num_events"]]


def test_non_voided_labels_mostly_complete_with_some_incomplete():
    random.seed(42)  # ~1% incomplete rate → seed so the small sample is stable
    created = datetime(2026, 6, 1, 10, 0, 0, tzinfo=UTC)
    label = {"label_id": "l", "label_created_at": created, "voided_at": None}
    counts = [_get_tracking_events(label)["num_events"] for _ in range(200)]
    assert 0.85 < counts.count(4) / 200 <= 1.0   # mostly the full 4-event sequence
    assert counts.count(2) > 0                    # some stuck-at-in_transit labels


# --- Timestamps: carrier formats + corruption ------------------------------

def test_carrier_timestamp_formats():
    dt = datetime(2026, 6, 6, 10, 30, 0, tzinfo=UTC)
    usps = _format_event_at(dt, "USPS")
    assert "05:30:00" in usps and "-05:00" in usps           # offset, time converted
    assert _format_event_at(dt, "UPS") == "2026-06-06T10:30:00Z"   # UTC Z
    assert _format_event_at(dt, "FEDEX") == "2026-06-06T10:30:00"  # plain, implied UTC
    _, abbr = _format_event_at(dt, "DHL_ECOM").split(" ")          # tz abbreviation
    assert abbr in US_TIMEZONE_OFFSETS


def test_dhl_timestamp_round_trips_to_utc():
    """The generator bug we fixed: DHL local time must reconstruct the UTC instant."""
    dt = datetime(2026, 6, 6, 10, 30, 0, tzinfo=UTC)
    local, abbr = _format_event_at(dt, "DHL_ECOM").split(" ")
    parsed = datetime.strptime(local, "%Y-%m-%dT%H:%M:%S")
    recovered = (parsed - timedelta(hours=US_TIMEZONE_OFFSETS[abbr])).replace(tzinfo=UTC)
    assert recovered == dt


def test_corrupt_timestamp_is_unparseable_and_strips_timezone():
    out = _corrupt_timestamp("2026-06-06T10:30:00-05:00")
    assert out in {"20260606T103000", "2026-06-06", "2026/06/06T10:30:00"}
    assert "-05:00" not in out


# --- Data-quality weirdnesses ----------------------------------------------

def test_out_of_order_shuffle_reorders_but_preserves_events():
    random.seed(0)
    events = [_event(f"ev_{i}", event_at=f"2026-06-0{i}T10:00:00-05:00") for i in range(1, 5)]
    # A single event is never shuffled.
    assert _shuffle_out_of_order_events([events[0]], 1.0) == [events[0]]
    # Shuffling reorders at least sometimes...
    original = tuple(e["event_id"] for e in events)
    assert any(
        tuple(e["event_id"] for e in _shuffle_out_of_order_events(events.copy(), 1.0)) != original
        for _ in range(20)
    )
    # ...without losing or changing the timestamps.
    shuffled = _shuffle_out_of_order_events(events.copy(), 1.0)
    assert sorted(e["event_at"] for e in shuffled) == sorted(e["event_at"] for e in events)


def test_duplicates_append_copies_with_a_new_event_id():
    result = _apply_duplicates([_event("ev_1")], duplicate_proportion=1.0)
    assert len(result) == 2
    original, dup = result
    assert original["event_id"] == "ev_1" and dup["event_id"] != "ev_1"
    for field in ("label_id", "carrier", "event_code", "event_at", "event_received_at"):
        assert dup[field] == original[field]


def test_late_arrivals_delay_only_received_at():
    base = datetime(2026, 6, 6, 10, 0, 0, tzinfo=UTC)
    ev = _event("ev_1", received_at=base)
    result = _apply_late_arrivals([ev], late_arrival_proportion=1.0, min_days=2, max_days=8)
    assert 2 <= (result[0]["event_received_at"] - base).days <= 8
    assert result[0]["event_at"] == ev["event_at"]  # the event time itself is untouched


def test_missing_fields_nulls_both_code_and_type():
    result = _apply_missing_fields(
        [_event("ev_1", event_code="0300", event_type=None)], missing_fields_proportion=1.0
    )
    assert result[0]["event_code"] is None and result[0]["event_type"] is None


def test_timestamp_issues_apply_malformed_or_carrier_weirdness():
    # Malformed → an unparseable corrupted format.
    malformed = _apply_timestamp_issues(
        [_event("ev_1", event_at="2026-06-06T10:30:00")],
        malformed_proportion=1.0, weirdness_proportion=0.0,
    )
    assert malformed[0]["event_at"] in {"20260606T103000", "2026-06-06", "2026/06/06T10:30:00"}
    # Timezone weirdness → reformatted into the carrier's own style (USPS offset).
    weird = _apply_timestamp_issues(
        [_event("ev_1", carrier="USPS", event_at="2026-06-06T10:30:00")],
        malformed_proportion=0.0, weirdness_proportion=1.0,
    )
    assert "-05:00" in weird[0]["event_at"]


def test_voided_label_tracking_adds_1_to_2_events_only_to_voided_labels():
    result = _apply_voided_label_tracking([], _labels_df(), voided_tracking_proportion=1.0)
    assert result  # events were added
    assert all(e["label_id"] in {"lbl_1", "lbl_3"} for e in result)  # only voided labels
    per_label = Counter(e["label_id"] for e in result)
    assert all(1 <= n <= 2 for n in per_label.values())


def test_voided_tracking_adds_nothing_when_no_labels_are_voided():
    labels = pd.DataFrame({
        "label_id": ["a"], "carrier": ["USPS"], "voided_at": [None],
        "label_created_at": [datetime(2026, 6, 5, 9, 0, 0, tzinfo=UTC)],
    })
    result = _apply_voided_label_tracking([_event("ev_1", label_id="a")], labels, 1.0)
    assert len(result) == 1 and result[0]["event_id"] == "ev_1"
