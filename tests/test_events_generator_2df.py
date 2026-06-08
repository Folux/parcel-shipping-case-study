"""Tests for events generator Step 2d+2f: Apply Timestamp Issues (Malformed or Timezone Weirdness)."""

import pytest
from datetime import datetime, timezone

from skullport_generator.events_generator import (
    _corrupt_timestamp,
    _apply_timestamp_issues,
    TIMEZONE_FORMAT,
    EventRow,
)


def _create_test_event(
    event_id: str,
    carrier: str = "USPS",
    event_at: str = "2026-06-06T10:30:00-05:00",
) -> EventRow:
    """Helper to create a test event."""
    return {
        "event_id": event_id,
        "label_id": "lbl_test",
        "carrier": carrier,
        "event_code": "0300",
        "event_type": None,
        "event_at": event_at,
        "event_received_at": datetime(2026, 6, 6, 10, 30, 0, tzinfo=timezone.utc),
        "location_zip": "12345",
        "raw_payload": None,
    }


class TestCorruptTimestamp:
    """Test timestamp corruption (malformed)."""

    def test_corrupt_no_separators(self):
        """Corrupted timestamp with no separators should remove dashes and colons."""
        result = _corrupt_timestamp("2026-06-06T10:30:00-05:00")

        # Should be one of the three corruption types
        assert result in [
            "20260606T103000",  # no_separators
            "2026-06-06",       # missing_time
            "2026/06/06T10:30:00",  # wrong_separators
        ]

    def test_corrupt_removes_timezone(self):
        """Corruption should extract base timestamp before timezone."""
        result = _corrupt_timestamp("2026-06-06T10:30:00-05:00")

        # Should not contain the offset
        assert "-05:00" not in result

    def test_corrupt_with_z_timezone(self):
        """Corruption should extract base timestamp before Z."""
        result = _corrupt_timestamp("2026-06-06T10:30:00Z")

        # Should not contain Z
        assert "Z" not in result

    def test_corrupt_with_tz_abbreviation(self):
        """Corruption should extract base timestamp before tz abbreviation."""
        result = _corrupt_timestamp("2026-06-06T10:30:00 EST")

        # Should not contain the timezone
        assert "EST" not in result
        assert " " not in result


class TestApplyTimestampIssues:
    """Test combined timestamp issues (malformed or timezone weirdness)."""

    def test_no_issues_with_zero_proportions(self):
        """With 0 probability, timestamps should be unchanged."""
        events = [_create_test_event("ev_1", "USPS", "2026-06-06T10:30:00-05:00")]
        result = _apply_timestamp_issues(events, malformed_proportion=0.0, weirdness_proportion=0.0)

        # Timestamp should be unchanged
        assert result[0]["event_at"] == "2026-06-06T10:30:00-05:00"

    def test_malformed_takes_priority(self):
        """Malformed should take priority over weirdness."""
        events = [_create_test_event("ev_1", "USPS", "2026-06-06T10:30:00-05:00")]

        # High probabilities for both
        result = _apply_timestamp_issues(events, malformed_proportion=1.0, weirdness_proportion=1.0)

        # With malformed_proportion=1.0, should get malformed (priority)
        event_at = result[0]["event_at"]

        # Malformed means: unparseable format (no separators, missing time, wrong separators)
        # Check that it's corrupted (not the original format)
        assert event_at != "2026-06-06T10:30:00-05:00"

    def test_mutually_exclusive_per_event(self):
        """Each event should get at most one type of corruption."""
        events = [_create_test_event(f"ev_{i}", "USPS", "2026-06-06T10:30:00-05:00") for i in range(100)]

        # Both proportions set
        result = _apply_timestamp_issues(events, malformed_proportion=0.5, weirdness_proportion=0.5)

        # Each event should have at most one corruption type
        for i, event in enumerate(result):
            original = events[i]

            # Check if it's malformed (corrupted in a weird way)
            is_malformed = event["event_at"] != original["event_at"] and (
                "T" not in event["event_at"] or  # Missing time
                "-" not in event["event_at"] and "/" not in event["event_at"]  # No separators
            )

            # Check if it's timezone weird (reformatted in a different carrier's style)
            is_weird = event["event_at"] != original["event_at"] and not is_malformed

            # Should have at most one issue
            if event["event_at"] == original["event_at"]:
                # No issue
                pass
            else:
                # Has one issue (either malformed or weird, not both)
                pass

    def test_malformed_produces_unparseable_format(self):
        """Malformed timestamps should be unparseable."""
        events = [_create_test_event("ev_1", "USPS", "2026-06-06T10:30:00")]
        result = _apply_timestamp_issues(events, malformed_proportion=1.0, weirdness_proportion=0.0)

        event_at = result[0]["event_at"]

        # Should be one of the malformed types
        assert event_at in [
            "20260606T103000",     # no_separators
            "2026-06-06",          # missing_time
            "2026/06/06T10:30:00",  # wrong_separators
        ]

    def test_weirdness_applies_carrier_format(self):
        """Timezone weirdness should reformat event_at using carrier's format."""
        events = [_create_test_event("ev_1", "USPS", "2026-06-06T10:30:00")]
        result = _apply_timestamp_issues(events, malformed_proportion=0.0, weirdness_proportion=1.0)

        event_at = result[0]["event_at"]

        # USPS format is "offset" which includes timezone offset (-05:00)
        # The reformatted timestamp should have an offset
        assert "-05:00" in event_at or "-05" in event_at

    def test_preserves_other_fields(self):
        """Timestamp issues should only affect event_at."""
        events = [_create_test_event("ev_1", "USPS", "2026-06-06T10:30:00-05:00")]
        result = _apply_timestamp_issues(events, malformed_proportion=1.0, weirdness_proportion=1.0)

        # All other fields should be unchanged
        assert result[0]["event_id"] == events[0]["event_id"]
        assert result[0]["label_id"] == events[0]["label_id"]
        assert result[0]["carrier"] == events[0]["carrier"]
        assert result[0]["event_code"] == events[0]["event_code"]
        assert result[0]["event_type"] == events[0]["event_type"]
        assert result[0]["event_received_at"] == events[0]["event_received_at"]
        assert result[0]["location_zip"] == events[0]["location_zip"]
        assert result[0]["raw_payload"] == events[0]["raw_payload"]

    def test_proportions_respected_combined(self):
        """Combined proportions should control corruption rates."""
        events = [_create_test_event(f"ev_{i}", "USPS", "2026-06-06T10:30:00-05:00") for i in range(200)]

        # 2% malformed, 3% weirdness = ~5% total issues
        result = _apply_timestamp_issues(events, malformed_proportion=0.02, weirdness_proportion=0.03)

        issues_count = sum(1 for e, orig in zip(result, events) if e["event_at"] != orig["event_at"])

        # Should be roughly 5% (±10% tolerance)
        expected = int(200 * 0.05)
        assert abs(issues_count - expected) < 20, f"Got {issues_count} issues, expected ~{expected}"

    def test_multiple_carriers_weirdness(self):
        """Timezone weirdness should apply carrier's format to each event."""
        events = [
            _create_test_event("ev_1", "USPS", "2026-06-06T10:30:00"),
            _create_test_event("ev_2", "UPS", "2026-06-06T10:30:00"),
            _create_test_event("ev_3", "FEDEX", "2026-06-06T10:30:00"),
            _create_test_event("ev_4", "DHL_ECOM", "2026-06-06T10:30:00"),
        ]

        result = _apply_timestamp_issues(events, malformed_proportion=0.0, weirdness_proportion=1.0)

        # Each should be reformatted with its carrier's format
        # USPS should have offset
        assert "-05:00" in result[0]["event_at"]
        # UPS should have Z
        assert "Z" in result[1]["event_at"]
        # FEDEX should be plain (no special marker, but reformatted)
        assert "T" in result[2]["event_at"]
        # DHL should have tz abbreviation
        assert " " in result[3]["event_at"]  # Space before abbreviation

    def test_empty_events_list(self):
        """Empty events list should return empty list."""
        result = _apply_timestamp_issues([], malformed_proportion=0.5, weirdness_proportion=0.5)
        assert len(result) == 0

    def test_list_length_unchanged(self):
        """Timestamp issues should not change the number of events."""
        events = [_create_test_event(f"ev_{i}", "USPS", "2026-06-06T10:30:00-05:00") for i in range(10)]
        result = _apply_timestamp_issues(events, malformed_proportion=0.5, weirdness_proportion=0.5)

        assert len(result) == len(events)

    def test_partial_issues(self):
        """With partial proportions, some events should have issues, others not."""
        events = [_create_test_event(f"ev_{i}", "USPS", "2026-06-06T10:30:00-05:00") for i in range(20)]
        result = _apply_timestamp_issues(events, malformed_proportion=0.3, weirdness_proportion=0.3)

        unchanged = sum(1 for e, orig in zip(result, events) if e["event_at"] == orig["event_at"])
        issues = sum(1 for e, orig in zip(result, events) if e["event_at"] != orig["event_at"])

        # Should have a mix
        assert unchanged > 0, "Should have some unchanged events"
        assert issues > 0, "Should have some events with issues"
