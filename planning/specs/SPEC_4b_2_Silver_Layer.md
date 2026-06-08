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

**Source**: Deduplicate and parse `raw.tracking_events`, conform event codes/types, normalize timestamps

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `event_id` | String | NO | Unique event ID |
| `label_id` | String | NO | Foreign key to silver.labels |
| `carrier` | String | NO | Carrier name |
| `event_code` | String | YES | Original carrier event code (USPS/DHL); NULL for type-based carriers — preserved for traceability |
| `event_type` | String | YES | Original carrier event type (UPS/FEDEX); NULL for code-based carriers — preserved for traceability |
| `event_name` | String | NO | **Canonical** event conformed from code/type: `picked_up`, `in_transit`, `out_for_delivery`, `delivered`, `unknown` |
| `event_at` | Timestamp | YES | Event time normalized to UTC (NULL only if truly unparseable) |
| `event_received_at` | Timestamp | NO | System received timestamp |
| `location_zip` | String | YES | Scan location ZIP code |
| `raw_payload` | String | YES | Original carrier payload |
| `is_malformed_timestamp` | Boolean | NO | Source `event_at` was a corrupted format (separators/time/zone destroyed) or unparseable (~1%) |
| `is_missing_event_type` | Boolean | NO | Both event_code and event_type NULL → `event_name='unknown'` (~1%) |
| `is_event_on_voided_label` | Boolean | NO | Event on a voided label (~5% of voided labels) |
| `inserted_at` | Timestamp | NO | When Silver ETL ran and inserted this row (UTC) |

**Transformation Logic**:
- **Deduplicate**: Remove duplicate event_ids, keep last one (by event_received_at)
- **Conform `event_name`**: Map carrier-specific code/type into a canonical event name (see mapping below) — handles schema drift across carriers
- **Normalize `event_at` to UTC**: Rewrite every carrier/corrupted timestamp variant into an explicit-offset ISO-8601 string, then parse once (see normalization below)
- **Preserve** original `event_code` / `event_type` for traceability
- Flag malformed patterns (malformed_timestamp, missing_event_type)
- Join to silver.labels to check if label is voided

**Canonical `event_name` mapping** (schema-drift conformance):

| Canonical | USPS (code) | UPS (type) | FEDEX (type) | DHL (code) |
|-----------|-------------|------------|--------------|------------|
| `picked_up` | 0300 | PICKUP | PICKUP | PU |
| `in_transit` | 0301 | IN_TRANSIT | IN_TRANSIT | IT |
| `out_for_delivery` | 0310 | OUT_FOR_DELIVERY | OUT_FOR_DELIVERY | OFD |
| `delivered` | 0320 | DELIVERED | DELIVERED | DL |
| `unknown` | _(missing / unmapped)_ | | | |

**Timestamp normalization** (`event_at` → UTC). The generator emits carrier-specific and deliberately-corrupted formats; Silver canonicalizes them to one explicit-offset ISO string, then parses with `try_to_timestamp`:

| Source format | Example | Handling |
|---------------|---------|----------|
| Offset (USPS) | `2026-06-06T05:30:00-05:00` | kept as-is (offset is explicit) |
| Z / UTC (UPS) | `2026-06-06T10:30:00Z` | kept as-is |
| Plain, no tz (FEDEX) | `2026-06-06T10:30:00` | assume UTC (append `Z`) |
| Abbreviation (DHL) | `2026-06-06T05:30:00 EST` | swap abbr → numeric offset (`-05:00`, …) |
| Corrupted: no separators | `20260606T103000` | rebuild ISO, assume UTC (tz destroyed → flag malformed) |
| Corrupted: wrong separators | `2026/06/06T10:30:00` | slashes→dashes, assume UTC (flag malformed) |
| Corrupted: date only | `2026-06-06` | midnight UTC (flag malformed) |

> The abbreviation→offset mapping mirrors the generator (EST −5, EDT −4, CST −6, CDT −5, MST −7, MDT −6, PST −8, PDT −7), so DHL events round-trip back to the correct UTC instant.

**Data Organization**:
- Events stored in received order (not necessarily chronological by event_at)
- Out-of-order events are valid; sequence can be reconstructed from event_name and timestamps in downstream analytics
- Ordering does not affect data lake correctness

---

## Data Quality Handling

**Strategy**: Keep all rows (don't drop), flag suspicious/malformed data, handle gracefully

**Specific Rules**:

- **Malformed timestamps** (`is_malformed_timestamp`):
  - Corrupted source formats are repaired best-effort and parsed as UTC (the timezone was destroyed by corruption, so the instant may be off by hours)
  - Truly unparseable strings → `event_at` = NULL
  - Either way: keep row, set flag = true (downstream can exclude flagged events from time-sensitive metrics)

- **Missing event type** (`is_missing_event_type`):
  - Both event_code AND event_type NULL → keep row, set flag = true
  - `event_name` = `'unknown'`

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
