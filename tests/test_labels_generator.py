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


def _config_to_dict(config, num_labels=None):
    """Convert GeneratorConfig dataclass to dict for modification."""
    return {
        "num_labels": num_labels or config.num_labels,
        "carrier_distribution": config.carrier_distribution,
        "service_class_express_proportion": config.service_class_express_proportion,
        "insurance_proportion": config.insurance_proportion,
        "date_range_days": config.date_range_days,
        "random_seed": config.random_seed,
        "changed_labels_proportion": config.changed_labels_proportion,
        "changed_voided_proportion": config.changed_voided_proportion,
        "voided_fraud_proportion": config.voided_fraud_proportion,
    }


class TestGenerateBaseLabels:
    """Test base labels generation."""

    def test_generate_base_labels_count(self):
        """Should generate correct number of labels."""
        config = load_config("config.yaml")
        config_dict = _config_to_dict(config, num_labels=100)
        df = generate_base_labels(config_dict)
        assert len(df) == 100

    def test_generate_base_labels_columns(self):
        """Should have all 12 required columns."""
        config = load_config("config.yaml")
        config_dict = _config_to_dict(config, num_labels=10)
        df = generate_base_labels(config_dict)

        expected_columns = {
            "label_id",
            "customer_id",
            "carrier",
            "service_class",
            "origin_zip",
            "dest_zip",
            "weight_oz",
            "declared_value_cents",
            "label_created_at",
            "carrier_promised_delivery_at",
            "voided_at",
            "last_updated_at",
        }
        assert set(df.columns) == expected_columns

    def test_generate_base_labels_types(self):
        """Columns should have correct types."""
        config = load_config("config.yaml")
        config_dict = _config_to_dict(config, num_labels=10)
        df = generate_base_labels(config_dict)

        # String columns can be object, string, or str dtype
        assert "object" in str(df["label_id"].dtype) or "str" in str(df["label_id"].dtype)
        assert "object" in str(df["carrier"].dtype) or "str" in str(df["carrier"].dtype)
        assert df["weight_oz"].dtype == int
        assert "datetime" in str(df["label_created_at"].dtype)

    def test_generate_base_labels_one_row_per_label(self):
        """Each label should have exactly one row (no CDC yet)."""
        config = load_config("config.yaml")
        config_dict = _config_to_dict(config, num_labels=100)
        df = generate_base_labels(config_dict)

        # Each label_id should appear exactly once
        assert df["label_id"].nunique() == 100

    def test_generate_base_labels_reproducible(self):
        """Same seed should produce same data."""
        config = load_config("config.yaml")
        config_dict1 = _config_to_dict(config, num_labels=50)
        config_dict1["random_seed"] = 42
        config_dict2 = _config_to_dict(config, num_labels=50)
        config_dict2["random_seed"] = 42

        df1 = generate_base_labels(config_dict1)
        df2 = generate_base_labels(config_dict2)

        # Compare key columns (IDs and values)
        assert df1["label_id"].tolist() == df2["label_id"].tolist()
        assert df1["weight_oz"].tolist() == df2["weight_oz"].tolist()
        assert df1["carrier"].tolist() == df2["carrier"].tolist()

    def test_generate_base_labels_promised_delivery_after_created(self):
        """Promised delivery should always be after creation."""
        config = load_config("config.yaml")
        config_dict = _config_to_dict(config, num_labels=100)
        df = generate_base_labels(config_dict)

        assert all(
            df["carrier_promised_delivery_at"] > df["label_created_at"]
        )

    def test_generate_base_labels_weight_fraud_applied(self):
        """Weights > 1120 oz should be adjusted to 1000-1120 oz."""
        config = load_config("config.yaml")
        config_dict = _config_to_dict(config, num_labels=1000)
        df = generate_base_labels(config_dict)

        # No weight should exceed 1120 oz
        assert (df["weight_oz"] <= 1120).all()

        # Weights that were adjusted should be in 1000-1120 range
        # (Note: We can't directly verify which ones were adjusted without
        # re-running generation, but we can verify no weights exceed the limit)
        assert (df["weight_oz"] >= 1).all()

    def test_generate_base_labels_weight_fraud_consistent_across_rows(self):
        """All rows for same label should have same weight (fraud applied at generation)."""
        config = load_config("config.yaml")
        config_dict = _config_to_dict(config, num_labels=100)
        base_df = generate_base_labels(config_dict)
        cdc_df = apply_cdc_changes(base_df, config_dict)

        # For each label, verify all its rows have the same weight
        for label_id in cdc_df["label_id"].unique():
            label_rows = cdc_df[cdc_df["label_id"] == label_id]
            weights = label_rows["weight_oz"].unique()
            assert len(weights) == 1, f"Label {label_id} has multiple different weights: {weights}"

    def test_generate_base_labels_insurance_edge_case(self):
        """Some insured labels should have declared_value_cents = 0."""
        config = load_config("config.yaml")
        config_dict = _config_to_dict(config, num_labels=1000)
        df = generate_base_labels(config_dict)

        # Find insured labels (declared_value_cents is not None)
        insured = df[df["declared_value_cents"].notna()]

        # At least some should have value = 0 (edge case)
        zero_value = insured[insured["declared_value_cents"] == 0]
        assert len(zero_value) > 0, "No insured labels with zero value found"

        # Proportion should be roughly 5% of insured (allow 2-8% range for statistical variance)
        proportion = len(zero_value) / len(insured)
        assert 0.02 < proportion < 0.08, f"Edge case proportion {proportion:.2%} outside 2-8% range"

    def test_generate_base_labels_insurance_consistent_across_rows(self):
        """All rows for same label should have same insurance value."""
        config = load_config("config.yaml")
        config_dict = _config_to_dict(config, num_labels=100)
        base_df = generate_base_labels(config_dict)
        cdc_df = apply_cdc_changes(base_df, config_dict)

        # For each label, verify all its rows have the same insurance value
        for label_id in cdc_df["label_id"].unique():
            label_rows = cdc_df[cdc_df["label_id"] == label_id]
            insurance_values = label_rows["declared_value_cents"].unique()
            assert len(insurance_values) == 1, f"Label {label_id} has multiple different insurance values: {insurance_values}"


class TestApplyCDCChanges:
    """Test CDC changes logic (30% of labels get updates/voiding)."""

    def test_apply_cdc_changes_expands_dataframe(self):
        """Applying CDC changes should expand row count."""
        config = load_config("config.yaml")
        config_dict = _config_to_dict(config, num_labels=100)
        base_df = generate_base_labels(config_dict)

        cdc_df = apply_cdc_changes(base_df, config_dict)

        # Should have more rows than original
        assert len(cdc_df) > len(base_df)
        # But still same labels
        assert cdc_df["label_id"].nunique() == 100

    def test_apply_cdc_changes_percentage_changed(self):
        """Approximately 30% of labels should have multiple rows."""
        config = load_config("config.yaml")
        config_dict = _config_to_dict(config, num_labels=200)
        base_df = generate_base_labels(config_dict)

        cdc_df = apply_cdc_changes(base_df, config_dict)

        # Count labels with multiple rows
        row_counts = cdc_df.groupby("label_id").size()
        multi_row_labels = (row_counts > 1).sum()

        # Should be roughly 30% (200 * 0.30 = 60, allow 40-80 range)
        assert 40 < multi_row_labels < 80

    def test_apply_cdc_changes_voiding_percentage(self):
        """Approximately 9% of labels should be voided (30% * 30%)."""
        config = load_config("config.yaml")
        config_dict = _config_to_dict(config, num_labels=200)
        base_df = generate_base_labels(config_dict)

        cdc_df = apply_cdc_changes(base_df, config_dict)

        # Count voided labels (last row has voided_at set)
        voided_labels = cdc_df[cdc_df["voided_at"].notna()]["label_id"].nunique()

        # Should be roughly 9% (200 * 0.30 * 0.30 = 18, allow 10-26 range)
        assert 10 < voided_labels < 26

    def test_apply_cdc_changes_voided_has_two_rows(self):
        """Voided labels should have exactly 2 rows (initial + void)."""
        config = load_config("config.yaml")
        config_dict = _config_to_dict(config, num_labels=100)
        base_df = generate_base_labels(config_dict)

        cdc_df = apply_cdc_changes(base_df, config_dict)

        # Get voided labels
        voided_label_ids = cdc_df[cdc_df["voided_at"].notna()]["label_id"].unique()

        if len(voided_label_ids) > 0:
            for label_id in voided_label_ids:
                rows = cdc_df[cdc_df["label_id"] == label_id]
                assert len(rows) == 2  # Initial + void

    def test_apply_cdc_changes_non_voided_multi_rows(self):
        """Non-voided changed labels should have 2-3 rows (initial + 1-2 changes)."""
        config = load_config("config.yaml")
        config_dict = _config_to_dict(config, num_labels=100)
        base_df = generate_base_labels(config_dict)

        cdc_df = apply_cdc_changes(base_df, config_dict)

        # Get labels with multiple rows that are not voided
        multi_row_labels = cdc_df.groupby("label_id").filter(lambda x: len(x) > 1)
        non_voided_label_ids = (
            multi_row_labels.groupby("label_id")["voided_at"]
            .apply(lambda x: x.isna().all())
            .index
        )

        if len(non_voided_label_ids) > 0:
            for label_id in non_voided_label_ids:
                rows = cdc_df[cdc_df["label_id"] == label_id]
                assert 2 <= len(rows) <= 3  # Initial + 1 or 2 changes

    def test_apply_cdc_changes_timestamp_ordering(self):
        """For each label, last_updated_at should be in ascending order."""
        config = load_config("config.yaml")
        config_dict = _config_to_dict(config, num_labels=100)
        base_df = generate_base_labels(config_dict)

        cdc_df = apply_cdc_changes(base_df, config_dict)

        # Check ordering for multi-row labels
        for label_id in cdc_df[cdc_df.duplicated(subset=["label_id"], keep=False)][
            "label_id"
        ].unique():
            rows = cdc_df[cdc_df["label_id"] == label_id].sort_values("last_updated_at")
            timestamps = rows["last_updated_at"].tolist()
            # Should be strictly ascending
            assert timestamps == sorted(timestamps)
            assert len(set(timestamps)) == len(timestamps)  # All unique

    def test_apply_cdc_changes_voided_at_after_created(self):
        """Voided_at should always be after label_created_at."""
        config = load_config("config.yaml")
        config_dict = _config_to_dict(config, num_labels=100)
        base_df = generate_base_labels(config_dict)

        cdc_df = apply_cdc_changes(base_df, config_dict)

        voided = cdc_df[cdc_df["voided_at"].notna()]
        if len(voided) > 0:
            assert all(voided["voided_at"] > voided["label_created_at"])

    def test_apply_cdc_changes_voided_stops_updates(self):
        """Once voided, label should have no further updates."""
        config = load_config("config.yaml")
        config_dict = _config_to_dict(config, num_labels=100)
        base_df = generate_base_labels(config_dict)

        cdc_df = apply_cdc_changes(base_df, config_dict)

        # For each voided label, check last row has voided_at set
        voided_label_ids = cdc_df[cdc_df["voided_at"].notna()]["label_id"].unique()

        for label_id in voided_label_ids:
            rows = cdc_df[cdc_df["label_id"] == label_id].sort_values("last_updated_at")
            last_row = rows.iloc[-1]
            # Last row should have voided_at set
            assert pd.notna(last_row["voided_at"])

    def test_apply_cdc_changes_preserves_original_rows(self):
        """First row for each label should match original base label."""
        config = load_config("config.yaml")
        config_dict = _config_to_dict(config, num_labels=50)
        base_df = generate_base_labels(config_dict)

        cdc_df = apply_cdc_changes(base_df, config_dict)

        # Compare first rows
        for label_id in cdc_df["label_id"].unique():
            base_row = base_df[base_df["label_id"] == label_id].iloc[0]
            cdc_first = cdc_df[cdc_df["label_id"] == label_id].sort_values(
                "last_updated_at"
            ).iloc[0]

            # First rows should match (same ID, same created_at, etc.)
            assert base_row["label_id"] == cdc_first["label_id"]
            assert base_row["label_created_at"] == cdc_first["label_created_at"]
            assert base_row["carrier"] == cdc_first["carrier"]

    def test_apply_cdc_changes_single_change_exists(self):
        """Some labels should have exactly 2 rows (original + 1 change)."""
        config = load_config("config.yaml")
        config_dict = _config_to_dict(config, num_labels=100)
        base_df = generate_base_labels(config_dict)

        cdc_df = apply_cdc_changes(base_df, config_dict)

        # Find non-voided labels with exactly 2 rows
        two_row_non_voided = (
            cdc_df.groupby("label_id")
            .filter(lambda x: len(x) == 2 and x["voided_at"].isna().all())
        )
        single_change_ids = two_row_non_voided["label_id"].unique()

        # Verify at least some labels have single changes
        assert len(single_change_ids) > 0, "No labels with single change found"

        # Verify structure of single-change labels
        for label_id in single_change_ids[:5]:  # Check first 5 as sample
            rows = cdc_df[cdc_df["label_id"] == label_id].sort_values("last_updated_at")
            original = rows.iloc[0]
            changed = rows.iloc[1]

            # Verify same label, same creation date
            assert original["label_id"] == changed["label_id"]
            assert original["label_created_at"] == changed["label_created_at"]
            # Timestamp must advance
            assert changed["last_updated_at"] > original["last_updated_at"]
            # No voiding
            assert pd.isna(original["voided_at"])
            assert pd.isna(changed["voided_at"])

    def test_apply_cdc_changes_double_change_exists(self):
        """Some labels should have exactly 3 rows (original + 2 changes with chaining)."""
        config = load_config("config.yaml")
        config_dict = _config_to_dict(config, num_labels=100)
        base_df = generate_base_labels(config_dict)

        cdc_df = apply_cdc_changes(base_df, config_dict)

        # Find non-voided labels with exactly 3 rows
        three_row_non_voided = (
            cdc_df.groupby("label_id")
            .filter(lambda x: len(x) == 3 and x["voided_at"].isna().all())
        )
        double_change_ids = three_row_non_voided["label_id"].unique()

        # Verify at least some labels have double changes
        assert len(double_change_ids) > 0, "No labels with double change found"

        # Verify structure and chaining of double-change labels
        for label_id in double_change_ids[:5]:  # Check first 5 as sample
            rows = cdc_df[cdc_df["label_id"] == label_id].sort_values("last_updated_at")
            original = rows.iloc[0]
            first_change = rows.iloc[1]
            second_change = rows.iloc[2]

            # Verify same label throughout
            assert original["label_id"] == first_change["label_id"] == second_change["label_id"]
            assert original["label_created_at"] == first_change["label_created_at"] == second_change["label_created_at"]

            # Verify timestamps strictly ascending (CDC chaining proof)
            assert (
                original["last_updated_at"]
                < first_change["last_updated_at"]
                < second_change["last_updated_at"]
            )

            # No voiding
            assert pd.isna(original["voided_at"])
            assert pd.isna(first_change["voided_at"])
            assert pd.isna(second_change["voided_at"])

    def test_apply_cdc_changes_void_timing_split(self):
        """Void timing should be roughly 90% immediate, 10% fraud (2-5 days later)."""
        config = load_config("config.yaml")
        config_dict = _config_to_dict(config, num_labels=500)
        base_df = generate_base_labels(config_dict)

        cdc_df = apply_cdc_changes(base_df, config_dict)

        # Get voided labels and classify by timing
        voided_rows = cdc_df[cdc_df["voided_at"].notna()]

        if len(voided_rows) == 0:
            pytest.skip("No voided labels generated")

        # For each voided label, check the time delta between creation and voiding
        immediate_count = 0
        fraud_count = 0

        for label_id in voided_rows["label_id"].unique():
            rows = cdc_df[cdc_df["label_id"] == label_id].sort_values("last_updated_at")
            if len(rows) >= 2:
                created_at = rows.iloc[0]["label_created_at"]
                voided_at = rows.iloc[-1]["voided_at"]  # Last row has voided_at

                time_delta_hours = (voided_at - created_at).total_seconds() / 3600

                if time_delta_hours <= 1:
                    immediate_count += 1
                elif 48 <= time_delta_hours <= 120:  # 2-5 days
                    fraud_count += 1

        total_voided = immediate_count + fraud_count

        if total_voided > 0:
            immediate_prop = immediate_count / total_voided
            # Should be roughly 90% immediate (allow 75-99% range for statistical variance)
            assert 0.75 < immediate_prop, f"Immediate void proportion {immediate_prop:.1%} below 75%"
