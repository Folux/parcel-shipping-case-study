# Databricks notebook source
"""
Pipeline Validation Checks

Data-quality / correctness checks across the Silver and Gold layers. Each check
runs a SQL query and asserts an expected condition; failures are collected and
the notebook raises at the end so it can be used as a gate (e.g. in a job).

Grouped by layer:
  1. Silver — event_name conformance & timestamp parsing
  2. Silver — integrity & dedup
  3. Silver — timezone sanity
  4. Gold   — the on-time metric
  5. Idempotency (documented manual check)

These checks are intentionally written as plain Spark SQL so they port directly
to dbt tests (schema/data tests + a few singular tests) in Phase 2.
"""

# COMMAND ----------

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Render timestamps as UTC wall-clock for any manual inspection
spark.sql("SET TIME ZONE 'UTC'")

# COMMAND ----------

# Lightweight assertion harness: record every check, raise at the end if any failed.

_results = []  # list of (name, passed, detail)


def check(name: str, passed: bool, detail: str = ""):
    """Record a check result and log it."""
    status = "PASS" if passed else "FAIL"
    _results.append((name, passed, detail))
    logger.info(f"[{status}] {name}" + (f" — {detail}" if detail else ""))


def scalar(sql: str):
    """Run a query and return the first column of the first row."""
    return spark.sql(sql).collect()[0][0]


# COMMAND ----------

# =====================================================================
# 1. SILVER — event_name conformance & timestamp parsing
# =====================================================================

logger.info("=" * 70)
logger.info("1. SILVER — CONFORMANCE & TIMESTAMPS")
logger.info("=" * 70)

# 1a. event_name contains only canonical values (no raw carrier codes leaked)
non_canonical = scalar("""
SELECT COUNT(*)
FROM skullport.silver.tracking_events
WHERE event_name NOT IN ('picked_up', 'in_transit', 'out_for_delivery', 'delivered', 'unknown')
""")
check("1a. event_name only canonical values", non_canonical == 0,
      f"{non_canonical} rows with non-canonical event_name")

# 1b. Every carrier maps to all four canonical stages
carriers_missing_stage = scalar("""
WITH per_carrier AS (
  SELECT carrier, COUNT(DISTINCT event_name) AS stages
  FROM skullport.silver.tracking_events
  WHERE event_name <> 'unknown'
  GROUP BY carrier
)
SELECT COUNT(*) FROM per_carrier WHERE stages < 4
""")
check("1b. All 4 stages present per carrier", carriers_missing_stage == 0,
      f"{carriers_missing_stage} carriers missing a stage")

# 1c. Timestamps parse to UTC for ~all events; malformed stays small
total_events = scalar("SELECT COUNT(*) FROM skullport.silver.tracking_events")
parsed_events = scalar("SELECT COUNT(event_at) FROM skullport.silver.tracking_events")
malformed = scalar("SELECT SUM(CASE WHEN is_malformed_timestamp THEN 1 ELSE 0 END) FROM skullport.silver.tracking_events")
pct_parsed = 100.0 * parsed_events / total_events
pct_malformed = 100.0 * malformed / total_events
check("1c. >=99% of event_at parsed to UTC", pct_parsed >= 99.0,
      f"{pct_parsed:.2f}% parsed")
check("1d. Malformed timestamps in sane range (<3%)", pct_malformed < 3.0,
      f"{pct_malformed:.2f}% malformed")

# COMMAND ----------

# =====================================================================
# 2. SILVER — integrity & dedup
# =====================================================================

logger.info("=" * 70)
logger.info("2. SILVER — INTEGRITY & DEDUP")
logger.info("=" * 70)

# 2a. event_id is unique (dedup worked)
event_dupes = scalar("""
SELECT COUNT(*) - COUNT(DISTINCT event_id) FROM skullport.silver.tracking_events
""")
check("2a. event_id unique (no duplicates)", event_dupes == 0,
      f"{event_dupes} duplicate event_ids")

# 2b. No orphan events (referential integrity)
orphans = scalar("""
SELECT COUNT(*)
FROM skullport.silver.tracking_events e
LEFT JOIN skullport.silver.labels l USING (label_id)
WHERE l.label_id IS NULL
""")
check("2b. No orphan events", orphans == 0, f"{orphans} orphan events")

# 2c. labels collapsed to one row per label_id (CDC collapse)
label_rows = scalar("SELECT COUNT(*) FROM skullport.silver.labels")
label_distinct = scalar("SELECT COUNT(DISTINCT label_id) FROM skullport.silver.labels")
check("2c. One row per label_id (CDC collapse)", label_rows == label_distinct,
      f"{label_rows} rows vs {label_distinct} distinct label_ids")

# COMMAND ----------

# =====================================================================
# 3. SILVER — timezone sanity
# =====================================================================

logger.info("=" * 70)
logger.info("3. SILVER — TIMEZONE SANITY")
logger.info("=" * 70)

# 3a. No delivery event occurs before its label was created (would signal a TZ/parse bug)
delivered_before_created = scalar("""
SELECT COUNT(*)
FROM skullport.silver.tracking_events e
JOIN skullport.silver.labels l USING (label_id)
WHERE e.event_name = 'delivered' AND e.event_at < l.label_created_at
""")
check("3a. No delivery before label creation", delivered_before_created == 0,
      f"{delivered_before_created} deliveries before creation")

# COMMAND ----------

# =====================================================================
# 4. GOLD — the on-time metric
# =====================================================================

logger.info("=" * 70)
logger.info("4. GOLD — DELIVERY PERFORMANCE METRIC")
logger.info("=" * 70)

# 4a. One row per label
gold_rows = scalar("SELECT COUNT(*) FROM skullport.gold.delivery_performance")
gold_distinct = scalar("SELECT COUNT(DISTINCT label_id) FROM skullport.gold.delivery_performance")
check("4a. Gold: one row per label", gold_rows == gold_distinct == label_distinct,
      f"{gold_rows} rows / {gold_distinct} distinct / {label_distinct} labels")

# 4b. On-time rate is realistic: case study expects 80%+, and a non-100% value
metric = spark.sql("""
SELECT
  COUNT(*) AS total,
  SUM(CASE WHEN is_delivered THEN 1 ELSE 0 END) AS delivered,
  SUM(CASE WHEN is_delivered_on_time THEN 1 ELSE 0 END) AS on_time
FROM skullport.gold.delivery_performance
""").collect()[0]
pct_on_time_overall = 100.0 * metric["on_time"] / metric["total"]
pct_on_time_delivered = 100.0 * metric["on_time"] / metric["delivered"]
check("4b. Overall on-time in [80%, 99%]", 80.0 <= pct_on_time_overall <= 99.0,
      f"{pct_on_time_overall:.1f}% overall on-time")
check("4c. On-time of delivered in [80%, 99.9%]", 80.0 <= pct_on_time_delivered <= 99.9,
      f"{pct_on_time_delivered:.1f}% of delivered on-time")

# 4d. Late deliveries are visible (the late_delivery_proportion signal)
pct_late_delivered = 100.0 * (metric["delivered"] - metric["on_time"]) / metric["delivered"]
check("4d. Late deliveries visible in (0%, 15%)", 0.0 < pct_late_delivered < 15.0,
      f"{pct_late_delivered:.1f}% of delivered are late")

# 4e. No logically impossible states
impossible = spark.sql("""
SELECT
  SUM(CASE WHEN NOT is_delivered AND actual_delivery_at IS NOT NULL THEN 1 ELSE 0 END) AS not_delivered_but_has_ts,
  SUM(CASE WHEN NOT is_delivered AND is_delivered_on_time THEN 1 ELSE 0 END) AS undelivered_but_ontime,
  SUM(CASE WHEN is_delivered_on_time AND actual_delivery_at > carrier_promised_delivery_at THEN 1 ELSE 0 END) AS ontime_but_late_ts
FROM skullport.gold.delivery_performance
""").collect()[0]
impossible_total = sum(impossible)
check("4e. No impossible delivery states", impossible_total == 0,
      f"not_delivered_but_has_ts={impossible[0]}, undelivered_but_ontime={impossible[1]}, ontime_but_late_ts={impossible[2]}")

# 4f. No carrier is pathologically at 0% or 100% (would hint a per-carrier mapping/format slip)
carrier_outliers = scalar("""
WITH per_carrier AS (
  SELECT carrier,
    100.0 * SUM(CASE WHEN is_delivered_on_time THEN 1 ELSE 0 END) / COUNT(*) AS pct_on_time
  FROM skullport.gold.delivery_performance
  GROUP BY carrier
)
SELECT COUNT(*) FROM per_carrier WHERE pct_on_time <= 1.0 OR pct_on_time >= 99.5
""")
check("4f. No carrier at 0% / 100% on-time", carrier_outliers == 0,
      f"{carrier_outliers} carrier(s) at an extreme")

# COMMAND ----------

# =====================================================================
# Summary — raise if any check failed
# =====================================================================

logger.info("=" * 70)
logger.info("VALIDATION SUMMARY")
logger.info("=" * 70)

failures = [r for r in _results if not r[1]]
logger.info(f"Total checks : {len(_results)}")
logger.info(f"Passed       : {len(_results) - len(failures)}")
logger.info(f"Failed       : {len(failures)}")

if failures:
    for name, _, detail in failures:
        logger.error(f"  FAILED: {name} — {detail}")
    raise AssertionError(f"{len(failures)} validation check(s) failed — see log above")

logger.info("✓ All validation checks passed")

# COMMAND ----------

# Idempotency (manual check)
#
# OVERWRITE / CREATE OR REPLACE makes every layer idempotent. To verify:
#   1. Note the values below.
#   2. Re-run silver_layer and gold_layer notebooks.
#   3. Re-run this cell — the numbers must be identical.
idem = spark.sql("""
SELECT COUNT(*) AS rows,
       SUM(CASE WHEN is_delivered_on_time THEN 1 ELSE 0 END) AS on_time
FROM skullport.gold.delivery_performance
""").collect()[0]
logger.info(f"Idempotency snapshot — rows={idem['rows']}, on_time={idem['on_time']} (should be stable across re-runs)")
