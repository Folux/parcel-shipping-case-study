# Databricks notebook source
"""
Pirate Ship Synthetic Data Generator - Databricks Notebook Wrapper

This notebook orchestrates the generation of synthetic parcel shipping data
for the Delivery Performance Mart case study. It generates both:
1. raw.labels: Shipping labels with CDC-style updates (voiding, field changes)
2. raw.tracking_events: Carrier tracking events with realistic data quality issues

The generated data includes:
- Normal labels with complete event sequences
- Voided labels (voided early or due to fraud)
- Incomplete sequences (stuck in transit)
- Data quality issues: duplicates, late arrivals, missing fields, malformed timestamps,
  timezone weirdness, out-of-order events

Usage:
  1. Install this notebook in your Databricks workspace
  2. (Optional) Update the config_path widget to point to your config file
  3. Run all cells
  4. Check Delta tables in your configured location
"""

# COMMAND ----------

# Add source directory to path (no pip install needed)
import sys
import os

# Databricks repo path - adjust if your clone path is different
# Standard clone: /Workspace/Repos/{username}/parcel-shipping-case-study
notebook_path = dbutils.notebook.entry_point.get_notebook_path()
repo_root = "/".join(notebook_path.split("/")[:-2])  # Go up from /notebooks/pirate_ship_generator.py
src_path = f"{repo_root}/src"

print(f"Adding to Python path: {src_path}")
sys.path.insert(0, src_path)

# COMMAND ----------

# Standard library imports
import logging

# Third-party imports
from pyspark.sql import SparkSession

# Local imports
from pirate_ship_generator.main import main

# COMMAND ----------

# Configure logging for better visibility
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# COMMAND ----------

# Define notebook widgets for configuration
dbutils.widgets.text(
    "config_path",
    "config.yaml",
    label="Config File Path"
)
dbutils.widgets.text(
    "labels_path",
    "/mnt/bronze/labels",
    label="Bronze Labels Table Path"
)
dbutils.widgets.text(
    "events_path",
    "/mnt/bronze/tracking_events",
    label="Bronze Events Table Path"
)

# COMMAND ----------

# Read widget values
config_path = dbutils.widgets.get("config_path")
labels_path = dbutils.widgets.get("labels_path")
events_path = dbutils.widgets.get("events_path")

logger.info(f"Configuration:")
logger.info(f"  config_path: {config_path}")
logger.info(f"  labels_path: {labels_path}")
logger.info(f"  events_path: {events_path}")

# COMMAND ----------

# Run the main orchestration
logger.info("=" * 70)
logger.info("STARTING PIRATE SHIP SYNTHETIC DATA GENERATION")
logger.info("=" * 70)

result = main(config_path)

# COMMAND ----------

# Display results
logger.info("=" * 70)
logger.info("BRONZE LAYER GENERATION COMPLETE")
logger.info("=" * 70)

print(f"Status: {result['status']}")
print(f"Bronze Labels: {result.get('labels_count', 'error')} rows")
print(f"Bronze Events: {result.get('events_count', 'error')} rows")
print(f"Message: {result.get('message', result.get('error_type', 'unknown'))}")
print("\nNext step: Implement Silver layer transformations")

# COMMAND ----------

# Display full result for debugging
display(result)

# COMMAND ----------

# Optional: Verify tables exist and show schema
if result['status'] in ['success', 'success_with_warnings']:
    logger.info("Verifying generated tables...")

    spark = SparkSession.builder.appName("verify").getOrCreate()

    try:
        labels_df = spark.read.format("delta").load(labels_path)
        logger.info(f"✓ Labels table exists: {labels_df.count()} rows")
        display(labels_df.head(5))
    except Exception as e:
        logger.error(f"Could not read labels table: {e}")

    try:
        events_df = spark.read.format("delta").load(events_path)
        logger.info(f"✓ Events table exists: {events_df.count()} rows")
        display(events_df.head(10))
    except Exception as e:
        logger.error(f"Could not read events table: {e}")
