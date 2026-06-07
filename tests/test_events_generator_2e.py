"""Tests for events generator Step 2e: Apply Missing Fields."""

import pytest
from datetime import datetime, timezone

from pirate_ship_generator.events_generator import (
    _apply_missing_fields,
    EventRow,
)


def _create_test_event(event_id: str, event_code: str | None = "0300", event_type: str | None = None) -> EventRow:
    """Helper to create a test event."""
    return {
        "event_id": event_id,
        "label_id": "lbl_test",
        "carrier": "USPS",
        "event_code": event_code,
        "event_type": event_type,
        "event_at": "2026-06-06T10:00:00-05:00",
        "event_received_at": datetime(2026, 6, 6, 10, 0, 0, tzinfo=timezone.utc),
        "location_zip": "12345",
        "raw_payload": None,
    }


class TestApplyMissingFields:
    """Test missing fields event generation."""

    def test_no_missing_fields_with_zero_proportion(self):
        """With 0 probability, no fields should be removed."""
        events = [_create_test_event("ev_1", "0300", None)]
        result = _apply_missing_fields(events, missing_fields_proportion=0.0)

        # Fields should be unchanged
        assert result[0]["event_code"] == "0300"
        assert result[0]["event_type"] is None

    def test_missing_fields_sets_both_null(self):
        """Missing fields should set both event_code and event_type to NULL."""
        events = [_create_test_event("ev_1", "0300", None)]
        result = _apply_missing_fields(events, missing_fields_proportion=1.0)

        # Both should be NULL
        assert result[0]["event_code"] is None
        assert result[0]["event_type"] is None

    def test_missing_fields_preserves_other_fields(self):
        """Missing fields should only affect code/type."""
        events = [_create_test_event("ev_1", "0300", None)]
        result = _apply_missing_fields(events, missing_fields_proportion=1.0)

        # All other fields should be unchanged
        assert result[0]["event_id"] == events[0]["event_id"]
        assert result[0]["label_id"] == events[0]["label_id"]
        assert result[0]["carrier"] == events[0]["carrier"]
        assert result[0]["event_at"] == events[0]["event_at"]
        assert result[0]["event_received_at"] == events[0]["event_received_at"]
        assert result[0]["location_zip"] == events[0]["location_zip"]
        assert result[0]["raw_payload"] == events[0]["raw_payload"]

    def test_multiple_events_with_missing_fields(self):
        """Multiple events can have missing fields."""
        events = [
            _create_test_event("ev_1", "0300", None),
            _create_test_event("ev_2", "0301", None),
            _create_test_event("ev_3", "0310", None),
        ]

        result = _apply_missing_fields(events, missing_fields_proportion=1.0)

        # All should have NULL code and type
        for event in result:
            assert event["event_code"] is None
            assert event["event_type"] is None

    def test_missing_fields_proportion_respected(self):
        """Missing fields proportion should control how many events are affected."""
        events = [_create_test_event(f"ev_{i}", "0300", None) for i in range(100)]

        # With 0.5 probability, should get ~50 with missing fields, ~50 unchanged
        result = _apply_missing_fields(events, missing_fields_proportion=0.5)

        missing_count = sum(1 for e in result if e["event_code"] is None and e["event_type"] is None)

        # Should be approximately 50 (within reasonable variance)
        assert 30 < missing_count < 70, f"Got {missing_count} with missing fields, expected ~50"

    def test_missing_fields_with_ups_event(self):
        """Missing fields should work with UPS events (event_type populated)."""
        events = [_create_test_event("ev_1", None, "PICKUP")]
        result = _apply_missing_fields(events, missing_fields_proportion=1.0)

        # Both should be NULL
        assert result[0]["event_code"] is None
        assert result[0]["event_type"] is None

    def test_missing_fields_with_both_populated(self):
        """Missing fields should NULL both fields even if both were populated."""
        events = [_create_test_event("ev_1", "0300", "PICKUP")]  # Both populated (unusual)
        result = _apply_missing_fields(events, missing_fields_proportion=1.0)

        # Both should be NULL
        assert result[0]["event_code"] is None
        assert result[0]["event_type"] is None

    def test_empty_events_list(self):
        """Empty events list should return empty list."""
        result = _apply_missing_fields([], missing_fields_proportion=0.5)
        assert len(result) == 0

    def test_single_event_missing_fields(self):
        """Single event can have missing fields."""
        events = [_create_test_event("ev_1", "0300", None)]
        result = _apply_missing_fields(events, missing_fields_proportion=1.0)

        assert result[0]["event_code"] is None
        assert result[0]["event_type"] is None

    def test_list_length_unchanged(self):
        """Missing fields should not change the number of events."""
        events = [_create_test_event(f"ev_{i}", "0300", None) for i in range(10)]
        result = _apply_missing_fields(events, missing_fields_proportion=0.5)

        assert len(result) == len(events)

    def test_partial_missing_fields(self):
        """With partial proportion, some events should have fields, others not."""
        events = [_create_test_event(f"ev_{i}", "0300", None) for i in range(20)]
        result = _apply_missing_fields(events, missing_fields_proportion=0.5)

        with_fields = sum(1 for e in result if e["event_code"] is not None or e["event_type"] is not None)
        missing = sum(1 for e in result if e["event_code"] is None and e["event_type"] is None)

        # Should have a mix
        assert with_fields > 0, "Should have some events with fields"
        assert missing > 0, "Should have some events with missing fields"
