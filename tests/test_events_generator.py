"""Tests for events generator helpers and constants (Step 1a)."""

import pytest
from skullport_generator.events_generator import (
    _generate_event_id,
    _get_event_code_and_type,
    _get_event_sla_proportion,
    EVENT_CODES,
    EVENT_TIMING,
    EVENT_SEQUENCE,
)


class TestEventIDGeneration:
    """Test event ID generation."""

    def test_generate_event_id_format(self):
        """Event ID should be UUID-style hex string (32 chars)."""
        event_id = _generate_event_id()
        assert len(event_id) == 32
        assert all(c in "0123456789abcdef" for c in event_id)

    def test_generate_event_id_uniqueness(self):
        """Generated event IDs should be unique."""
        ids = {_generate_event_id() for _ in range(100)}
        assert len(ids) == 100  # All unique


class TestEventCodeMapping:
    """Test event code/type retrieval for all carriers."""

    def test_usps_event_codes(self):
        """USPS should have all 4 event codes."""
        assert _get_event_code_and_type("USPS", "picked_up") == ("0300", None)
        assert _get_event_code_and_type("USPS", "in_transit") == ("0301", None)
        assert _get_event_code_and_type("USPS", "out_for_delivery") == ("0310", None)
        assert _get_event_code_and_type("USPS", "delivered") == ("0320", None)

    def test_ups_event_types(self):
        """UPS should have all 4 event types."""
        assert _get_event_code_and_type("UPS", "picked_up") == (None, "PICKUP")
        assert _get_event_code_and_type("UPS", "in_transit") == (None, "IN_TRANSIT")
        assert _get_event_code_and_type("UPS", "out_for_delivery") == (None, "OUT_FOR_DELIVERY")
        assert _get_event_code_and_type("UPS", "delivered") == (None, "DELIVERED")

    def test_fedex_event_types(self):
        """FEDEX should have all 4 event types."""
        assert _get_event_code_and_type("FEDEX", "picked_up") == (None, "PICKUP")
        assert _get_event_code_and_type("FEDEX", "in_transit") == (None, "IN_TRANSIT")
        assert _get_event_code_and_type("FEDEX", "out_for_delivery") == (None, "OUT_FOR_DELIVERY")
        assert _get_event_code_and_type("FEDEX", "delivered") == (None, "DELIVERED")

    def test_dhl_event_codes(self):
        """DHL_ECOM should have all 4 event codes."""
        assert _get_event_code_and_type("DHL_ECOM", "picked_up") == ("PU", None)
        assert _get_event_code_and_type("DHL_ECOM", "in_transit") == ("IT", None)
        assert _get_event_code_and_type("DHL_ECOM", "out_for_delivery") == ("OFD", None)
        assert _get_event_code_and_type("DHL_ECOM", "delivered") == ("DL", None)

    def test_invalid_event_returns_none(self):
        """Invalid event name should return (None, None)."""
        assert _get_event_code_and_type("USPS", "invalid_event") == (None, None)
        assert _get_event_code_and_type("UPS", "invalid_event") == (None, None)


class TestEventSLAProportion:
    """Test SLA proportion retrieval."""

    def test_all_events_have_proportions(self):
        """All 4 events should have SLA proportions."""
        assert _get_event_sla_proportion("picked_up") == 0.15
        assert _get_event_sla_proportion("in_transit") == 0.40
        assert _get_event_sla_proportion("out_for_delivery") == 0.75
        assert _get_event_sla_proportion("delivered") == 0.95

    def test_proportions_in_ascending_order(self):
        """SLA proportions should be in ascending order."""
        picked_up = _get_event_sla_proportion("picked_up")
        in_transit = _get_event_sla_proportion("in_transit")
        out_for_delivery = _get_event_sla_proportion("out_for_delivery")
        delivered = _get_event_sla_proportion("delivered")

        assert picked_up < in_transit < out_for_delivery < delivered

    def test_invalid_event_returns_zero(self):
        """Invalid event should return 0.0."""
        assert _get_event_sla_proportion("invalid_event") == 0.0


class TestEventConstants:
    """Test event-related constants."""

    def test_event_codes_all_carriers(self):
        """EVENT_CODES should have all 4 carriers."""
        assert "USPS" in EVENT_CODES
        assert "UPS" in EVENT_CODES
        assert "FEDEX" in EVENT_CODES
        assert "DHL_ECOM" in EVENT_CODES

    def test_event_codes_all_events(self):
        """Each carrier in EVENT_CODES should have all 4 events."""
        for carrier in EVENT_CODES.keys():
            assert "picked_up" in EVENT_CODES[carrier]
            assert "in_transit" in EVENT_CODES[carrier]
            assert "out_for_delivery" in EVENT_CODES[carrier]
            assert "delivered" in EVENT_CODES[carrier]

    def test_event_timing_completeness(self):
        """EVENT_TIMING should have all 4 event names."""
        assert "picked_up" in EVENT_TIMING
        assert "in_transit" in EVENT_TIMING
        assert "out_for_delivery" in EVENT_TIMING
        assert "delivered" in EVENT_TIMING

    def test_event_sequence_standard(self):
        """EVENT_SEQUENCE should be the standard 4-event sequence."""
        assert EVENT_SEQUENCE == [
            "picked_up",
            "in_transit",
            "out_for_delivery",
            "delivered",
        ]
