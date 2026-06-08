# Silver Layer Specification (4a.2)

## Overview

**Purpose**: Transform raw Bronze data into clean, deduplicated, conformed Silver tables ready for analytics.

**Data Flow**: `Bronze` → `Silver` → `Gold`

**Implementation Strategy**:
- **Phase 1**: Proof-of-concept in Databricks notebook
  - Develop SQL logic incrementally
  - Test transformations in isolation
  - Verify idempotency and data quality handling
- **Phase 2**: Migrate to dbt (if time permits)
  - Package logic as dbt models
  - Add tests and documentation
  - Formalize deployment via Databricks Asset Bundle

---

## Silver Tables

### `silver.labels` (16 columns)

**Source**: Collapse CDC rows from `raw.labels` to latest state per label_id

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `label_id` | String | NO | Unique label ID (PK) |
| `customer_id` | String | NO | Customer ID |
| `carrier` | String | NO | Final carrier (after any updates) |
| `service_class` | String | NO | Final service class |
| `origin_zip` | String | NO | Origin ZIP code |
| `dest_zip` | String | NO | Destination ZIP code |
| `weight_oz` | Integer | NO | Final weight in ounces |
| `declared_value_cents` | Integer | YES | Final insurance value (or NULL) |
| `label_created_at` | Timestamp | NO | Original creation timestamp |
| `carrier_promised_delivery_at` | Timestamp | NO | SLA promised delivery date |
| `voided_at` | Timestamp | YES | Void timestamp (or NULL if active) |
| `last_updated_at` | Timestamp | NO | Latest update timestamp |
| `can_be_weight_fraud` | Boolean | NO | Weight close to max system limit (1000-1120 oz) — suspicious |
| `can_be_void_fraud` | Boolean | NO | Voided 2-5 days after creation (suspicious) |
| `can_be_insurance_anomaly` | Boolean | NO | Declared value = 0 but label insured |
| `can_be_missing_zip` | Boolean | NO | Origin or dest ZIP missing (safety check) |
| `inserted_at` | Timestamp | NO | When Silver ETL ran and inserted this row (UTC) |

**Transformation Logic**:
- Keep only the latest row per `label_id` (collapse CDC)
- Compute fraud flags based on Bronze data quality patterns
- Preserve all original columns

---

### `silver.tracking_events` (14 columns)

**Source**: Deduplicate and parse `raw.tracking_events`, merge event codes/types

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `event_id` | String | NO | Unique event ID |
| `label_id` | String | NO | Foreign key to silver.labels |
| `carrier` | String | NO | Carrier name |
| `event_name` | String | NO | Merged: event_code OR event_type (picked_up, in_transit, out_for_delivery, delivered) |
| `event_at` | Timestamp | NO | Event timestamp (parsed to valid UTC) |
| `event_received_at` | Timestamp | NO | System received timestamp |
| `location_zip` | String | YES | Scan location ZIP code |
| `raw_payload` | String | YES | Original carrier payload |
| `is_malformed_timestamp` | Boolean | NO | event_at couldn't be parsed to valid UTC (~1%) |
| `is_missing_event_type` | Boolean | NO | Both event_code and event_type NULL (~1%) |
| `is_event_on_voided_label` | Boolean | NO | Event on a voided label (~5% of voided labels) |
| `inserted_at` | Timestamp | NO | When Silver ETL ran and inserted this row (UTC) |

**Transformation Logic**:
- **Deduplicate**: Remove duplicate event_ids, keep last one (by event_received_at)
- Merge `event_code` and `event_type` into single `event_name` column
- Parse `event_at` (STRING) to TIMESTAMP in valid UTC (handle all carrier formats + malformed)
- Flag malformed patterns from Bronze (malformed_timestamp, missing_event_type)
- Join to silver.labels to check if label is voided

**Data Organization**:
- Events stored in received order (not necessarily chronological by event_at)
- Out-of-order events are valid; sequence can be reconstructed from event_name and timestamps in downstream analytics
- Ordering does not affect data lake correctness

---

## Data Quality Handling

**Strategy**: Keep all rows (don't drop), flag suspicious/malformed data, handle gracefully

**Specific Rules**:

- **Malformed timestamps** (`is_malformed_timestamp`):
  - If `event_at` unparseable → use `event_received_at` as fallback
  - Keep row, set flag = true

- **Missing event type** (`is_missing_event_type`):
  - Both event_code AND event_type NULL → keep row, set flag = true
  - `event_name` = NULL or "UNKNOWN"

- **Fraud flags** (weight, void, insurance, missing_zip):
  - Keep all rows, set flag = true
  - No rows dropped (preserve for audit trail)

- **Voided label events** (`is_event_on_voided_label`):
  - Keep all events, even on voided labels
  - Set flag = true for informational purposes

- **Referential Integrity**:
  - All `label_id` in events must exist in labels table
  - Orphaned events (no matching label) → dropped, logged for investigation

- **Nulls (allowed)**:
  - `declared_value_cents` NULL = not insured ✓
  - `location_zip` NULL = carrier didn't report ✓
  - `raw_payload` NULL = not captured ✓

**Philosophy**: Explicit flagging over silent dropping — enables downstream audit/investigation

---

## Idempotency

**All loads must be idempotent**: Re-running the Silver layer should produce identical results without duplicates or data corruption.

**MVP Approach (Notebook)**:
- Write mode: `OVERWRITE` (replace entire table)
- Safe to re-run any time without side effects
- Simple, effective for full-refresh batches

**Future (dbt + Incremental)**:
- Merge/upsert strategy using primary key (label_id, event_id)
- Incremental loads for efficiency at scale
- Late-arriving events handled via merge semantics

---

## Technology Stack

- **Phase 1 (Notebook)**: PySpark SQL + Databricks SQL
- **Phase 2 (dbt)**: dbt + Databricks SQL adapter

---

## Testing Strategy

**Phase 1 (Notebook MVP)**:
- Basic validation: row counts, NULLs, referential integrity
- Simple SQL checks in notebook

**Phase 2 (dbt)**:
- Comprehensive dbt tests (schema, uniqueness, referential integrity, edge cases)
- Great Expectations or dbt-native framework

---

## Success Criteria

- [ ] All Bronze quality issues handled explicitly (flags for fraud, malformed, missing fields)
- [ ] Silver tables idempotent (OVERWRITE mode safe to re-run without duplicates)
- [ ] 3+ meaningful data-quality tests passing (row counts, NULLs, referential integrity)
- [ ] Notebook POC works end-to-end
- [ ] Late-arriving events: MVP not required; becomes relevant with dbt + incremental loads (Phase 2)
- [ ] (Optional) dbt migration complete with tests + documentation
