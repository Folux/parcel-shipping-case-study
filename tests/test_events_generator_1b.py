"""Tests for events generator Step 1b: Decide Event Sequence per Label."""

import pytest
from datetime import datetime, timedelta, timezone

from skullport_generator.events_generator import (
    _get_tracking_events,
    EVENT_SEQUENCE,
    EVENT_SEQUENCE_RULES,
)


class TestDecideEventSequenceImmediateVoid:
    """Test event sequence for immediately voided labels."""

    def test_immediately_voided_zero_events(self):
        """Label voided < 1 hour should have 0 events."""
        created_at = datetime(2026, 6, 1, 10, 0, 0, tzinfo=timezone.utc)
        voided_at = datetime(2026, 6, 1, 10, 30, 0, tzinfo=timezone.utc)  # 30 min later

        label = {
            "label_id": "lbl_test",
            "label_created_at": created_at,
            "voided_at": voided_at,
        }

        result = _get_tracking_events(label)

        assert result["num_events"] == 0
        assert result["sequence"] == []

    def test_immediately_voided_boundary(self):
        """Label voided at exactly 1 hour should have 0 events (boundary condition)."""
        created_at = datetime(2026, 6, 1, 10, 0, 0, tzinfo=timezone.utc)
        voided_at = datetime(2026, 6, 1, 11, 0, 0, tzinfo=timezone.utc)  # exactly 1 hour

        label = {
            "label_id": "lbl_test",
            "label_created_at": created_at,
            "voided_at": voided_at,
        }

        result = _get_tracking_events(label)

        assert result["num_events"] == 0
        assert result["sequence"] == []


class TestDecideEventSequenceLateVoid:
    """Test event sequence for late-voided labels (2-5 days)."""

    def test_late_voided_can_have_0_events(self):
        """Late-voided label should possibly have 0 events (50% chance)."""
        created_at = datetime(2026, 6, 1, 10, 0, 0, tzinfo=timezone.utc)
        voided_at = created_at + timedelta(days=3)  # 3 days later

        label = {
            "label_id": "lbl_test",
            "label_created_at": created_at,
            "voided_at": voided_at,
        }

        # Run multiple times to check range
        results = [_get_tracking_events(label) for _ in range(50)]
        num_events_list = [r["num_events"] for r in results]

        # Should have mix of 0, 1, 2, 3 events
        assert 0 in num_events_list
        assert all(0 <= n <= 3 for n in num_events_list)

    def test_late_voided_num_events_within_range(self):
        """Late-voided events should be 0-3."""
        created_at = datetime(2026, 6, 1, 10, 0, 0, tzinfo=timezone.utc)
        voided_at = created_at + timedelta(days=2.5)

        label = {
            "label_id": "lbl_test",
            "label_created_at": created_at,
            "voided_at": voided_at,
        }

        for _ in range(20):
            result = _get_tracking_events(label)
            assert 0 <= result["num_events"] <= 3
            assert len(result["sequence"]) == result["num_events"]

    def test_late_voided_sequence_matches_count(self):
        """Sequence length should match num_events."""
        created_at = datetime(2026, 6, 1, 10, 0, 0, tzinfo=timezone.utc)
        voided_at = created_at + timedelta(days=4)

        label = {
            "label_id": "lbl_test",
            "label_created_at": created_at,
            "voided_at": voided_at,
        }

        result = _get_tracking_events(label)

        assert len(result["sequence"]) == result["num_events"]
        # Sequence should be prefix of standard sequence
        assert result["sequence"] == EVENT_SEQUENCE[: result["num_events"]]


class TestDecideEventSequenceNotVoided:
    """Test event sequence for non-voided labels."""

    def test_not_voided_mostly_4_events(self):
        """Non-voided labels should mostly have 4 events (99%)."""
        created_at = datetime(2026, 6, 1, 10, 0, 0, tzinfo=timezone.utc)

        label = {
            "label_id": "lbl_test",
            "label_created_at": created_at,
            "voided_at": None,
        }

        results = [_get_tracking_events(label) for _ in range(200)]
        four_event_count = sum(1 for r in results if r["num_events"] == 4)
        two_event_count = sum(1 for r in results if r["num_events"] == 2)

        # Should be roughly 99% with 4 events, 1% with 2 events
        # Allow 85-100% range for statistical variance
        assert 0.85 < (four_event_count / 200) <= 1.0
        # At least some 2-event (incomplete) labels should exist
        assert two_event_count > 0

    def test_not_voided_4_events_full_sequence(self):
        """Non-voided 4-event labels should have full sequence."""
        created_at = datetime(2026, 6, 1, 10, 0, 0, tzinfo=timezone.utc)

        label = {
            "label_id": "lbl_test",
            "label_created_at": created_at,
            "voided_at": None,
        }

        # Run enough times to get at least one 4-event result
        for _ in range(200):
            result = _get_tracking_events(label)
            if result["num_events"] == 4:
                assert result["sequence"] == EVENT_SEQUENCE
                break

    def test_not_voided_2_events_incomplete(self):
        """Non-voided 2-event labels (1%) should have incomplete sequence."""
        created_at = datetime(2026, 6, 1, 10, 0, 0, tzinfo=timezone.utc)

        label = {
            "label_id": "lbl_test",
            "label_created_at": created_at,
            "voided_at": None,
        }

        # Run enough times to get at least one 2-event result
        for _ in range(200):
            result = _get_tracking_events(label)
            if result["num_events"] == 2:
                assert result["sequence"] == ["picked_up", "in_transit"]
                break


class TestDecideEventSequenceEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_sequence_is_prefix_of_standard(self):
        """Any sequence should be a prefix of EVENT_SEQUENCE."""
        created_at = datetime(2026, 6, 1, 10, 0, 0, tzinfo=timezone.utc)

        # Test multiple scenarios
        scenarios = [
            {"voided_at": None},
            {"voided_at": created_at + timedelta(minutes=30)},
            {"voided_at": created_at + timedelta(days=3)},
        ]

        for scenario in scenarios:
            label = {
                "label_id": "lbl_test",
                "label_created_at": created_at,
                "voided_at": scenario["voided_at"],
            }

            for _ in range(20):
                result = _get_tracking_events(label)
                expected_sequence = EVENT_SEQUENCE[: result["num_events"]]
                assert result["sequence"] == expected_sequence

    def test_result_has_required_keys(self):
        """Result should always have num_events and sequence."""
        created_at = datetime(2026, 6, 1, 10, 0, 0, tzinfo=timezone.utc)

        label = {
            "label_id": "lbl_test",
            "label_created_at": created_at,
            "voided_at": None,
        }

        result = _get_tracking_events(label)

        assert "num_events" in result
        assert "sequence" in result
        assert isinstance(result["num_events"], int)
        assert isinstance(result["sequence"], list)
