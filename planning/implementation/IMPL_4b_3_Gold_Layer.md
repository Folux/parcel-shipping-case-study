# Implementation Plan: 4a.3. Gold Layer

## Overview

Build the delivery_performance analytics mart using the same approach as the Silver layer: pure SQL via `spark.sql()`, idempotent `CREATE OR REPLACE TABLE`, CTEs for multi-step logic, and comprehensive validation.

Single notebook: `notebooks/gold_layer.py`

---

## Phase 1: Notebook MVP

### Implementation Steps

**Step 0: Ensure Schema**
- `CREATE SCHEMA IF NOT EXISTS skullport.gold`

**Step 1: Create `skullport.gold.delivery_performance`**
- Join `skullport.silver.labels` with `skullport.silver.tracking_events`
- CTE: extract latest "delivered" event per label using `ROW_NUMBER() OVER (PARTITION BY label_id ORDER BY event_at DESC)`
- Calculate metrics:
  - `is_delivered`: CASE WHEN delivery event exists THEN TRUE ELSE FALSE END
  - `actual_delivery_at`: event_at from delivery event (NULL if no delivery)
  - `is_delivered_on_time`: CASE WHEN actual_delivery_at <= carrier_promised_delivery_at THEN TRUE ELSE FALSE END
- Result: one row per label with all dimensions and metrics
- Write with `CREATE OR REPLACE TABLE` (idempotent, full refresh)

**Step 2: Validation**
- Row count = count of distinct label_ids in silver.labels (one row per label)
- `is_delivered_on_time` is boolean (0/1 values only)
- Sample queries work:
  - Overall % on-time
  - % on-time by carrier
  - % on-time by service_class

**Step 3: Summary Output**
- Log total labels, count on-time, % on-time
- Log counts by carrier

---

## Implementation Style

**Same as Silver layer:**
- ✅ Pure SQL (`spark.sql()`)
- ✅ CTEs for multi-step transformations
- ✅ Window functions for deduplication (no DISTINCT)
- ✅ `CREATE OR REPLACE TABLE` for idempotency
- ✅ Comprehensive logging throughout
- ✅ Validation checks with row counts, type checks, business logic assertions
- ✅ Pre-injected `spark` global (no `SparkSession.getOrCreate()`)

---

## Testing (Phase 1)

- Validation queries at end of notebook
- Row counts (one per label)
- Boolean flag distributions
- Sample aggregation queries (% on-time overall, by carrier, by service_class)

---

## Phase 2: dbt (deferred)

- Refactor to dbt models with tests
- Add more metrics as columns (days_late, days_to_first_scan, event_count)
- Create separate analytical marts (delay_analysis, data_freshness) with different grains
- Incremental merge strategy

---

## Success Criteria

- [ ] Notebook reads Silver, writes Gold (idempotent)
- [ ] One row per label (no duplicates)
- [ ] `is_delivered_on_time` computed correctly
- [ ] Validation checks pass
- [ ] % on-time metric is accurate (testable: count manual vs. COUNT/SUM)
- [ ] Notebook runs end-to-end without errors
