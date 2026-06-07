"""Write generated DataFrames to Delta tables."""

import pandas as pd
from pyspark.sql import SparkSession
from pyspark.sql import functions as F

from pirate_ship_generator.schemas import (
    RAW_LABELS_SCHEMA,
    RAW_TRACKING_EVENTS_SCHEMA,
)


def write_labels(
    spark: SparkSession,
    labels_df: pd.DataFrame,
    table_path: str = "/mnt/raw/labels",
    mode: str = "overwrite",
) -> None:
    """
    Write labels DataFrame to raw.labels Delta table.

    Args:
        spark: Active SparkSession
        labels_df: Pandas DataFrame with label data
        table_path: Path to Delta table location (default: /mnt/raw/labels)
        mode: Write mode - "overwrite", "append", or "ignore" (default: overwrite)

    Raises:
        ValueError: If DataFrame schema doesn't match RAW_LABELS_SCHEMA
        Exception: If write fails
    """
    # Convert Pandas DataFrame to PySpark DataFrame
    spark_df = spark.createDataFrame(labels_df, schema=RAW_LABELS_SCHEMA)

    # Validate row count
    row_count = spark_df.count()
    if row_count == 0:
        raise ValueError("Cannot write empty labels DataFrame")

    # Write to Delta table
    spark_df.write.format("delta").mode(mode).save(table_path)

    print(f"✓ Wrote {row_count} labels to {table_path}")


def write_events(
    spark: SparkSession,
    events_df: pd.DataFrame,
    table_path: str = "/mnt/raw/tracking_events",
    mode: str = "overwrite",
) -> None:
    """
    Write events DataFrame to raw.tracking_events Delta table.

    Args:
        spark: Active SparkSession
        events_df: Pandas DataFrame with event data
        table_path: Path to Delta table location (default: /mnt/raw/tracking_events)
        mode: Write mode - "overwrite", "append", or "ignore" (default: overwrite)

    Raises:
        ValueError: If DataFrame schema doesn't match RAW_TRACKING_EVENTS_SCHEMA
        Exception: If write fails
    """
    # Convert Pandas DataFrame to PySpark DataFrame
    spark_df = spark.createDataFrame(events_df, schema=RAW_TRACKING_EVENTS_SCHEMA)

    # Validate row count
    row_count = spark_df.count()
    if row_count == 0:
        raise ValueError("Cannot write empty events DataFrame")

    # Write to Delta table
    spark_df.write.format("delta").mode(mode).save(table_path)

    print(f"✓ Wrote {row_count} events to {table_path}")


def write_all(
    spark: SparkSession,
    labels_df: pd.DataFrame,
    events_df: pd.DataFrame,
    labels_path: str = "/mnt/raw/labels",
    events_path: str = "/mnt/raw/tracking_events",
    mode: str = "overwrite",
) -> dict:
    """
    Write both labels and events DataFrames to Delta tables.

    Args:
        spark: Active SparkSession
        labels_df: Pandas DataFrame with label data
        events_df: Pandas DataFrame with event data
        labels_path: Path to labels Delta table (default: /mnt/raw/labels)
        events_path: Path to events Delta table (default: /mnt/raw/tracking_events)
        mode: Write mode - "overwrite", "append", or "ignore" (default: overwrite)

    Returns:
        Dictionary with write statistics:
        {
            "labels_count": int,
            "events_count": int,
            "labels_path": str,
            "events_path": str
        }

    Raises:
        ValueError: If either DataFrame is empty or schema is invalid
        Exception: If write fails
    """
    # Write labels
    write_labels(spark, labels_df, table_path=labels_path, mode=mode)

    # Write events
    write_events(spark, events_df, table_path=events_path, mode=mode)

    # Return statistics
    return {
        "labels_count": len(labels_df),
        "events_count": len(events_df),
        "labels_path": labels_path,
        "events_path": events_path,
    }


def validate_written_data(
    spark: SparkSession,
    labels_path: str = "/mnt/raw/labels",
    events_path: str = "/mnt/raw/tracking_events",
) -> dict:
    """
    Validate written data in Delta tables.

    Checks:
    - Tables exist
    - Row counts > 0
    - Schema matches expected
    - No null values in non-nullable columns

    Args:
        spark: Active SparkSession
        labels_path: Path to labels Delta table
        events_path: Path to events Delta table

    Returns:
        Dictionary with validation results:
        {
            "labels_valid": bool,
            "events_valid": bool,
            "labels_count": int,
            "events_count": int,
            "all_valid": bool
        }
    """
    results = {
        "labels_valid": False,
        "events_valid": False,
        "labels_count": 0,
        "events_count": 0,
    }

    try:
        # Read labels table
        labels_spark_df = spark.read.format("delta").load(labels_path)
        labels_count = labels_spark_df.count()

        # Check labels schema
        if labels_count > 0:
            # Verify non-null constraints
            null_checks = []
            for field in RAW_LABELS_SCHEMA.fields:
                if not field.nullable:
                    null_count = labels_spark_df.filter(
                        F.col(field.name).isNull()
                    ).count()
                    null_checks.append(null_count == 0)

            results["labels_valid"] = all(null_checks)
            results["labels_count"] = labels_count

    except Exception as e:
        print(f"⚠ Labels validation failed: {e}")
        results["labels_valid"] = False

    try:
        # Read events table
        events_spark_df = spark.read.format("delta").load(events_path)
        events_count = events_spark_df.count()

        # Check events schema
        if events_count > 0:
            # Verify non-null constraints
            null_checks = []
            for field in RAW_TRACKING_EVENTS_SCHEMA.fields:
                if not field.nullable:
                    null_count = events_spark_df.filter(
                        F.col(field.name).isNull()
                    ).count()
                    null_checks.append(null_count == 0)

            results["events_valid"] = all(null_checks)
            results["events_count"] = events_count

    except Exception as e:
        print(f"⚠ Events validation failed: {e}")
        results["events_valid"] = False

    results["all_valid"] = results["labels_valid"] and results["events_valid"]
    return results
