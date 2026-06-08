# Databricks notebook source
"""
Pirate Ship Synthetic Data Generator - Databricks Notebook Wrapper

Generates synthetic parcel shipping data for the Delivery Performance Mart
case study and writes it to the Bronze layer as Unity Catalog managed tables:
  - <catalog>.<schema>.labels           (shipping labels with CDC-style updates)
  - <catalog>.<schema>.tracking_events  (carrier tracking events)

The target catalog/schema is configured in config.yaml.

Usage:
  1. Clone this repo into Databricks as a Git folder
  2. (Optional) Edit config.yaml or the config_path widget
  3. Run all cells
"""

# COMMAND ----------

# Add the package source to the Python path.
# `spark` is injected automatically by Databricks — do not create a new session.
import sys
import os

sys.path.insert(0, os.path.abspath("../src"))

# COMMAND ----------

import logging

from skullport_generator.main import main

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# COMMAND ----------

dbutils.widgets.text("config_path", "../config.yaml", label="Config File Path")
config_path = dbutils.widgets.get("config_path")

# COMMAND ----------

# Run the generation pipeline
result = main(config_path, spark=spark)

print(f"Status:        {result['status']}")
print(f"Bronze Labels: {result.get('labels_count', 'error')} rows")
print(f"Bronze Events: {result.get('events_count', 'error')} rows")
print(f"Message:       {result.get('message', result.get('error_type', 'unknown'))}")

# COMMAND ----------

# Verify the written tables
if result["status"] in ("success", "success_with_warnings"):
    labels_table = result["labels_table"]
    events_table = result["events_table"]

    labels_df = spark.read.table(labels_table)
    logger.info(f"✓ {labels_table}: {labels_df.count()} rows")
    display(labels_df.limit(5))

    events_df = spark.read.table(events_table)
    logger.info(f"✓ {events_table}: {events_df.count()} rows")
    display(events_df.limit(10))
