"""Tests for events generator Step 2c: Apply Late Arrivals."""

import pytest
from datetime import datetime, timezone, timedelta

from skullport_generator.events_generator import (
    _apply_late_arrivals,
    EventRow,
)


def _create_test_event(
    event_id: str, received_at: datetime | None = None
) -> EventRow:
    """Helper to create a test event."""
    if received_at is None:
        received_at = datetime(2026, 6, 6, 10, 0, 0, tzinfo=timezone.utc)

    return {
        "event_id": event_id,
        "label_id": "lbl_test",
        "carrier": "USPS",
        "event_code": "0300",
        "event_type": None,
        "event_at": "2026-06-06T10:00:00-05:00",
        "event_received_at": received_at,
        "location_zip": "12345",
        "raw_payload": None,
    }


class TestApplyLateArrivals:
    """Test late arrival event generation."""

    def test_no_late_arrivals_with_zero_proportion(self):
        """With 0 probability, no events should be delayed."""
        base_time = datetime(2026, 6, 6, 10, 0, 0, tzinfo=timezone.utc)
        events = [_create_test_event("ev_1", base_time)]

        result = _apply_late_arrivals(events, late_arrival_proportion=0.0, min_days=2, max_days=8)

        # Event received_at should be unchanged
        assert result[0]["event_received_at"] == base_time

    def test_late_arrival_delay_in_range(self):
        """Late arrivals should be delayed by 2-8 days."""
        base_time = datetime(2026, 6, 6, 10, 0, 0, tzinfo=timezone.utc)
        events = [_create_test_event("ev_1", base_time)]

        # Collect delays across multiple runs
        delays = []
        for _ in range(50):
            result = _apply_late_arrivals(events.copy(), late_arrival_proportion=1.0, min_days=2, max_days=8)
            if result[0]["event_received_at"] != base_time:
                delay = result[0]["event_received_at"] - base_time
                delays.append(delay.days)

        # Should have at least one late arrival with high probability
        assert len(delays) > 0

        # All delays should be 2-8 days
        assert all(2 <= d <= 8 for d in delays), f"Got delays: {delays}"

    def test_late_arrival_preserves_other_fields(self):
        """Late arrivals should only modify event_received_at."""
        base_time = datetime(2026, 6, 6, 10, 0, 0, tzinfo=timezone.utc)
        events = [_create_test_event("ev_1", base_time)]

        result = _apply_late_arrivals(events, late_arrival_proportion=1.0, min_days=2, max_days=8)

        # All fields except event_received_at should be unchanged
        assert result[0]["event_id"] == events[0]["event_id"]
        assert result[0]["label_id"] == events[0]["label_id"]
        assert result[0]["carrier"] == events[0]["carrier"]
        assert result[0]["event_code"] == events[0]["event_code"]
        assert result[0]["event_type"] == events[0]["event_type"]
        assert result[0]["event_at"] == events[0]["event_at"]
        assert result[0]["location_zip"] == events[0]["location_zip"]
        assert result[0]["raw_payload"] == events[0]["raw_payload"]

        # Only event_received_at should differ
        assert result[0]["event_received_at"] > events[0]["event_received_at"]

    def test_multiple_events_with_late_arrivals(self):
        """Multiple events can have late arrivals."""
        base_time = datetime(2026, 6, 6, 10, 0, 0, tzinfo=timezone.utc)
        events = [
            _create_test_event("ev_1", base_time),
            _create_test_event("ev_2", base_time),
            _create_test_event("ev_3", base_time),
        ]

        result = _apply_late_arrivals(events, late_arrival_proportion=1.0, min_days=2, max_days=8)

        # All should be delayed
        for event in result:
            assert event["event_received_at"] > base_time

    def test_late_arrival_proportion_respected(self):
        """Late arrival proportion should control how many events are delayed."""
        base_time = datetime(2026, 6, 6, 10, 0, 0, tzinfo=timezone.utc)
        events = [_create_test_event(f"ev_{i}", base_time) for i in range(100)]

        # With 0.5 probability, should get ~50 delayed, ~50 unchanged
        result = _apply_late_arrivals(events, late_arrival_proportion=0.5, min_days=2, max_days=8)

        delayed_count = sum(1 for e in result if e["event_received_at"] > base_time)

        # Should be approximately 50 delayed (within reasonable variance)
        assert 30 < delayed_count < 70, f"Got {delayed_count} delayed, expected ~50"

    def test_zero_delay_not_considered_late(self):
        """Events with 0 days delay should not count as late arrivals."""
        base_time = datetime(2026, 6, 6, 10, 0, 0, tzinfo=timezone.utc)
        events = [_create_test_event("ev_1", base_time)]

        result = _apply_late_arrivals(events, late_arrival_proportion=1.0, min_days=1, max_days=1)

        # With min_days=1, should always be at least 1 day late
        assert result[0]["event_received_at"] >= base_time + timedelta(days=1)

    def test_received_at_always_after_or_equal_original(self):
        """event_received_at should never be before the original."""
        base_time = datetime(2026, 6, 6, 10, 0, 0, tzinfo=timezone.utc)
        events = [_create_test_event(f"ev_{i}", base_time) for i in range(50)]

        result = _apply_late_arrivals(events, late_arrival_proportion=1.0, min_days=2, max_days=8)

        for original, modified in zip(events, result):
            assert modified["event_received_at"] >= original["event_received_at"]

    def test_empty_events_list(self):
        """Empty events list should return empty list."""
        result = _apply_late_arrivals([], late_arrival_proportion=0.5, min_days=2, max_days=8)
        assert len(result) == 0

    def test_single_event_late_arrival(self):
        """Single event can be delayed."""
        base_time = datetime(2026, 6, 6, 10, 0, 0, tzinfo=timezone.utc)
        events = [_create_test_event("ev_1", base_time)]

        result = _apply_late_arrivals(events, late_arrival_proportion=1.0, min_days=3, max_days=5)

        delay = result[0]["event_received_at"] - base_time
        assert 3 <= delay.days <= 5

    def test_custom_min_max_days(self):
        """Custom min/max days should be respected."""
        base_time = datetime(2026, 6, 6, 10, 0, 0, tzinfo=timezone.utc)
        events = [_create_test_event("ev_1", base_time)]

        result = _apply_late_arrivals(events, late_arrival_proportion=1.0, min_days=10, max_days=15)

        delay = result[0]["event_received_at"] - base_time
        assert 10 <= delay.days <= 15

    def test_list_length_unchanged(self):
        """Late arrivals should not change the number of events."""
        base_time = datetime(2026, 6, 6, 10, 0, 0, tzinfo=timezone.utc)
        events = [_create_test_event(f"ev_{i}", base_time) for i in range(10)]

        result = _apply_late_arrivals(events, late_arrival_proportion=0.5, min_days=2, max_days=8)

        assert len(result) == len(events)
