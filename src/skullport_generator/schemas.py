"""PySpark schema definitions for raw.labels and raw.tracking_events Delta tables."""

from pyspark.sql.types import (
    StructType,
    StructField,
    StringType,
    IntegerType,
    TimestampType,
)


# raw.labels: Shipping labels with CDC-style updates
RAW_LABELS_SCHEMA = StructType(
    [
        StructField("label_id", StringType(), nullable=False),
        StructField("customer_id", StringType(), nullable=False),
        StructField("carrier", StringType(), nullable=False),
        StructField("service_class", StringType(), nullable=False),
        StructField("origin_zip", StringType(), nullable=False),
        StructField("dest_zip", StringType(), nullable=False),
        StructField("weight_oz", IntegerType(), nullable=False),
        StructField("declared_value_cents", IntegerType(), nullable=True),
        StructField("label_created_at", TimestampType(), nullable=False),
        StructField("carrier_promised_delivery_at", TimestampType(), nullable=False),
        StructField("voided_at", TimestampType(), nullable=True),
        StructField("last_updated_at", TimestampType(), nullable=False),
    ]
)


# raw.tracking_events: Carrier scan events as they land in the system
RAW_TRACKING_EVENTS_SCHEMA = StructType(
    [
        StructField("event_id", StringType(), nullable=False),
        StructField("label_id", StringType(), nullable=False),
        StructField("carrier", StringType(), nullable=False),
        StructField("event_code", StringType(), nullable=True),
        StructField("event_type", StringType(), nullable=True),
        StructField("event_at", StringType(), nullable=False),
        StructField("event_received_at", TimestampType(), nullable=False),
        StructField("location_zip", StringType(), nullable=True),
        StructField("raw_payload", StringType(), nullable=True),
    ]
)
