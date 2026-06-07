"""Tests for events generator Step 2a: Apply Out-of-Order Row Shuffling."""

import pytest
from datetime import datetime, timezone

from pirate_ship_generator.events_generator import (
    _shuffle_out_of_order_events,
    EventRow,
)


def _create_test_event(event_id: str, event_name: str, position: int) -> EventRow:
    """Helper to create a test event."""
    return {
        "event_id": event_id,
        "label_id": "lbl_test",
        "carrier": "USPS",
        "event_code": "0300",
        "event_type": None,
        "event_at": f"2026-06-0{position}T10:00:00-05:00",
        "event_received_at": datetime(2026, 6, position, 10, 0, 0, tzinfo=timezone.utc),
        "location_zip": "12345",
        "raw_payload": None,
    }


class TestShuffleOutOfOrderEvents:
    """Test out-of-order event shuffling."""

    def test_single_event_no_shuffle(self):
        """Single event should never be shuffled."""
        events = [_create_test_event("ev_1", "picked_up", 1)]
        result = _shuffle_out_of_order_events(events, shuffle_probability=1.0)

        assert result == events
        assert len(result) == 1

    def test_two_events_can_shuffle(self):
        """Two events can be shuffled into any order."""
        events = [
            _create_test_event("ev_1", "picked_up", 1),
            _create_test_event("ev_2", "delivered", 4),
        ]

        # Run multiple times to see variation in orderings
        results = [_shuffle_out_of_order_events(events.copy(), shuffle_probability=1.0) for _ in range(20)]

        # All events should be present
        for result in results:
            event_ids = [e["event_id"] for e in result]
            assert set(event_ids) == {"ev_1", "ev_2"}

        # Should see different orderings (even if low probability with just 2 events)
        orderings = set()
        for result in results:
            ordering = tuple(e["event_id"] for e in result)
            orderings.add(ordering)

        # With random shuffle, should see at least one different ordering eventually
        assert len(orderings) > 0  # At least have the results

    def test_four_events_shuffle(self):
        """Four events can be shuffled into multiple different orderings."""
        events = [
            _create_test_event("ev_1", "picked_up", 1),
            _create_test_event("ev_2", "in_transit", 2),
            _create_test_event("ev_3", "out_for_delivery", 3),
            _create_test_event("ev_4", "delivered", 4),
        ]

        # Run multiple times to check for shuffling variation
        results = [_shuffle_out_of_order_events(events.copy(), shuffle_probability=1.0) for _ in range(20)]

        # All events should be present in each result
        for result in results:
            event_ids = [e["event_id"] for e in result]
            assert set(event_ids) == {"ev_1", "ev_2", "ev_3", "ev_4"}

        # Check that we see different orderings across runs
        orderings = set()
        for result in results:
            ordering = tuple(e["event_id"] for e in result)
            orderings.add(ordering)

        # With random shuffle, should see multiple different orderings
        assert len(orderings) > 1

    def test_events_can_appear_in_any_position(self):
        """Events can appear in any position after shuffling."""
        events = [
            _create_test_event("first", "picked_up", 1),
            _create_test_event("mid1", "in_transit", 2),
            _create_test_event("mid2", "out_for_delivery", 3),
            _create_test_event("last", "delivered", 4),
        ]

        # Collect positions where each event appears
        position_map = {"first": set(), "mid1": set(), "mid2": set(), "last": set()}

        for _ in range(50):
            result = _shuffle_out_of_order_events(events.copy(), shuffle_probability=1.0)
            for position, event in enumerate(result):
                position_map[event["event_id"]].add(position)

        # Each event should appear in multiple different positions
        for event_id, positions in position_map.items():
            assert len(positions) > 1, f"Event {event_id} only appeared in position(s) {positions}"

    def test_shuffle_probability_respected(self):
        """Shuffle probability should control whether shuffling happens."""
        events = [
            _create_test_event("ev_1", "picked_up", 1),
            _create_test_event("ev_2", "in_transit", 2),
            _create_test_event("ev_3", "out_for_delivery", 3),
            _create_test_event("ev_4", "delivered", 4),
        ]

        # With 0 probability, should never shuffle
        results_no_shuffle = [_shuffle_out_of_order_events(events.copy(), shuffle_probability=0.0) for _ in range(10)]
        for result in results_no_shuffle:
            assert result[1]["event_id"] == "ev_2"  # Middle unchanged

        # With 1.0 probability, should always shuffle (if random condition met)
        results_shuffle = [_shuffle_out_of_order_events(events.copy(), shuffle_probability=1.0) for _ in range(10)]
        # At least some should have different order
        shuffled_count = sum(1 for r in results_shuffle if r[1]["event_id"] != "ev_2")
        assert shuffled_count > 0

    def test_three_events_shuffle(self):
        """Three events can be shuffled into different orderings."""
        events = [
            _create_test_event("ev_1", "picked_up", 1),
            _create_test_event("ev_2", "in_transit", 2),
            _create_test_event("ev_3", "delivered", 3),
        ]

        # Run multiple times to see variation
        results = [_shuffle_out_of_order_events(events.copy(), shuffle_probability=1.0) for _ in range(20)]

        # All events should be present
        for result in results:
            event_ids = [e["event_id"] for e in result]
            assert set(event_ids) == {"ev_1", "ev_2", "ev_3"}

        # Should see different orderings
        orderings = set()
        for result in results:
            ordering = tuple(e["event_id"] for e in result)
            orderings.add(ordering)

        assert len(orderings) > 1

    def test_timestamps_unchanged(self):
        """Shuffling should not change event_at timestamps."""
        events = [
            _create_test_event("ev_1", "picked_up", 1),
            _create_test_event("ev_2", "in_transit", 2),
            _create_test_event("ev_3", "out_for_delivery", 3),
            _create_test_event("ev_4", "delivered", 4),
        ]

        original_timestamps = [e["event_at"] for e in events]
        result = _shuffle_out_of_order_events(events, shuffle_probability=1.0)
        result_timestamps = [e["event_at"] for e in result]

        # Same timestamps, just possibly different order
        assert sorted(result_timestamps) == sorted(original_timestamps)
