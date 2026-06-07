"""Tests for events generator Step 2b: Apply Duplicates."""

import pytest
from datetime import datetime, timezone

from pirate_ship_generator.events_generator import (
    _apply_duplicates,
    EventRow,
)


def _create_test_event(event_id: str) -> EventRow:
    """Helper to create a test event."""
    return {
        "event_id": event_id,
        "label_id": "lbl_test",
        "carrier": "USPS",
        "event_code": "0300",
        "event_type": None,
        "event_at": "2026-06-06T10:00:00-05:00",
        "event_received_at": datetime(2026, 6, 6, 10, 0, 0, tzinfo=timezone.utc),
        "location_zip": "12345",
        "raw_payload": None,
    }


class TestApplyDuplicates:
    """Test duplicate event generation."""

    def test_no_duplicates_with_zero_proportion(self):
        """With 0 probability, no duplicates should be added."""
        events = [_create_test_event("ev_1"), _create_test_event("ev_2")]
        result = _apply_duplicates(events, duplicate_proportion=0.0)

        # Should have exactly the original events, no duplicates
        assert len(result) == 2
        assert result[0]["event_id"] == "ev_1"
        assert result[1]["event_id"] == "ev_2"

    def test_duplicates_have_same_fields_except_event_id(self):
        """Duplicates should have identical fields except event_id."""
        events = [_create_test_event("ev_1")]
        result = _apply_duplicates(events, duplicate_proportion=1.0)

        # Should have original + duplicate
        assert len(result) == 2

        original = result[0]
        duplicate = result[1]

        # All fields same except event_id
        assert original["event_id"] == "ev_1"
        assert duplicate["event_id"] != "ev_1"  # Different ID
        assert duplicate["label_id"] == original["label_id"]
        assert duplicate["carrier"] == original["carrier"]
        assert duplicate["event_code"] == original["event_code"]
        assert duplicate["event_type"] == original["event_type"]
        assert duplicate["event_at"] == original["event_at"]
        assert duplicate["event_received_at"] == original["event_received_at"]
        assert duplicate["location_zip"] == original["location_zip"]
        assert duplicate["raw_payload"] == original["raw_payload"]

    def test_duplicate_event_id_is_unique(self):
        """Duplicates should have unique event IDs (different from original)."""
        events = [_create_test_event("ev_1")]
        result = _apply_duplicates(events, duplicate_proportion=1.0)

        original_id = result[0]["event_id"]
        duplicate_id = result[1]["event_id"]

        assert original_id != duplicate_id

    def test_multiple_events_duplicated(self):
        """Multiple events can be duplicated."""
        events = [
            _create_test_event("ev_1"),
            _create_test_event("ev_2"),
            _create_test_event("ev_3"),
        ]
        result = _apply_duplicates(events, duplicate_proportion=1.0)

        # Should have 3 original + 3 duplicates
        assert len(result) == 6

        # First 3 are originals
        assert result[0]["event_id"] == "ev_1"
        assert result[1]["event_id"] == "ev_2"
        assert result[2]["event_id"] == "ev_3"

        # Last 3 are duplicates (same label_id, carrier, etc., but different event_id)
        assert result[3]["label_id"] == "lbl_test"
        assert result[4]["label_id"] == "lbl_test"
        assert result[5]["label_id"] == "lbl_test"

    def test_duplicate_proportion_respected(self):
        """Duplicate proportion should control how many duplicates are added."""
        # Generate many events to get statistical significance
        events = [_create_test_event(f"ev_{i}") for i in range(100)]

        # With 0.5 probability, should get ~100 original + ~50 duplicates = ~150 total
        result = _apply_duplicates(events, duplicate_proportion=0.5)

        # Check that we got roughly the expected number of duplicates
        original_count = len(events)
        duplicate_count = len(result) - len(events)

        # Should be approximately 50 duplicates (within reasonable variance)
        assert 30 < duplicate_count < 70, f"Got {duplicate_count} duplicates, expected ~50"

    def test_duplicates_appended_to_end(self):
        """Duplicates should be appended to the end of the list."""
        events = [
            _create_test_event("ev_1"),
            _create_test_event("ev_2"),
        ]
        result = _apply_duplicates(events, duplicate_proportion=1.0)

        # Originals should be first
        assert result[0]["event_id"] == "ev_1"
        assert result[1]["event_id"] == "ev_2"

        # Duplicates should be after
        assert len(result) == 4
        assert result[2]["label_id"] == "lbl_test"
        assert result[3]["label_id"] == "lbl_test"

    def test_null_fields_preserved_in_duplicates(self):
        """Duplicates should preserve NULL fields from original."""
        event = _create_test_event("ev_1")
        # Set some fields to None
        event["event_code"] = None
        event["location_zip"] = None

        result = _apply_duplicates([event], duplicate_proportion=1.0)

        duplicate = result[1]
        assert duplicate["event_code"] is None
        assert duplicate["location_zip"] is None

    def test_empty_events_list(self):
        """Empty events list should return empty list."""
        result = _apply_duplicates([], duplicate_proportion=0.5)
        assert len(result) == 0

    def test_duplicates_unique_event_ids(self):
        """Each duplicate should have a unique event_id."""
        events = [_create_test_event("ev_1")]
        result = _apply_duplicates(events, duplicate_proportion=1.0)

        event_ids = [e["event_id"] for e in result]
        assert len(event_ids) == len(set(event_ids)), "Duplicate event IDs found!"
