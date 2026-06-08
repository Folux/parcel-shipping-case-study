"""Tests for events generator Step 2g: Apply Voided Label Tracking."""

import pytest
from datetime import datetime, timezone, timedelta

from skullport_generator.events_generator import (
    _apply_voided_label_tracking,
    EventRow,
)


def _create_test_event(event_id: str, label_id: str = "lbl_test") -> EventRow:
    """Helper to create a test event."""
    return {
        "event_id": event_id,
        "label_id": label_id,
        "carrier": "USPS",
        "event_code": "0300",
        "event_type": None,
        "event_at": "2026-06-06T10:30:00-05:00",
        "event_received_at": datetime(2026, 6, 6, 10, 30, 0, tzinfo=timezone.utc),
        "location_zip": "12345",
        "raw_payload": None,
    }


def _create_test_labels_df():
    """Helper to create test labels dataframe."""
    import pandas as pd

    data = {
        "label_id": ["lbl_1", "lbl_2", "lbl_3", "lbl_4"],
        "carrier": ["USPS", "UPS", "FEDEX", "DHL_ECOM"],
        "voided_at": [
            datetime(2026, 6, 5, 10, 0, 0, tzinfo=timezone.utc),  # voided
            None,  # not voided
            datetime(2026, 6, 4, 14, 30, 0, tzinfo=timezone.utc),  # voided
            None,  # not voided
        ],
        "label_created_at": [
            datetime(2026, 6, 5, 9, 0, 0, tzinfo=timezone.utc),
            datetime(2026, 6, 6, 8, 0, 0, tzinfo=timezone.utc),
            datetime(2026, 6, 4, 13, 0, 0, tzinfo=timezone.utc),
            datetime(2026, 6, 6, 7, 0, 0, tzinfo=timezone.utc),
        ],
    }
    return pd.DataFrame(data)


class TestApplyVoidedLabelTracking:
    """Test voided label tracking."""

    def test_no_events_with_zero_proportion(self):
        """With 0 probability, no events should be added to voided labels."""
        events = [_create_test_event("ev_1", "lbl_1")]
        labels_df = _create_test_labels_df()

        result = _apply_voided_label_tracking(events, labels_df, voided_tracking_proportion=0.0)

        # Should have only the original event
        assert len(result) == 1
        assert result[0]["event_id"] == "ev_1"

    def test_events_added_to_voided_labels(self):
        """With 1.0 probability, events should be added to all voided labels."""
        events = [_create_test_event("ev_1", "lbl_1")]
        labels_df = _create_test_labels_df()

        result = _apply_voided_label_tracking(events, labels_df, voided_tracking_proportion=1.0)

        # Should have original event + events for 2 voided labels (lbl_1, lbl_3)
        # Each voided label gets 1-2 events, so minimum is 1 + 1 + 1 = 3 total
        assert len(result) >= 3  # Original + at least 1 for each of 2 voided labels

    def test_events_only_for_voided_labels(self):
        """Events should only be added to voided labels, not active ones."""
        events = []
        labels_df = _create_test_labels_df()

        result = _apply_voided_label_tracking(events, labels_df, voided_tracking_proportion=1.0)

        # All new events should belong to voided labels (lbl_1 or lbl_3)
        for event in result:
            assert event["label_id"] in ["lbl_1", "lbl_3"]

    def test_added_events_have_correct_carrier(self):
        """Events added to voided labels should have correct carrier."""
        events = []
        labels_df = _create_test_labels_df()

        result = _apply_voided_label_tracking(events, labels_df, voided_tracking_proportion=1.0)

        # Check carrier matches the label's carrier
        for event in result:
            if event["label_id"] == "lbl_1":
                assert event["carrier"] == "USPS"
            elif event["label_id"] == "lbl_3":
                assert event["carrier"] == "FEDEX"

    def test_added_events_after_voiding(self):
        """Events added to voided labels should have timestamps after voiding."""
        events = []
        labels_df = _create_test_labels_df()

        result = _apply_voided_label_tracking(events, labels_df, voided_tracking_proportion=1.0)

        # Check that event_received_at is after voided_at
        voided_times = {
            "lbl_1": datetime(2026, 6, 5, 10, 0, 0, tzinfo=timezone.utc),
            "lbl_3": datetime(2026, 6, 4, 14, 30, 0, tzinfo=timezone.utc),
        }

        for event in result:
            if event["label_id"] in voided_times:
                assert event["event_received_at"] > voided_times[event["label_id"]]

    def test_proportion_respected(self):
        """Voided tracking proportion should control how many labels get events."""
        events = []
        # Create many voided labels
        import pandas as pd

        labels_data = {
            "label_id": [f"lbl_{i}" for i in range(100)],
            "carrier": ["USPS"] * 100,
            "voided_at": [
                datetime(2026, 6, 5, 10, 0, 0, tzinfo=timezone.utc) for _ in range(100)
            ],
            "label_created_at": [
                datetime(2026, 6, 5, 9, 0, 0, tzinfo=timezone.utc) for _ in range(100)
            ],
        }
        labels_df = pd.DataFrame(labels_data)

        # With 0.5 probability, ~50 labels should get events
        result = _apply_voided_label_tracking(events, labels_df, voided_tracking_proportion=0.5)

        # Count how many unique labels got events
        labels_with_events = set(e["label_id"] for e in result)

        # Should be roughly 50 (within reasonable variance)
        assert 30 < len(labels_with_events) < 70, f"Got {len(labels_with_events)} labels with events"

    def test_1_to_2_events_per_voided_label(self):
        """Each voided label should get 1-2 events."""
        events = []
        import pandas as pd

        labels_data = {
            "label_id": ["lbl_1", "lbl_2"],
            "carrier": ["USPS", "USPS"],
            "voided_at": [
                datetime(2026, 6, 5, 10, 0, 0, tzinfo=timezone.utc),
                datetime(2026, 6, 5, 10, 0, 0, tzinfo=timezone.utc),
            ],
            "label_created_at": [
                datetime(2026, 6, 5, 9, 0, 0, tzinfo=timezone.utc),
                datetime(2026, 6, 5, 9, 0, 0, tzinfo=timezone.utc),
            ],
        }
        labels_df = pd.DataFrame(labels_data)

        result = _apply_voided_label_tracking(events, labels_df, voided_tracking_proportion=1.0)

        # Count events per label
        lbl_1_count = sum(1 for e in result if e["label_id"] == "lbl_1")
        lbl_2_count = sum(1 for e in result if e["label_id"] == "lbl_2")

        # Each should have 1-2 events
        assert 1 <= lbl_1_count <= 2
        assert 1 <= lbl_2_count <= 2

    def test_added_events_have_valid_fields(self):
        """Added events should have all required fields."""
        events = []
        labels_df = _create_test_labels_df()

        result = _apply_voided_label_tracking(events, labels_df, voided_tracking_proportion=1.0)

        # Check all added events have valid fields
        for event in result:
            assert event["event_id"]
            assert event["label_id"]
            assert event["carrier"]
            # event_code or event_type should be set (depending on carrier)
            assert event["event_code"] is not None or event["event_type"] is not None
            assert event["event_at"]
            assert event["event_received_at"]
            # location_zip can be None

    def test_original_events_preserved(self):
        """Original events should be preserved and extended."""
        events = [_create_test_event("ev_1", "lbl_1"), _create_test_event("ev_2", "lbl_2")]
        labels_df = _create_test_labels_df()

        result = _apply_voided_label_tracking(events, labels_df, voided_tracking_proportion=1.0)

        # Original events should still be there
        assert result[0]["event_id"] == "ev_1"
        assert result[1]["event_id"] == "ev_2"

        # New events appended after
        assert len(result) > 2

    def test_empty_events_list(self):
        """Empty events list should still add voided label events."""
        events = []
        labels_df = _create_test_labels_df()

        result = _apply_voided_label_tracking(events, labels_df, voided_tracking_proportion=1.0)

        # Should have events (from 2 voided labels)
        assert len(result) >= 2

    def test_no_voided_labels(self):
        """If there are no voided labels, no events should be added."""
        import pandas as pd

        events = [_create_test_event("ev_1", "lbl_1")]

        # Create labels with no voided_at
        labels_data = {
            "label_id": ["lbl_1", "lbl_2"],
            "carrier": ["USPS", "UPS"],
            "voided_at": [None, None],
            "label_created_at": [
                datetime(2026, 6, 5, 9, 0, 0, tzinfo=timezone.utc),
                datetime(2026, 6, 6, 8, 0, 0, tzinfo=timezone.utc),
            ],
        }
        labels_df = pd.DataFrame(labels_data)

        result = _apply_voided_label_tracking(events, labels_df, voided_tracking_proportion=1.0)

        # Should have only original event
        assert len(result) == 1
        assert result[0]["event_id"] == "ev_1"
