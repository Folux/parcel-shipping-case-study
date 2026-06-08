"""Tests for base labels generator (Step 1)."""

import pytest
import pandas as pd
from datetime import datetime

from skullport_generator.labels_generator import (
    _generate_label_id,
    _generate_customer_id,
    _select_carrier,
    _select_service_class,
    _generate_zip_code,
    _generate_weight,
    _generate_insurance,
    _calculate_promised_delivery_date,
    generate_base_labels,
    apply_cdc_changes,
)
from skullport_generator.config import load_config


class TestIDGeneration:
    """Test label and customer ID generation."""

    def test_generate_label_id_format(self):
        """label_id should be lbl_<24 hex>."""
        label_id = _generate_label_id()
        assert label_id.startswith("lbl_")
        assert len(label_id) == 28  # 4 + 24
        hex_part = label_id[4:]  # Skip "lbl_"
        assert all(c in "0123456789abcdef" for c in hex_part)

    def test_generate_customer_id_format(self):
        """customer_id should be cust_<12 hex>."""
        customer_id = _generate_customer_id()
        assert customer_id.startswith("cust_")
        assert len(customer_id) == 17  # 5 + 12
        hex_part = customer_id[5:]  # Skip "cust_"
        assert all(c in "0123456789abcdef" for c in hex_part)

    def test_id_uniqueness(self):
        """Generated IDs should be unique."""
        ids = {_generate_label_id() for _ in range(100)}
        assert len(ids) == 100  # All unique


class TestCarrierSelection:
    """Test carrier selection logic."""

    def test_select_carrier_valid(self):
        """select_carrier should return a valid carrier."""
        carrier_dist = {"USPS": 0.5, "UPS": 0.3, "FEDEX": 0.15, "DHL_ECOM": 0.05}
        carrier = _select_carrier(carrier_dist)
        assert carrier in carrier_dist.keys()


class TestServiceClassSelection:
    """Test service class selection logic."""

    def test_select_service_class_usps(self):
        """USPS service class should be valid."""
        service_class = _select_service_class("USPS", 0.1)
        assert service_class in ("USPS_PRIORITY", "USPS_STANDARD")

    def test_select_service_class_ups(self):
        """UPS service class should be valid."""
        service_class = _select_service_class("UPS", 0.1)
        assert service_class in ("UPS_2ND_DAY", "UPS_GROUND")


class TestZIPGeneration:
    """Test ZIP code generation."""

    def test_generate_zip_code_format(self):
        """ZIP code should be 5 digits with leading zeros."""
        zip_code = _generate_zip_code()
        assert len(zip_code) == 5
        assert zip_code.isdigit()

    def test_generate_zip_code_range(self):
        """ZIP codes should be in range 00001-99999."""
        zip_codes = [int(_generate_zip_code()) for _ in range(100)]
        assert all(1 <= z <= 99999 for z in zip_codes)
        assert min(zip_codes) >= 1  # Should have at least one in lower range
        assert max(zip_codes) <= 99999


class TestWeightGeneration:
    """Test weight generation."""

    def test_generate_weight_range(self):
        """Weight should be 1-1180 oz."""
        weights = [_generate_weight() for _ in range(100)]
        assert all(1 <= w <= 1180 for w in weights)
        assert min(weights) >= 1
        assert max(weights) <= 1180


class TestInsuranceGeneration:
    """Test insurance value generation."""

    def test_generate_insurance_uninsured(self):
        """Insurance should be None when not insured."""
        # Set proportion to 0 to guarantee uninsured
        insurance = _generate_insurance(0.0)
        assert insurance is None

    def test_generate_insurance_insured(self):
        """Insurance should be $50-$500 when insured."""
        # Set proportion to 1.0 to guarantee insured
        insurance = _generate_insurance(1.0)
        assert insurance is not None
        assert 5000 <= insurance <= 50000  # Cents: $50-$500


class TestPromisedDelivery:
    """Test promised delivery calculation."""

    def test_calculate_promised_delivery_usps_priority(self):
        """USPS_PRIORITY should add 3 days."""
        created = datetime(2026, 6, 1, 10, 0, 0)
        promised = _calculate_promised_delivery_date(created, "USPS_PRIORITY")
        assert promised == datetime(2026, 6, 4, 10, 0, 0)

    def test_calculate_promised_delivery_ups_ground(self):
        """UPS_GROUND should add 7 days."""
        created = datetime(2026, 6, 1, 10, 0, 0)
        promised = _calculate_promised_delivery_date(created, "UPS_GROUND")
        assert promised == datetime(2026, 6, 8, 10, 0, 0)
