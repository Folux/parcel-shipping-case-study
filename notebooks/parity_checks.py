# Databricks notebook source
"""
Parity Checks — dbt output vs notebook output

The dbt models are a faithful port of the notebook SQL, built from the same
Bronze data, so the tables should be row-for-row identical:

    skullport.silver.labels             == skullport.silver_dbt.labels
    skullport.silver.tracking_events    == skullport.silver_dbt.tracking_events
    skullport.gold.delivery_performance == skullport.gold_dbt.delivery_performance

The only expected difference is `inserted_at` (a build-time load timestamp), so
it is excluded from the comparison. Any other difference fails the notebook.

Prereq: build both sides from the SAME Bronze run —
  1. ingestion_and_bronze_layer  (Bronze)
  2. silver_layer + gold_layer    (notebook side)
  3. databricks bundle run skullport_dbt_build  (dbt side)
"""

# COMMAND ----------

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# COMMAND ----------

# Table pairs: (notebook-built, dbt-built)
PAIRS = [
    ("skullport.silver.labels",             "skullport.silver_dbt.labels"),
    ("skullport.silver.tracking_events",    "skullport.silver_dbt.tracking_events"),
    ("skullport.gold.delivery_performance", "skullport.gold_dbt.delivery_performance"),
]

# Columns excluded from the comparison (build-time, expected to differ)
IGNORE = {"inserted_at"}

# COMMAND ----------

logger.info("=" * 70)
logger.info("PARITY CHECKS: notebook vs dbt")
logger.info("=" * 70)

failures = []

for nb_table, dbt_table in PAIRS:
    df_nb = spark.table(nb_table)
    df_dbt = spark.table(dbt_table)

    cols_nb = sorted(c for c in df_nb.columns if c not in IGNORE)
    cols_dbt = sorted(c for c in df_dbt.columns if c not in IGNORE)

    # 1) Column sets must match
    if cols_nb != cols_dbt:
        only_nb = set(cols_nb) - set(cols_dbt)
        only_dbt = set(cols_dbt) - set(cols_nb)
        logger.error(f"[FAIL] {nb_table} vs {dbt_table}: column mismatch")
        logger.error(f"        only in notebook: {sorted(only_nb)}")
        logger.error(f"        only in dbt     : {sorted(only_dbt)}")
        failures.append(nb_table)
        continue

    # 2) Row counts + set difference in both directions (null-safe)
    a = df_nb.select(cols_nb)
    b = df_dbt.select(cols_nb)
    n_nb = a.count()
    n_dbt = b.count()
    only_in_nb = a.exceptAll(b).count()
    only_in_dbt = b.exceptAll(a).count()

    identical = (n_nb == n_dbt and only_in_nb == 0 and only_in_dbt == 0)
    status = "PASS" if identical else "FAIL"
    logger.info(f"[{status}] {nb_table} vs {dbt_table}")
    logger.info(f"        rows: notebook={n_nb}, dbt={n_dbt}")
    logger.info(f"        rows only in notebook={only_in_nb}, only in dbt={only_in_dbt}")

    if not identical:
        failures.append(nb_table)

# COMMAND ----------

logger.info("=" * 70)
logger.info("PARITY SUMMARY")
logger.info("=" * 70)
logger.info(f"Pairs checked : {len(PAIRS)}")
logger.info(f"Identical     : {len(PAIRS) - len(failures)}")
logger.info(f"Mismatched    : {len(failures)}")

if failures:
    for t in failures:
        logger.error(f"  MISMATCH: {t}")
    raise AssertionError(
        f"{len(failures)} table(s) differ between notebook and dbt — see log. "
        f"(Did both sides build from the same Bronze run?)"
    )

logger.info("✓ dbt output is identical to the notebook output across all tables")
