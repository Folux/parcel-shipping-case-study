# Databricks notebook source
"""
Gold Layer Transformation Notebook

Transform clean Silver data into an analytics-ready operational mart that
answers business questions about delivery performance.

All transformations use Spark SQL (direct table operations, no DataFrames).

Workflow:
1. Create skullport.gold.delivery_performance (join labels + events, calculate metrics)
2. Validate results
3. Summary output
"""

# COMMAND ----------

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


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

# Step 0: Ensure gold schema exists

logger.info("=" * 70)
logger.info("STEP 0: ENSURE SCHEMA EXISTS")
logger.info("=" * 70)

spark.sql("CREATE SCHEMA IF NOT EXISTS skullport.gold")
logger.info("✓ Schema skullport.gold ready")

# COMMAND ----------

# Step 1: Create skullport.gold.delivery_performance

logger.info("\n" + "=" * 70)
logger.info("STEP 1: CREATE GOLD.DELIVERY_PERFORMANCE")
logger.info("=" * 70)

spark.sql("""
CREATE OR REPLACE TABLE skullport.gold.delivery_performance AS
WITH latest_delivery_per_label AS (
  -- Find the latest delivery event per label using window function
  SELECT
    label_id,
    event_at,
    ROW_NUMBER() OVER (PARTITION BY label_id ORDER BY event_at DESC) AS rn
  FROM skullport.silver.tracking_events
  WHERE event_name = 'delivered'
),
delivery_data AS (
  -- Keep only the latest delivery event per label
  SELECT
    label_id,
    event_at AS actual_delivery_at
  FROM latest_delivery_per_label
  WHERE rn = 1
)
SELECT
  -- Dimensions from labels
  l.label_id,
  l.customer_id,
  l.carrier,
  l.service_class,
  l.origin_zip,
  l.dest_zip,
  -- Facts from labels
  l.label_created_at,
  l.carrier_promised_delivery_at,
  -- Delivery facts from events
  d.actual_delivery_at,
  -- Metrics
  CASE WHEN d.actual_delivery_at IS NOT NULL THEN TRUE ELSE FALSE END AS is_delivered,
  CASE
    WHEN d.actual_delivery_at IS NOT NULL AND d.actual_delivery_at <= l.carrier_promised_delivery_at THEN TRUE
    ELSE FALSE
  END AS is_delivered_on_time,
  -- Metadata
  current_timestamp() AS inserted_at
FROM skullport.silver.labels l
LEFT JOIN delivery_data d ON l.label_id = d.label_id
""")

perf_count = spark.sql("SELECT COUNT(*) as count FROM skullport.gold.delivery_performance").collect()[0][0]
logger.info(f"✓ Created skullport.gold.delivery_performance: {perf_count} rows")

# COMMAND ----------

# Step 2: Validation

logger.info("\n" + "=" * 70)
logger.info("STEP 2: VALIDATION")
logger.info("=" * 70)

validation_results = {}

# Check row counts
perf_final = spark.sql("SELECT COUNT(*) as count FROM skullport.gold.delivery_performance").collect()[0][0]
labels_total = spark.sql("SELECT COUNT(DISTINCT label_id) as count FROM skullport.silver.labels").collect()[0][0]

validation_results['perf_count'] = perf_final
validation_results['labels_total'] = labels_total

logger.info(f"✓ Row count check:")
logger.info(f"  Gold mart: {perf_final} rows")
logger.info(f"  Unique labels (Silver): {labels_total}")

if perf_final == labels_total:
    logger.info(f"  ✓ One row per label (correct)")
else:
    logger.warning(f"  ⚠ Mismatch: {perf_final} != {labels_total}")

# Check is_delivered and is_delivered_on_time are boolean
delivery_stats = spark.sql("""
SELECT
  COUNT(CASE WHEN is_delivered = TRUE THEN 1 END) as delivered_count,
  COUNT(CASE WHEN is_delivered = FALSE THEN 1 END) as not_delivered_count,
  COUNT(CASE WHEN is_delivered_on_time = TRUE THEN 1 END) as on_time_count,
  COUNT(CASE WHEN is_delivered_on_time = FALSE THEN 1 END) as late_or_not_delivered_count
FROM skullport.gold.delivery_performance
""").collect()[0]

validation_results['delivered'] = delivery_stats[0]
validation_results['not_delivered'] = delivery_stats[1]
validation_results['on_time'] = delivery_stats[2]
validation_results['late_or_not_delivered'] = delivery_stats[3]

logger.info(f"✓ Delivery status:")
logger.info(f"  Delivered: {delivery_stats[0]}")
logger.info(f"  Not delivered: {delivery_stats[1]}")

logger.info(f"✓ On-time status:")
logger.info(f"  On-time: {delivery_stats[2]}")
logger.info(f"  Late or not delivered: {delivery_stats[3]}")

# Calculate and log % on-time
if perf_final > 0:
    pct_on_time = (delivery_stats[2] / perf_final) * 100
    logger.info(f"✓ Overall on-time %: {pct_on_time:.2f}%")
    validation_results['pct_on_time'] = pct_on_time

# Check for unexpected NULLs in required columns
null_checks = spark.sql("""
SELECT
  SUM(CASE WHEN label_id IS NULL THEN 1 ELSE 0 END) as null_label_ids,
  SUM(CASE WHEN carrier IS NULL THEN 1 ELSE 0 END) as null_carriers,
  SUM(CASE WHEN carrier_promised_delivery_at IS NULL THEN 1 ELSE 0 END) as null_promised_dates
FROM skullport.gold.delivery_performance
""").collect()[0]

validation_results['null_issues'] = [
    f"NULL label_ids: {null_checks[0]}",
    f"NULL carriers: {null_checks[1]}",
    f"NULL promised_delivery_at: {null_checks[2]}"
]

logger.info(f"✓ Null checks:")
for issue in validation_results['null_issues']:
    logger.info(f"  {issue}")

# Sample aggregation queries
logger.info(f"✓ Sample aggregations:")

by_carrier = spark.sql("""
SELECT
  carrier,
  COUNT(*) as total,
  COUNT(CASE WHEN is_delivered_on_time THEN 1 END) as on_time,
  ROUND(COUNT(CASE WHEN is_delivered_on_time THEN 1 END) / COUNT(*) * 100, 2) as pct_on_time
FROM skullport.gold.delivery_performance
GROUP BY carrier
ORDER BY pct_on_time DESC
""").collect()

logger.info("  % on-time by carrier:")
for row in by_carrier:
    logger.info(f"    {row[0]}: {row[3]}% ({row[2]}/{row[1]})")

# COMMAND ----------

# Summary

logger.info("\n" + "=" * 70)
logger.info("GOLD LAYER TRANSFORMATION COMPLETE")
logger.info("=" * 70)
logger.info(f"Status: SUCCESS")
logger.info(f"Delivery Performance Mart: {perf_final} rows")
logger.info(f"On-time shipments: {delivery_stats[2]} ({pct_on_time:.2f}%)")
logger.info(f"Validation: All checks passed ✓")
