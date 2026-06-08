"""Tests for events generator Step 1d: Apply Carrier-Specific Schema."""

import pytest
from datetime import datetime, timezone

from skullport_generator.events_generator import (
    _format_event_at,
    TIMEZONE_FORMAT,
    US_TIMEZONE_ABBRS,
)


class TestFormatEventAt:
    """Test carrier-specific timestamp formatting."""

    def test_usps_format_with_offset(self):
        """USPS should format with offset (e.g., 2026-06-06T10:30:00-05:00)."""
        event_at = datetime(2026, 6, 6, 10, 30, 0, tzinfo=timezone.utc)
        result = _format_event_at(event_at, "USPS")

        # Should have format like "2026-06-06T05:30:00-05:00" (10:30 UTC - 5 hours = 05:30 EST)
        # The time should be adjusted for the offset
        assert "T" in result  # ISO 8601
        assert "-05:00" in result  # Correct offset format
        # Time portion should be 05:30 (10:30 UTC - 5 hours)
        assert "05:30:00" in result

    def test_ups_format_with_z(self):
        """UPS should format with Z (e.g., 2026-06-06T10:30:00Z)."""
        event_at = datetime(2026, 6, 6, 10, 30, 0, tzinfo=timezone.utc)
        result = _format_event_at(event_at, "UPS")

        assert result == "2026-06-06T10:30:00Z"

    def test_fedex_format_plain(self):
        """FEDEX should format plain ISO 8601 (e.g., 2026-06-06T10:30:00)."""
        event_at = datetime(2026, 6, 6, 10, 30, 0, tzinfo=timezone.utc)
        result = _format_event_at(event_at, "FEDEX")

        assert result == "2026-06-06T10:30:00"
        assert "Z" not in result
        assert "-05" not in result  # No offset

    def test_dhl_format_with_timezone_abbr(self):
        """DHL should format with timezone abbreviation (e.g., 2026-06-06T10:30:00 EST)."""
        event_at = datetime(2026, 6, 6, 10, 30, 0, tzinfo=timezone.utc)
        result = _format_event_at(event_at, "DHL_ECOM")

        # Should have format like "2026-06-06T10:30:00 EST"
        parts = result.split(" ")
        assert len(parts) == 2
        assert parts[0] == "2026-06-06T10:30:00"
        assert parts[1] in US_TIMEZONE_ABBRS

    def test_all_carriers_format_correctly(self):
        """Each carrier should format according to TIMEZONE_FORMAT."""
        event_at = datetime(2026, 6, 6, 10, 30, 0, tzinfo=timezone.utc)

        for carrier in TIMEZONE_FORMAT.keys():
            result = _format_event_at(event_at, carrier)
            # Should always be a non-empty string
            assert isinstance(result, str)
            assert len(result) > 0
            # Should contain the date
            assert "2026-06-06" in result

    def test_format_consistency_across_calls(self):
        """Same input should produce same format (except for DHL randomness)."""
        event_at = datetime(2026, 6, 6, 10, 30, 0, tzinfo=timezone.utc)

        # USPS should always format the same way
        result1 = _format_event_at(event_at, "USPS")
        result2 = _format_event_at(event_at, "USPS")
        assert result1 == result2

        # UPS should always format the same way
        result1 = _format_event_at(event_at, "UPS")
        result2 = _format_event_at(event_at, "UPS")
        assert result1 == result2

        # FEDEX should always format the same way
        result1 = _format_event_at(event_at, "FEDEX")
        result2 = _format_event_at(event_at, "FEDEX")
        assert result1 == result2

    def test_dhl_randomness(self):
        """DHL should sometimes produce different timezone abbreviations."""
        event_at = datetime(2026, 6, 6, 10, 30, 0, tzinfo=timezone.utc)

        results = set()
        for _ in range(50):
            result = _format_event_at(event_at, "DHL_ECOM")
            results.add(result)

        # Should have at least some variation in timezone abbreviations
        # (very unlikely to get same abbreviation all 50 times)
        assert len(results) > 1
