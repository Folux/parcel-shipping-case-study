"""Tests for schema definitions."""

import pytest

from pyspark.sql.types import StringType, IntegerType, TimestampType, StructType

from pirate_ship_generator.schemas import (
    RAW_LABELS_SCHEMA,
    RAW_TRACKING_EVENTS_SCHEMA,
)


def validate_schemas() -> dict[str, bool]:
    """
    Validate that schemas are defined correctly (test utility).

    Checks:
    - Both schemas are StructType objects
    - Schemas have correct number of columns
    - Schemas have correct column names and types
    - Schemas have correct nullable settings

    Returns:
        Dictionary with validation results:
        {
            "raw_labels": bool,
            "raw_tracking_events": bool,
            "all_valid": bool
        }
    """
    results = {
        "raw_labels": False,
        "raw_tracking_events": False,
    }

    # Validate raw.labels schema
    try:
        assert isinstance(RAW_LABELS_SCHEMA, StructType)
        assert len(RAW_LABELS_SCHEMA.fields) == 12
        # Check first field (label_id)
        assert RAW_LABELS_SCHEMA.fields[0].name == "label_id"
        assert RAW_LABELS_SCHEMA.fields[0].nullable is False
        # Check nullable field (declared_value_cents)
        assert RAW_LABELS_SCHEMA.fields[7].name == "declared_value_cents"
        assert RAW_LABELS_SCHEMA.fields[7].nullable is True
        # Check last field (last_updated_at)
        assert RAW_LABELS_SCHEMA.fields[11].name == "last_updated_at"
        assert RAW_LABELS_SCHEMA.fields[11].nullable is False
        results["raw_labels"] = True
    except AssertionError:
        results["raw_labels"] = False

    # Validate raw.tracking_events schema
    try:
        assert isinstance(RAW_TRACKING_EVENTS_SCHEMA, StructType)
        assert len(RAW_TRACKING_EVENTS_SCHEMA.fields) == 9
        # Check first field (event_id)
        assert RAW_TRACKING_EVENTS_SCHEMA.fields[0].name == "event_id"
        assert RAW_TRACKING_EVENTS_SCHEMA.fields[0].nullable is False
        # Check nullable fields (event_code, event_type)
        assert RAW_TRACKING_EVENTS_SCHEMA.fields[3].name == "event_code"
        assert RAW_TRACKING_EVENTS_SCHEMA.fields[3].nullable is True
        assert RAW_TRACKING_EVENTS_SCHEMA.fields[4].name == "event_type"
        assert RAW_TRACKING_EVENTS_SCHEMA.fields[4].nullable is True
        # Check last field (raw_payload)
        assert RAW_TRACKING_EVENTS_SCHEMA.fields[8].name == "raw_payload"
        assert RAW_TRACKING_EVENTS_SCHEMA.fields[8].nullable is True
        results["raw_tracking_events"] = True
    except AssertionError:
        results["raw_tracking_events"] = False

    results["all_valid"] = results["raw_labels"] and results["raw_tracking_events"]
    return results


# ============================================================================
# TESTS
# ============================================================================


class TestRawLabelsSchema:
    """Test raw.labels schema definition."""

    def test_schema_is_struct_type(self):
        """Schema should be a StructType."""
        assert isinstance(RAW_LABELS_SCHEMA, StructType)

    def test_schema_has_12_fields(self):
        """raw.labels should have exactly 12 fields."""
        assert len(RAW_LABELS_SCHEMA.fields) == 12

    def test_field_names(self):
        """Schema should have correct field names in order."""
        expected_names = [
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
        ]
        actual_names = [f.name for f in RAW_LABELS_SCHEMA.fields]
        assert actual_names == expected_names

    def test_field_types(self):
        """Schema should have correct field types."""
        field_types = {f.name: type(f.dataType).__name__ for f in RAW_LABELS_SCHEMA.fields}

        assert field_types["label_id"] == "StringType"
        assert field_types["customer_id"] == "StringType"
        assert field_types["carrier"] == "StringType"
        assert field_types["service_class"] == "StringType"
        assert field_types["origin_zip"] == "StringType"
        assert field_types["dest_zip"] == "StringType"
        assert field_types["weight_oz"] == "IntegerType"
        assert field_types["declared_value_cents"] == "IntegerType"
        assert field_types["label_created_at"] == "TimestampType"
        assert field_types["carrier_promised_delivery_at"] == "TimestampType"
        assert field_types["voided_at"] == "TimestampType"
        assert field_types["last_updated_at"] == "TimestampType"

    def test_nullable_fields(self):
        """Schema should have correct nullable settings."""
        field_nullable = {f.name: f.nullable for f in RAW_LABELS_SCHEMA.fields}

        # Non-nullable fields
        assert field_nullable["label_id"] is False
        assert field_nullable["customer_id"] is False
        assert field_nullable["carrier"] is False
        assert field_nullable["service_class"] is False
        assert field_nullable["origin_zip"] is False
        assert field_nullable["dest_zip"] is False
        assert field_nullable["weight_oz"] is False
        assert field_nullable["label_created_at"] is False
        assert field_nullable["carrier_promised_delivery_at"] is False
        assert field_nullable["last_updated_at"] is False

        # Nullable fields
        assert field_nullable["declared_value_cents"] is True
        assert field_nullable["voided_at"] is True


class TestRawTrackingEventsSchema:
    """Test raw.tracking_events schema definition."""

    def test_schema_is_struct_type(self):
        """Schema should be a StructType."""
        assert isinstance(RAW_TRACKING_EVENTS_SCHEMA, StructType)

    def test_schema_has_9_fields(self):
        """raw.tracking_events should have exactly 9 fields."""
        assert len(RAW_TRACKING_EVENTS_SCHEMA.fields) == 9

    def test_field_names(self):
        """Schema should have correct field names in order."""
        expected_names = [
            "event_id",
            "label_id",
            "carrier",
            "event_code",
            "event_type",
            "event_at",
            "event_received_at",
            "location_zip",
            "raw_payload",
        ]
        actual_names = [f.name for f in RAW_TRACKING_EVENTS_SCHEMA.fields]
        assert actual_names == expected_names

    def test_field_types(self):
        """Schema should have correct field types."""
        field_types = {f.name: type(f.dataType).__name__ for f in RAW_TRACKING_EVENTS_SCHEMA.fields}

        assert field_types["event_id"] == "StringType"
        assert field_types["label_id"] == "StringType"
        assert field_types["carrier"] == "StringType"
        assert field_types["event_code"] == "StringType"
        assert field_types["event_type"] == "StringType"
        assert field_types["event_at"] == "StringType"  # Kept as STRING for raw fidelity
        assert field_types["event_received_at"] == "TimestampType"
        assert field_types["location_zip"] == "StringType"
        assert field_types["raw_payload"] == "StringType"

    def test_nullable_fields(self):
        """Schema should have correct nullable settings."""
        field_nullable = {f.name: f.nullable for f in RAW_TRACKING_EVENTS_SCHEMA.fields}

        # Non-nullable fields
        assert field_nullable["event_id"] is False
        assert field_nullable["label_id"] is False
        assert field_nullable["carrier"] is False
        assert field_nullable["event_at"] is False
        assert field_nullable["event_received_at"] is False

        # Nullable fields
        assert field_nullable["event_code"] is True
        assert field_nullable["event_type"] is True
        assert field_nullable["location_zip"] is True
        assert field_nullable["raw_payload"] is True


class TestValidateSchemas:
    """Test schema validation function."""

    def test_validate_schemas_returns_dict(self):
        """validate_schemas should return a dictionary."""
        result = validate_schemas()
        assert isinstance(result, dict)

    def test_validate_schemas_has_expected_keys(self):
        """Validation result should have expected keys."""
        result = validate_schemas()
        assert "raw_labels" in result
        assert "raw_tracking_events" in result
        assert "all_valid" in result

    def test_validate_schemas_all_valid(self):
        """Both schemas should be valid."""
        result = validate_schemas()
        assert result["raw_labels"] is True
        assert result["raw_tracking_events"] is True
        assert result["all_valid"] is True

    def test_validate_schemas_returns_booleans(self):
        """All validation results should be booleans."""
        result = validate_schemas()
        assert isinstance(result["raw_labels"], bool)
        assert isinstance(result["raw_tracking_events"], bool)
        assert isinstance(result["all_valid"], bool)


class TestSchemas:
    """Test that all schemas are valid per specification."""

    def test_schemas_are_valid(self):
        """All schemas should match specification exactly."""
        result = validate_schemas()
        assert result["all_valid"] is True
