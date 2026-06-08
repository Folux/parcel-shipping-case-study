"""Tests for events generator Step 1d: Apply Carrier-Specific Schema."""

import pytest
from datetime import datetime, timedelta, timezone

from skullport_generator.events_generator import (
    _format_event_at,
    TIMEZONE_FORMAT,
    US_TIMEZONE_ABBRS,
    US_TIMEZONE_OFFSETS,
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
        """DHL should format with a timezone abbreviation AND convert the wall-clock
        time into that zone, so the timestamp represents the correct UTC instant."""
        event_at = datetime(2026, 6, 6, 10, 30, 0, tzinfo=timezone.utc)
        result = _format_event_at(event_at, "DHL_ECOM")

        # Should have format like "2026-06-06T05:30:00 EST"
        parts = result.split(" ")
        assert len(parts) == 2
        local_ts, tz_abbr = parts
        assert tz_abbr in US_TIMEZONE_ABBRS

        # The local wall-clock time must equal the UTC instant shifted by the
        # abbreviation's offset (e.g. 10:30 UTC + (-5) = 05:30 EST).
        offset = US_TIMEZONE_OFFSETS[tz_abbr]
        expected_local = (event_at + timedelta(hours=offset)).strftime("%Y-%m-%dT%H:%M:%S")
        assert local_ts == expected_local

    def test_dhl_format_round_trips_to_utc(self):
        """Parsing the DHL local time back with its offset should recover the UTC instant."""
        event_at = datetime(2026, 6, 6, 10, 30, 0, tzinfo=timezone.utc)
        result = _format_event_at(event_at, "DHL_ECOM")

        local_ts, tz_abbr = result.split(" ")
        offset = US_TIMEZONE_OFFSETS[tz_abbr]
        parsed_local = datetime.strptime(local_ts, "%Y-%m-%dT%H:%M:%S")
        recovered_utc = (parsed_local - timedelta(hours=offset)).replace(tzinfo=timezone.utc)
        assert recovered_utc == event_at

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
