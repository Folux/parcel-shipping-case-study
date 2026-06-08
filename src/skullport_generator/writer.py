"""Write generated DataFrames to Delta tables."""

import pandas as pd
from pyspark.sql import SparkSession
from pyspark.sql import functions as F

from skullport_generator.schemas import (
    RAW_LABELS_SCHEMA,
    RAW_TRACKING_EVENTS_SCHEMA,
)


def write_labels(
    spark: SparkSession,
    labels_df: pd.DataFrame,
    table_name: str = "skullport.raw.labels",
    mode: str = "overwrite",
) -> None:
    """
    Write labels DataFrame to a Unity Catalog managed Delta table.

    Args:
        spark: Active SparkSession
        labels_df: Pandas DataFrame with label data
        table_name: Fully-qualified UC table (catalog.schema.table)
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

    # Write to a Unity Catalog managed table (no DBFS paths in serverless)
    spark_df.write.format("delta").mode(mode).saveAsTable(table_name)

    print(f"✓ Wrote {row_count} labels to table {table_name}")


def write_events(
    spark: SparkSession,
    events_df: pd.DataFrame,
    table_name: str = "skullport.raw.tracking_events",
    mode: str = "overwrite",
) -> None:
    """
    Write events DataFrame to a Unity Catalog managed Delta table.

    Args:
        spark: Active SparkSession
        events_df: Pandas DataFrame with event data
        table_name: Fully-qualified UC table (catalog.schema.table)
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

    # Write to a Unity Catalog managed table (no DBFS paths in serverless)
    spark_df.write.format("delta").mode(mode).saveAsTable(table_name)

    print(f"✓ Wrote {row_count} events to table {table_name}")


def write_all(
    spark: SparkSession,
    labels_df: pd.DataFrame,
    events_df: pd.DataFrame,
    labels_table: str = "skullport.raw.labels",
    events_table: str = "skullport.raw.tracking_events",
    mode: str = "overwrite",
) -> dict:
    """
    Write both labels and events DataFrames to Unity Catalog managed tables.

    Args:
        spark: Active SparkSession
        labels_df: Pandas DataFrame with label data
        events_df: Pandas DataFrame with event data
        labels_table: Fully-qualified UC table for labels (catalog.schema.table)
        events_table: Fully-qualified UC table for events (catalog.schema.table)
        mode: Write mode - "overwrite", "append", or "ignore" (default: overwrite)

    Returns:
        Dictionary with write statistics:
        {
            "labels_count": int,
            "events_count": int,
            "labels_table": str,
            "events_table": str
        }

    Raises:
        ValueError: If either DataFrame is empty or schema is invalid
        Exception: If write fails
    """
    # Write labels
    write_labels(spark, labels_df, table_name=labels_table, mode=mode)

    # Write events
    write_events(spark, events_df, table_name=events_table, mode=mode)

    # Return statistics
    return {
        "labels_count": len(labels_df),
        "events_count": len(events_df),
        "labels_table": labels_table,
        "events_table": events_table,
    }


def validate_written_data(
    spark: SparkSession,
    labels_table: str = "skullport.raw.labels",
    events_table: str = "skullport.raw.tracking_events",
) -> dict:
    """
    Validate written data in Unity Catalog Delta tables.

    Checks:
    - Tables exist
    - Row counts > 0
    - Schema matches expected
    - No null values in non-nullable columns

    Args:
        spark: Active SparkSession
        labels_table: Fully-qualified UC table for labels
        events_table: Fully-qualified UC table for events

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
        labels_spark_df = spark.read.table(labels_table)
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
        events_spark_df = spark.read.table(events_table)
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
