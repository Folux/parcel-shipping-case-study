# Specification: 4b. Bronze → Silver → Gold Pipeline

## Overview

Build a production-grade data pipeline in Databricks that transforms synthetic data from Section 4a into analytics-ready mart tables. The pipeline processes `raw.labels` and `raw.tracking_events` through three layers (Bronze, Silver, Gold) with explicit handling of data quality issues.

---

## Getting Bronze Tables to Databricks (Step 1: Deploy Generator)

**Step 1: Push to GitHub**
- Commit and push the project to GitHub (public repo)

**Step 2: Create Databricks Workspace**
- Sign up for Databricks Free Edition
- Create workspace
- Get workspace URL

**Step 3: Connect GitHub to Databricks**
- In Databricks: Settings → Developer → Personal access tokens
- Generate token and authenticate with GitHub
- Grant Databricks repo access

**Step 4: Clone Repo into Databricks**
- In Databricks: Repos → Add Repo
- Paste GitHub URL
- Clone repo into workspace

**Step 5: Run Generator Notebook**
- Open `notebooks/pirate_ship_generator.py` in Databricks
- Click "Run all"
- Wait for completion

**Step 6: Verify Bronze Tables (Generator Output)**
- Check Databricks Catalog
- Verify tables exist:
  - `pirate_ship.bronze.labels` (should have ~5000 rows)
  - `pirate_ship.bronze.tracking_events` (should have ~30000 rows)

**Note**: The generator creates the Bronze tables directly. In data lake terminology, these are the "landing zone" tables (idempotent, schema as-is from source).

---

## Silver Layer (Clean & Conformed Data)

**Purpose**: Deduplicate, parse, validate, and flag data quality issues.

### Silver Labels

**Transformations**:
1. Deduplicate: Keep latest row per `label_id` (by `last_updated_at`)
2. Validate: Flag data errors
   - `voided_at` < `label_created_at` → flag "voided_before_created"
   - `carrier_promised_delivery_at` < `label_created_at` → flag "promised_before_created"
   - `weight_oz > 1120` (weight fraud) → flag "weight_fraud_detected", mark `is_weight_adjusted = TRUE`
   - `declared_value_cents = 0` with insurance → flag "zero_declared_value_with_insurance", mark `is_insurance_anomaly = TRUE`
3. Add boolean: `is_voided` (derived from `voided_at IS NOT NULL`)
4. Add column: `data_quality_flags` (comma-separated list of issues)

**Target**: `pirate_ship.silver.labels`

### Silver Events

**Transformations**:
1. Deduplicate: Keep one row per `event_id`, latest by `event_received_at`
2. Parse timestamps:
   - Parse `event_at` STRING → TIMESTAMP (UTC)
   - Handle malformed formats, timezone offsets
   - If unparseable: set to NULL, flag "malformed_timestamp"
3. Late arrivals:
   - Calculate `event_lag_days` = (`event_received_at` - `event_at_parsed`) in days
   - Flag rows where lag > 3 days: `is_late_arrival = TRUE`, add "late_arrival" to flags
4. Missing fields:
   - Flag rows where BOTH `event_code` AND `event_type` are NULL
   - Set `has_missing_event_identifier = TRUE`, add "missing_event_code_and_type" to flags
5. JSON validation:
   - Try to parse `raw_payload` as JSON
   - If fails: set `has_invalid_payload = TRUE`, add "unparseable_json_payload" to flags
6. Voided label events:
   - Join with silver.labels
   - Flag events where `event_received_at` > `voided_at`
   - Set `is_voided_label_event = TRUE`, add "event_after_voiding" to flags
7. Schema drift:
   - Create `event_code_or_type` = coalesce(`event_code`, `event_type`)
   - Keep original columns for reference

**Target**: `pirate_ship.silver.tracking_events`

**Requirements**:
- Handle all case study data quality issues (duplicates, late arrivals, malformed timestamps, missing fields, schema drift, voided events)
- Preserve original columns
- Add explicit flags and quality indicators
- Keep all rows (don't filter, just flag)
- Idempotent: full refresh with OVERWRITE mode

---

## Gold Layer (Analytics-Ready Mart)

**Purpose**: Create analytics-ready table(s) that answer business questions.

### Mart: `pirate_ship.gold.delivery_performance`

**Grain**: One row per label

**Columns** (example):
- `label_id`, `customer_id`, `carrier`, `service_class`
- `origin_zip`, `dest_zip`, `weight_oz`, `declared_value_cents`
- `label_created_at`, `carrier_promised_delivery_at`
- `actual_delivery_at` (from latest "delivered" event)
- `days_late` (actual_delivery_at - carrier_promised_delivery_at)
- `is_delivered_on_time` (days_late <= 0)
- `is_delivered` (has delivery event)
- `days_to_first_scan`
- `event_count`
- `has_data_quality_issues`
- `data_quality_flags`

**Transformations**:
1. Join silver.labels with silver.tracking_events
2. Find "delivered" event per label (latest by event_at_parsed)
3. Calculate metrics (days_late, on_time status, event counts)
4. Flag any data quality issues
5. Result: one row per label with delivery metrics

**Requirements**:
- Answer business questions:
  - What % of shipments delivered on-time?
  - Where do delays cluster (carrier, service class, region)?
  - How fresh is tracking data (days_to_first_scan, has_recent_events)?
- Idempotent: full refresh with OVERWRITE mode

---

## Data Quality Tests

**Minimum 4 tests** covering completeness, data quality flagging, freshness, and business logic:

### Test 1: Deduplication & Completeness
```
Assert: COUNT(silver.labels) == COUNT(bronze.labels)
        (CDC resolved to current state, no data loss)

Assert: COUNT(silver.tracking_events) <= COUNT(bronze.tracking_events)
        (duplicates removed; silver <= bronze or equal if no duplicates)

Assert: COUNT(silver.tracking_events where event_at_parsed IS NOT NULL) >= 0.95 * COUNT(silver.tracking_events)
        (at least 95% timestamps parseable)
```

### Test 2: Data Quality Issue Detection
```
Assert: COUNT(silver.labels where is_weight_adjusted = TRUE) > 0
        (weight fraud flags detected)

Assert: COUNT(silver.labels where is_insurance_anomaly = TRUE) > 0
        (insurance anomalies detected)

Assert: COUNT(silver.tracking_events where is_late_arrival = TRUE) > 0
        (late arrivals flagged)

Assert: COUNT(silver.tracking_events where has_missing_event_identifier = TRUE) >= 0
        (missing event identifiers detected)

Assert: COUNT(silver.tracking_events where is_voided_label_event = TRUE) >= 0
        (events after voiding flagged)
```

### Test 3: Freshness
```
Assert: MAX(event_received_at) in silver.tracking_events >= CURRENT_TIMESTAMP - INTERVAL 1 DAY
        (recent data exists)

Assert: COUNT(silver.tracking_events where is_late_arrival = TRUE) <= 0.15 * COUNT(silver.tracking_events)
        (late arrivals < 15%; realistic proportion)
```

### Test 4: Business Logic
```
Assert: COUNT(gold.delivery_performance where is_delivered = TRUE AND is_delivered_on_time = TRUE) 
        >= 0.80 * COUNT(gold.delivery_performance where is_delivered = TRUE)
        (80%+ delivered packages are on-time)

Assert: COUNT(gold.delivery_performance where days_late < -30) == 0
        (no packages delivered > 30 days early)

Assert: COUNT(gold.delivery_performance where is_delivered = FALSE) <= 0.05 * COUNT(gold.delivery_performance)
        (< 5% no delivery event; reasonable for fresh data)
```

---

## Implementation Order

1. **Bronze layer** ✅ - Created by generator (4a)
2. **Silver layer** - Read from bronze, clean, deduplicate, flag issues
3. **Gold layer** - Read from silver, create analytics table(s)
4. **Data quality tests** - Validate at each layer

---

## Nice-to-Have (Future)

**Incremental Processing with Day Partitions**:
- Current: Full refresh of all layers on each run
- Future: Partition by date, only reprocess that day's data
- Benefits: Faster incremental runs, natural boundary for late arrivals
- Implementation: Add date partition column, delete-and-reinsert by date

