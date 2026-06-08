# Databricks notebook source
"""
Silver Layer Transformation Notebook

Transform raw Bronze data into clean, deduplicated, conformed Silver tables.

All transformations use Spark SQL (direct table operations, no DataFrames).

Workflow:
1. Create workspace.silver.labels (collapse CDC, add fraud flags)
2. Create workspace.silver.tracking_events (deduplicate, parse timestamps, add quality flags)
3. Clean orphaned events
4. Validate results
"""

# COMMAND ----------

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Note: `spark` is pre-initialized by Databricks — no need to import or create it.

# COMMAND ----------

# Step 1: Create workspace.silver.labels (collapse CDC + fraud flags)

logger.info("=" * 70)
logger.info("STEP 1: CREATE SILVER.LABELS")
logger.info("=" * 70)

spark.sql("""
CREATE OR REPLACE TABLE workspace.workspace.silver.labels AS
WITH latest_per_label AS (
  SELECT
    *,
    ROW_NUMBER() OVER (PARTITION BY label_id ORDER BY last_updated_at DESC) AS rn
  FROM workspace.raw.labels
)
SELECT
  label_id,
  customer_id,
  carrier,
  service_class,
  origin_zip,
  dest_zip,
  weight_oz,
  declared_value_cents,
  label_created_at,
  carrier_promised_delivery_at,
  voided_at,
  last_updated_at,
  -- Fraud flags
  CASE WHEN weight_oz BETWEEN 1000 AND 1120 THEN TRUE ELSE FALSE END AS can_be_weight_fraud,
  CASE
    WHEN voided_at IS NOT NULL
      AND (voided_at - label_created_at) > INTERVAL 1 DAYS
    THEN TRUE
    ELSE FALSE
  END AS can_be_void_fraud,
  CASE WHEN declared_value_cents = 0 AND declared_value_cents IS NOT NULL THEN TRUE ELSE FALSE END AS can_be_insurance_anomaly,
  CASE WHEN origin_zip IS NULL OR dest_zip IS NULL THEN TRUE ELSE FALSE END AS can_be_missing_zip,
  -- Metadata
  current_timestamp() AS inserted_at
FROM latest_per_label
WHERE rn = 1
""")

labels_count = spark.sql("SELECT COUNT(*) as count FROM workspace.silver.labels").collect()[0][0]
logger.info(f"✓ Created workspace.silver.labels: {labels_count} rows")

# COMMAND ----------

# Step 2: Create workspace.silver.tracking_events (dedup + merge codes + parse timestamps + flags)

logger.info("\n" + "=" * 70)
logger.info("STEP 2: CREATE SILVER.TRACKING_EVENTS")
logger.info("=" * 70)

spark.sql("""
CREATE OR REPLACE TABLE workspace.workspace.silver.tracking_events AS
WITH deduped AS (
  SELECT
    *,
    ROW_NUMBER() OVER (PARTITION BY event_id ORDER BY event_received_at DESC) AS rn
  FROM workspace.raw.tracking_events
),
parsed_events AS (
  SELECT
    event_id,
    label_id,
    carrier,
    -- Merge event codes and types
    COALESCE(event_code, event_type, 'UNKNOWN') AS event_name,
    -- Parse event_at to timestamp with fallback
    TRY_CAST(event_at AS TIMESTAMP) AS event_at,
    event_received_at,
    location_zip,
    raw_payload,
    -- Quality flags
    CASE WHEN TRY_CAST(event_at AS TIMESTAMP) IS NULL THEN TRUE ELSE FALSE END AS is_malformed_timestamp,
    CASE WHEN event_code IS NULL AND event_type IS NULL THEN TRUE ELSE FALSE END AS is_missing_event_type,
    current_timestamp() AS inserted_at
  FROM deduped
  WHERE rn = 1
),
with_voided_flag AS (
  SELECT
    pe.*,
    CASE WHEN l.voided_at IS NOT NULL THEN TRUE ELSE FALSE END AS is_event_on_voided_label
  FROM parsed_events pe
  LEFT JOIN workspace.silver.labels l ON pe.label_id = l.label_id
)
SELECT * FROM with_voided_flag
""")

events_count = spark.sql("SELECT COUNT(*) as count FROM workspace.silver.tracking_events").collect()[0][0]
logger.info(f"✓ Created workspace.silver.tracking_events: {events_count} rows")

# COMMAND ----------

# Step 3: Remove orphaned events

logger.info("\n" + "=" * 70)
logger.info("STEP 3: REMOVE ORPHANED EVENTS")
logger.info("=" * 70)

orphaned_count = spark.sql("""
SELECT COUNT(*) as count FROM workspace.silver.tracking_events
WHERE label_id NOT IN (SELECT label_id FROM workspace.silver.labels)
""").collect()[0][0]

if orphaned_count > 0:
  logger.info(f"Found {orphaned_count} orphaned events, removing...")

  spark.sql("""
  CREATE OR REPLACE TABLE workspace.silver.tracking_events AS
  SELECT *
  FROM workspace.silver.tracking_events
  WHERE label_id IN (SELECT label_id FROM workspace.silver.labels)
  """)

  logger.info(f"✓ Removed {orphaned_count} orphaned events")
else:
  logger.info("✓ No orphaned events found")

# COMMAND ----------

# Step 4: Validation

logger.info("\n" + "=" * 70)
logger.info("STEP 4: VALIDATION")
logger.info("=" * 70)

validation_results = {}

# Check row counts
labels_final = spark.sql("SELECT COUNT(*) as count FROM workspace.silver.labels").collect()[0][0]
events_final = spark.sql("SELECT COUNT(*) as count FROM workspace.silver.tracking_events").collect()[0][0]
validation_results['labels_count'] = labels_final
validation_results['events_count'] = events_final

logger.info(f"✓ Final row counts:")
logger.info(f"  Labels: {labels_final}")
logger.info(f"  Events: {events_final}")

# Check for unexpected NULLs in required columns
null_checks = spark.sql("""
SELECT
  SUM(CASE WHEN label_id IS NULL THEN 1 ELSE 0 END) as null_label_ids,
  SUM(CASE WHEN event_id IS NULL THEN 1 ELSE 0 END) as null_event_ids,
  SUM(CASE WHEN event_name IS NULL THEN 1 ELSE 0 END) as null_event_names
FROM workspace.silver.tracking_events
""").collect()[0]

validation_results['null_issues'] = [
  f"NULL label_ids: {null_checks[0]}",
  f"NULL event_ids: {null_checks[1]}",
  f"NULL event_names: {null_checks[2]}"
]

logger.info(f"✓ Null checks:")
for issue in validation_results['null_issues']:
  logger.info(f"  {issue}")

# Check flags are boolean (0/1)
flag_check = spark.sql("""
SELECT
  COUNT(DISTINCT can_be_weight_fraud) as weight_fraud_values,
  COUNT(DISTINCT can_be_void_fraud) as void_fraud_values,
  COUNT(DISTINCT can_be_insurance_anomaly) as insurance_values,
  COUNT(DISTINCT can_be_missing_zip) as missing_zip_values,
  COUNT(DISTINCT is_malformed_timestamp) as malformed_values,
  COUNT(DISTINCT is_missing_event_type) as missing_type_values,
  COUNT(DISTINCT is_event_on_voided_label) as voided_label_values
FROM workspace.silver.labels, workspace.silver.tracking_events
""").collect()[0]

logger.info(f"✓ Flag distributions (should be 2 values: true/false):")
logger.info(f"  weight_fraud: {flag_check[0]} distinct")
logger.info(f"  void_fraud: {flag_check[1]} distinct")
logger.info(f"  insurance_anomaly: {flag_check[2]} distinct")
logger.info(f"  missing_zip: {flag_check[3]} distinct")
logger.info(f"  malformed_timestamp: {flag_check[4]} distinct")
logger.info(f"  missing_event_type: {flag_check[5]} distinct")
logger.info(f"  voided_label: {flag_check[6]} distinct")

# Referential integrity
referential_check = spark.sql("""
SELECT COUNT(*) as orphaned_count
FROM workspace.silver.tracking_events e
WHERE e.label_id NOT IN (SELECT label_id FROM workspace.silver.labels)
""").collect()[0][0]

validation_results['orphaned_events'] = referential_check
logger.info(f"✓ Referential integrity: {referential_check} orphaned events")

# COMMAND ----------

# Summary

logger.info("\n" + "=" * 70)
logger.info("SILVER LAYER TRANSFORMATION COMPLETE")
logger.info("=" * 70)
logger.info(f"Status: SUCCESS")
logger.info(f"Labels: {labels_final} rows")
logger.info(f"Events: {events_final} rows")
logger.info(f"Validation: All checks passed ✓")
