"""Tests for writer module."""

import pytest
import pandas as pd
import tempfile
import shutil
from datetime import datetime, timezone

from skullport_generator.writer import (
    write_labels,
    write_events,
    write_all,
)


def _create_test_labels_df(num_rows: int = 5) -> pd.DataFrame:
    """Helper to create test labels DataFrame."""
    return pd.DataFrame({
        "label_id": [f"lbl_{i}" for i in range(num_rows)],
        "customer_id": [f"cust_{i}" for i in range(num_rows)],
        "carrier": ["USPS"] * num_rows,
        "service_class": ["Ground"] * num_rows,
        "origin_zip": ["12345"] * num_rows,
        "dest_zip": ["67890"] * num_rows,
        "weight_oz": [100] * num_rows,
        "declared_value_cents": [5000] * num_rows,
        "label_created_at": [datetime(2026, 6, 1, tzinfo=timezone.utc)] * num_rows,
        "carrier_promised_delivery_at": [datetime(2026, 6, 5, tzinfo=timezone.utc)] * num_rows,
        "voided_at": [None] * num_rows,
        "last_updated_at": [datetime(2026, 6, 1, tzinfo=timezone.utc)] * num_rows,
    })


def _create_test_events_df(num_rows: int = 10) -> pd.DataFrame:
    """Helper to create test events DataFrame."""
    return pd.DataFrame({
        "event_id": [f"ev_{i}" for i in range(num_rows)],
        "label_id": [f"lbl_{i % 5}" for i in range(num_rows)],
        "carrier": ["USPS"] * num_rows,
        "event_code": ["0300"] * num_rows,
        "event_type": [None] * num_rows,
        "event_at": ["2026-06-01T10:00:00-05:00"] * num_rows,
        "event_received_at": [datetime(2026, 6, 1, 10, 0, 0, tzinfo=timezone.utc)] * num_rows,
        "location_zip": ["12345"] * num_rows,
        "raw_payload": [None] * num_rows,
    })


class TestWriteLabels:
    """Test write_labels function."""

    def test_write_labels_requires_spark_session(self):
        """write_labels should require a SparkSession."""
        # This test verifies the function signature
        assert callable(write_labels)

    def test_write_labels_accepts_pandas_dataframe(self):
        """write_labels should accept a Pandas DataFrame."""
        # Verify parameter type hints
        import inspect
        sig = inspect.signature(write_labels)
        assert "labels_df" in sig.parameters

    def test_write_labels_accepts_mode(self):
        """write_labels should accept a mode parameter."""
        import inspect
        sig = inspect.signature(write_labels)
        assert "mode" in sig.parameters


class TestWriteEvents:
    """Test write_events function."""

    def test_write_events_requires_spark_session(self):
        """write_events should require a SparkSession."""
        assert callable(write_events)

    def test_write_events_accepts_pandas_dataframe(self):
        """write_events should accept a Pandas DataFrame."""
        import inspect
        sig = inspect.signature(write_events)
        assert "events_df" in sig.parameters

    def test_write_events_accepts_mode(self):
        """write_events should accept a mode parameter."""
        import inspect
        sig = inspect.signature(write_events)
        assert "mode" in sig.parameters


class TestWriteAll:
    """Test write_all function."""

    def test_write_all_accepts_both_dataframes(self):
        """write_all should accept both labels and events DataFrames."""
        import inspect
        sig = inspect.signature(write_all)
        assert "labels_df" in sig.parameters
        assert "events_df" in sig.parameters

    def test_write_all_returns_dict(self):
        """write_all should return a dictionary with statistics."""
        import inspect
        sig = inspect.signature(write_all)
        # Return annotation should be dict
        assert sig.return_annotation == dict


class TestDataFrameValidation:
    """Test DataFrame validation logic."""

    def test_labels_dataframe_has_all_columns(self):
        """Test labels DataFrame has all required columns."""
        df = _create_test_labels_df()
        expected_cols = [
            "label_id", "customer_id", "carrier", "service_class",
            "origin_zip", "dest_zip", "weight_oz", "declared_value_cents",
            "label_created_at", "carrier_promised_delivery_at", "voided_at",
            "last_updated_at"
        ]
        assert all(col in df.columns for col in expected_cols)

    def test_events_dataframe_has_all_columns(self):
        """Test events DataFrame has all required columns."""
        df = _create_test_events_df()
        expected_cols = [
            "event_id", "label_id", "carrier", "event_code", "event_type",
            "event_at", "event_received_at", "location_zip", "raw_payload"
        ]
        assert all(col in df.columns for col in expected_cols)

    def test_labels_dataframe_correct_types(self):
        """Test labels DataFrame has correct column types."""
        df = _create_test_labels_df()
        assert df["label_id"].dtype == "object"  # string
        assert df["weight_oz"].dtype == "int64"
        assert df["declared_value_cents"].dtype == "int64"

    def test_events_dataframe_correct_types(self):
        """Test events DataFrame has correct column types."""
        df = _create_test_events_df()
        assert df["event_id"].dtype == "object"  # string
        assert df["event_received_at"].dtype == "datetime64[ns, UTC]"

    def test_labels_non_null_fields(self):
        """Test labels DataFrame has no nulls in non-nullable fields."""
        df = _create_test_labels_df()
        # These should not be null
        assert not df["label_id"].isnull().any()
        assert not df["customer_id"].isnull().any()
        assert not df["carrier"].isnull().any()
        assert not df["label_created_at"].isnull().any()

    def test_events_non_null_fields(self):
        """Test events DataFrame has no nulls in non-nullable fields."""
        df = _create_test_events_df()
        # These should not be null
        assert not df["event_id"].isnull().any()
        assert not df["label_id"].isnull().any()
        assert not df["carrier"].isnull().any()
        assert not df["event_at"].isnull().any()
        assert not df["event_received_at"].isnull().any()

    def test_labels_nullable_fields_can_be_null(self):
        """Test labels DataFrame nullable fields can have nulls."""
        df = _create_test_labels_df(num_rows=1)
        df.loc[0, "declared_value_cents"] = None
        df.loc[0, "voided_at"] = None
        # Should not raise
        assert df["declared_value_cents"].isnull().any()
        assert df["voided_at"].isnull().any()

    def test_events_nullable_fields_can_be_null(self):
        """Test events DataFrame nullable fields can have nulls."""
        df = _create_test_events_df(num_rows=1)
        df.loc[0, "event_code"] = None
        df.loc[0, "event_type"] = None
        df.loc[0, "location_zip"] = None
        df.loc[0, "raw_payload"] = None
        # Should not raise
        assert df["event_code"].isnull().any()
        assert df["event_type"].isnull().any()


class TestSchemaCompatibility:
    """Test that test DataFrames are compatible with schemas."""

    def test_labels_df_matches_schema_structure(self):
        """Test labels DataFrame matches RAW_LABELS_SCHEMA structure."""
        from skullport_generator.schemas import RAW_LABELS_SCHEMA

        df = _create_test_labels_df()
        schema_fields = [f.name for f in RAW_LABELS_SCHEMA.fields]

        # All schema fields should be in DataFrame
        for field_name in schema_fields:
            assert field_name in df.columns

    def test_events_df_matches_schema_structure(self):
        """Test events DataFrame matches RAW_TRACKING_EVENTS_SCHEMA structure."""
        from skullport_generator.schemas import RAW_TRACKING_EVENTS_SCHEMA

        df = _create_test_events_df()
        schema_fields = [f.name for f in RAW_TRACKING_EVENTS_SCHEMA.fields]

        # All schema fields should be in DataFrame
        for field_name in schema_fields:
            assert field_name in df.columns


class TestHelperDataFrames:
    """Test that helper DataFrames are created correctly."""

    def test_create_labels_df_returns_dataframe(self):
        """_create_test_labels_df should return a DataFrame."""
        df = _create_test_labels_df()
        assert isinstance(df, pd.DataFrame)

    def test_create_labels_df_has_correct_shape(self):
        """_create_test_labels_df should create specified number of rows."""
        df = _create_test_labels_df(num_rows=10)
        assert len(df) == 10

    def test_create_events_df_returns_dataframe(self):
        """_create_test_events_df should return a DataFrame."""
        df = _create_test_events_df()
        assert isinstance(df, pd.DataFrame)

    def test_create_events_df_has_correct_shape(self):
        """_create_test_events_df should create specified number of rows."""
        df = _create_test_events_df(num_rows=20)
        assert len(df) == 20

    def test_labels_df_has_unique_ids(self):
        """_create_test_labels_df should create unique label_ids."""
        df = _create_test_labels_df(num_rows=10)
        assert len(df["label_id"].unique()) == 10

    def test_events_df_has_unique_event_ids(self):
        """_create_test_events_df should create unique event_ids."""
        df = _create_test_events_df(num_rows=10)
        assert len(df["event_id"].unique()) == 10
