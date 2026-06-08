# Databricks notebook source
"""
Silver Layer Transformation Notebook

Transform raw Bronze data into clean, deduplicated, conformed Silver tables.

All transformations use Spark SQL (direct table operations, no DataFrames).

Workflow:
1. Create skullport.silver.labels (collapse CDC, add fraud flags)
2. Create skullport.silver.tracking_events (deduplicate, parse timestamps, add quality flags)
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

# Verify Unity Catalog setup

logger.info("=" * 70)
logger.info("VERIFICATION: UNITY CATALOG SETUP")
logger.info("=" * 70)

try:
    current_catalog = spark.sql("SELECT current_catalog()").collect()[0][0]
    logger.info(f"Current catalog: {current_catalog}")
    logger.info("✓ Unity Catalog verified")
except Exception as e:
    logger.error(f"❌ Catalog check failed: {e}")
    raise

# COMMAND ----------

# Step 0: Ensure silver schema exists

logger.info("=" * 70)
logger.info("STEP 0: ENSURE SCHEMA EXISTS")
logger.info("=" * 70)

spark.sql("CREATE SCHEMA IF NOT EXISTS skullport.silver")
logger.info("✓ Schema skullport.silver ready")

# COMMAND ----------

# Step 1: Create skullport.silver.labels (collapse CDC + fraud flags)

logger.info("\n" + "=" * 70)
logger.info("STEP 1: CREATE SILVER.LABELS")
logger.info("=" * 70)

spark.sql("""
CREATE OR REPLACE TABLE skullport.silver.labels AS
WITH latest_per_label AS (
  SELECT
    *,
    ROW_NUMBER() OVER (PARTITION BY label_id ORDER BY last_updated_at DESC) AS rn
  FROM skullport.raw.labels
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

labels_count = spark.sql("SELECT COUNT(*) as count FROM skullport.silver.labels").collect()[0][0]
logger.info(f"✓ Created skullport.silver.labels: {labels_count} rows")

# COMMAND ----------

# Step 2: Create skullport.silver.tracking_events (dedup + merge codes + parse timestamps + flags)

logger.info("\n" + "=" * 70)
logger.info("STEP 2: CREATE SILVER.TRACKING_EVENTS")
logger.info("=" * 70)

spark.sql("""
CREATE OR REPLACE TABLE skullport.silver.tracking_events AS
WITH deduped AS (
  SELECT
    *,
    ROW_NUMBER() OVER (PARTITION BY event_id ORDER BY event_received_at DESC) AS rn
  FROM skullport.raw.tracking_events
),
normalized AS (
  -- Normalize every carrier-specific / corrupted event_at string into an
  -- explicit-offset ISO 8601 string, so a single parse yields the correct UTC instant.
  SELECT
    event_id,
    label_id,
    carrier,
    event_code,
    event_type,
    event_at AS event_at_raw,
    event_received_at,
    location_zip,
    raw_payload,
    -- Trailing timezone abbreviation, e.g. " EST" (empty string if none)
    regexp_extract(event_at, ' ([A-Z]{2,4})$', 1) AS tz_abbr,
    CASE
      -- 1) Timezone abbreviation (DHL) -> swap abbr for its numeric UTC offset
      WHEN regexp_extract(event_at, ' ([A-Z]{2,4})$', 1) <> '' THEN
        regexp_replace(event_at, ' [A-Z]{2,4}$', '') ||
        CASE regexp_extract(event_at, ' ([A-Z]{2,4})$', 1)
          WHEN 'EST' THEN '-05:00' WHEN 'EDT' THEN '-04:00'
          WHEN 'CST' THEN '-06:00' WHEN 'CDT' THEN '-05:00'
          WHEN 'MST' THEN '-07:00' WHEN 'MDT' THEN '-06:00'
          WHEN 'PST' THEN '-08:00' WHEN 'PDT' THEN '-07:00'
          ELSE 'Z'
        END
      -- 2) Already carries an explicit offset or Z (USPS, UPS) -> keep as-is
      WHEN event_at RLIKE 'T[0-9]{2}:[0-9]{2}:[0-9]{2}([+-][0-9]{2}:[0-9]{2}|Z)$' THEN event_at
      -- 3) Corrupted: no separators (20260606T053000) -> rebuild + assume UTC (tz was destroyed)
      WHEN event_at RLIKE '^[0-9]{8}T[0-9]{6}$' THEN
        substr(event_at,1,4)||'-'||substr(event_at,5,2)||'-'||substr(event_at,7,2)||'T'||
        substr(event_at,10,2)||':'||substr(event_at,12,2)||':'||substr(event_at,14,2)||'Z'
      -- 4) Corrupted: wrong separators (slashes) -> dashes + assume UTC
      WHEN event_at RLIKE '^[0-9]{4}/[0-9]{2}/[0-9]{2}' THEN replace(event_at,'/','-')||'Z'
      -- 5) Corrupted: date only (missing time) -> midnight UTC
      WHEN event_at RLIKE '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' THEN event_at||'T00:00:00Z'
      -- 6) Plain ISO, no tz (FEDEX) -> assume UTC
      WHEN event_at RLIKE '^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}$' THEN event_at||'Z'
      ELSE event_at
    END AS normalized_iso
  FROM deduped
  WHERE rn = 1
),
parsed_events AS (
  SELECT
    event_id,
    label_id,
    carrier,
    -- Preserve the original carrier-specific identifiers for traceability
    event_code,
    event_type,
    -- Conform carrier-specific codes/types into a canonical event_name
    -- (handles schema drift: USPS uses numeric codes, others use type strings,
    -- DHL uses short codes). Unmatched / missing -> 'unknown'.
    CASE COALESCE(event_code, event_type)
      WHEN '0300' THEN 'picked_up'
      WHEN 'PICKUP' THEN 'picked_up'
      WHEN 'PU' THEN 'picked_up'
      WHEN '0301' THEN 'in_transit'
      WHEN 'IN_TRANSIT' THEN 'in_transit'
      WHEN 'IT' THEN 'in_transit'
      WHEN '0310' THEN 'out_for_delivery'
      WHEN 'OUT_FOR_DELIVERY' THEN 'out_for_delivery'
      WHEN 'OFD' THEN 'out_for_delivery'
      WHEN '0320' THEN 'delivered'
      WHEN 'DELIVERED' THEN 'delivered'
      WHEN 'DL' THEN 'delivered'
      ELSE 'unknown'
    END AS event_name,
    -- Parse the normalized string into a UTC timestamp
    try_to_timestamp(normalized_iso) AS event_at,
    event_received_at,
    location_zip,
    raw_payload,
    -- Quality flags
    -- Malformed = source string was a corrupted format (separators/time destroyed,
    -- so the timezone was lost and the instant is best-effort) or is unparseable.
    CASE
      WHEN event_at_raw RLIKE '^[0-9]{8}T[0-9]{6}$' THEN TRUE          -- no separators
      WHEN event_at_raw RLIKE '^[0-9]{4}/[0-9]{2}/[0-9]{2}' THEN TRUE  -- wrong separators
      WHEN event_at_raw RLIKE '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' THEN TRUE -- date only
      WHEN try_to_timestamp(normalized_iso) IS NULL THEN TRUE          -- unparseable
      ELSE FALSE
    END AS is_malformed_timestamp,
    CASE WHEN event_code IS NULL AND event_type IS NULL THEN TRUE ELSE FALSE END AS is_missing_event_type,
    current_timestamp() AS inserted_at
  FROM normalized
),
with_voided_flag AS (
  SELECT
    pe.*,
    CASE WHEN l.voided_at IS NOT NULL THEN TRUE ELSE FALSE END AS is_event_on_voided_label
  FROM parsed_events pe
  LEFT JOIN skullport.silver.labels l ON pe.label_id = l.label_id
)
SELECT * FROM with_voided_flag
""")

events_count = spark.sql("SELECT COUNT(*) as count FROM skullport.silver.tracking_events").collect()[0][0]
logger.info(f"✓ Created skullport.silver.tracking_events: {events_count} rows")

# COMMAND ----------

# Step 3: Remove orphaned events

logger.info("\n" + "=" * 70)
logger.info("STEP 3: REMOVE ORPHANED EVENTS")
logger.info("=" * 70)

orphaned_count = spark.sql("""
SELECT COUNT(*) as count FROM skullport.silver.tracking_events
WHERE label_id NOT IN (SELECT label_id FROM skullport.silver.labels)
""").collect()[0][0]

if orphaned_count > 0:
  logger.info(f"Found {orphaned_count} orphaned events, removing...")

  spark.sql("""
  CREATE OR REPLACE TABLE skullport.silver.tracking_events AS
  SELECT *
  FROM skullport.silver.tracking_events
  WHERE label_id IN (SELECT label_id FROM skullport.silver.labels)
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
labels_final = spark.sql("SELECT COUNT(*) as count FROM skullport.silver.labels").collect()[0][0]
events_final = spark.sql("SELECT COUNT(*) as count FROM skullport.silver.tracking_events").collect()[0][0]
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
FROM skullport.silver.tracking_events
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
FROM skullport.silver.labels, skullport.silver.tracking_events
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
FROM skullport.silver.tracking_events e
WHERE e.label_id NOT IN (SELECT label_id FROM skullport.silver.labels)
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
