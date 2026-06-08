# Implementation Plan: 4a.2. Silver Layer

## Overview

Transform raw Bronze data into clean, deduplicated, conformed Silver tables via a Databricks notebook (Phase 1). Phase 2 dbt migration will be planned once notebook is complete.

---

## Phase 1: Notebook MVP

### Deliverable
Single notebook: `silver_layer.py` that reads Bronze, transforms, writes Silver tables (idempotent OVERWRITE mode)

### Implementation Steps

**Step 1: Load Bronze**
- Read `raw.labels` and `raw.tracking_events` into DataFrames
- Log row counts

**Step 2: Transform `silver.labels`**
- Collapse CDC: keep latest row per `label_id`
- Add fraud flags:
  - `can_be_weight_fraud`: weight 1000-1120 oz
  - `can_be_void_fraud`: voided 2-5 days after creation
  - `can_be_insurance_anomaly`: value = 0 but insured
  - `can_be_missing_zip`: origin or dest ZIP missing
- Add `inserted_at` timestamp
- Write with OVERWRITE mode

**Step 3: Transform `silver.tracking_events`**
- Deduplicate: remove duplicates, keep last by `event_received_at`
- Merge event codes/types into single `event_name` column
- Parse `event_at` to TIMESTAMP (handle all carrier formats)
  - Fallback to `event_received_at` if unparseable
- Add flags:
  - `is_malformed_timestamp`: couldn't parse
  - `is_missing_event_type`: both NULL
  - `is_event_on_voided_label`: label is voided
- Add `inserted_at` timestamp
- Write with OVERWRITE mode

**Step 4: Cleanup**
- Drop orphaned events (label_id not in labels)
- Log orphaned count

**Step 5: Validation**
- Row counts reasonable (~5000 labels, ~18000+ events after dedup)
- No unexpected NULLs in required columns
- Flags are boolean
- Referential integrity: all event.label_id exist in labels
- Print summary

---

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| **Notebook MVP** | Iterate quickly, test logic before formalizing |
| **OVERWRITE mode** | Simple, safe, idempotent |
| **Keep all rows** | Preserve audit trail; flag instead of drop |
| **Parse with fallback** | Maximize data retention |

---

## Testing (Phase 1)

- SQL validation queries at end of notebook
- Row counts, NULLs, referential integrity
- Fraud flag distributions

---

## Phase 2: dbt (if time permits)

dbt migration and detailed planning will be done once Phase 1 notebook is complete and working.

---

## Success Criteria

- [ ] Notebook reads Bronze, writes Silver (idempotent)
- [ ] Fraud flags computed correctly
- [ ] Timestamps parsed and validated
- [ ] Referential integrity maintained
- [ ] Validation checks pass
- [ ] Row counts reasonable
