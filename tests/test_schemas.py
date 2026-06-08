"""Contract tests for the Bronze output schemas (skullport_generator.schemas).

These guard the data contract the rest of the pipeline depends on: column
names/order, the deliberate decision to keep event_at as STRING, and the
nullability that encodes schema drift.
"""

from skullport_generator.schemas import (
    RAW_LABELS_SCHEMA,
    RAW_TRACKING_EVENTS_SCHEMA,
)


def _names(schema):
    return [f.name for f in schema.fields]


def _nullable(schema):
    return {f.name: f.nullable for f in schema.fields}


def _type(schema, field):
    return type(next(f for f in schema.fields if f.name == field).dataType).__name__


def test_labels_schema_contract():
    assert _names(RAW_LABELS_SCHEMA) == [
        "label_id", "customer_id", "carrier", "service_class", "origin_zip",
        "dest_zip", "weight_oz", "declared_value_cents", "label_created_at",
        "carrier_promised_delivery_at", "voided_at", "last_updated_at",
    ]
    nullable = _nullable(RAW_LABELS_SCHEMA)
    # Only the optional business fields may be null.
    assert nullable["declared_value_cents"] and nullable["voided_at"]
    assert not nullable["label_id"] and not nullable["carrier"]


def test_events_schema_contract():
    assert _names(RAW_TRACKING_EVENTS_SCHEMA) == [
        "event_id", "label_id", "carrier", "event_code", "event_type",
        "event_at", "event_received_at", "location_zip", "raw_payload",
    ]
    # event_at stays STRING in Bronze (raw carrier fidelity; parsed in Silver).
    assert _type(RAW_TRACKING_EVENTS_SCHEMA, "event_at") == "StringType"
    nullable = _nullable(RAW_TRACKING_EVENTS_SCHEMA)
    # Schema drift: a carrier supplies code OR type, so both are nullable.
    assert nullable["event_code"] and nullable["event_type"]
    assert not nullable["event_id"] and not nullable["event_received_at"]
