# Implementation Plan: 4a.2. Silver Layer

## Overview

Transform raw Bronze data into clean, deduplicated, conformed Silver tables. Start with a **Databricks notebook MVP** (Phase 1), then migrate to **dbt** (Phase 2, if time permits).

**Phase 1 Deliverable**: Notebook that reads Bronze, applies transformations, writes Silver tables (idempotent OVERWRITE mode)
**Phase 2 Deliverable**: dbt models + tests + documentation

---

## Project Structure

### Phase 1 (Notebook MVP)

```
notebooks/
└── silver_layer.py          # Databricks notebook
    - Load Bronze tables
    - Collapse CDC (labels)
    - Deduplicate events
    - Parse timestamps & merge event codes
    - Add fraud flags
    - Write Silver tables
    - Validation checks
```

### Phase 2 (dbt, if time permits)

```
dbt/
├── dbt_project.yml
├── profiles.yml
├── models/
│   ├── staging/
│   │   ├── stg_raw_labels.sql       # Clean + conform raw.labels
│   │   └── stg_raw_events.sql       # Clean + conform raw.tracking_events
│   └── marts/
│       ├── silver_labels.sql        # Final silver.labels (collapse CDC)
│       └── silver_events.sql        # Final silver.tracking_events (deduplicate)
├── tests/
│   ├── generic/
│   │   └── [dbt generic tests]      # Schema, uniqueness, referential integrity
│   └── singular/
│       └── [custom tests]           # Edge cases
└── README.md                        # dbt setup & run instructions
```

---

## Language & Environment

Same as Bronze layer:
- **Python**: 3.10+
- **Databricks Runtime**: 16.4 LTS
- **Spark**: 3.5.2
- **dbt** (Phase 2): dbt-databricks adapter

---

## Dependencies (Phase 1 Notebook)

No new dependencies beyond Bronze layer:
- PySpark (already available in Databricks)
- Pandas (already available)
- Python standard library (datetime, logging)

**Phase 2 (dbt)**:
- `dbt-databricks` package
- `dbt-core` (included in dbt-databricks)

---

## Implementation Sequence: Phase 1 (Notebook MVP)

### Step 1: Setup & Load Bronze
- Initialize Databricks notebook
- Load `raw.labels` and `raw.tracking_events` into DataFrames
- Log row counts

### Step 2: Silver Labels Transformation
- Collapse CDC: keep latest row per `label_id`
- Add fraud flags:
  - `can_be_weight_fraud`: weight in 1000-1120 oz range
  - `can_be_void_fraud`: voided 2-5 days after creation
  - `can_be_insurance_anomaly`: declared_value_cents = 0 but insured
  - `can_be_missing_zip`: origin_zip or dest_zip missing
- Add `inserted_at` = current timestamp
- Write to `silver.labels` (OVERWRITE mode)

### Step 3: Silver Tracking Events Transformation
- Deduplicate: remove duplicate event_ids, keep last by `event_received_at`
- Merge event codes/types:
  - Create `event_name` column: COALESCE(event_code, event_type, "UNKNOWN")
  - Set to NULL if both are NULL
- Parse `event_at`:
  - Handle all carrier formats (offset, Z, plain, timezone abbr)
  - On parse failure: use `event_received_at` as fallback
  - Add `is_malformed_timestamp` flag if unparseable
- Add flags:
  - `is_malformed_timestamp`: couldn't parse event_at
  - `is_missing_event_type`: both event_code and event_type NULL
  - `is_event_on_voided_label`: join to labels, check voided_at is not NULL
- Add `inserted_at` = current timestamp
- Write to `silver.tracking_events` (OVERWRITE mode)

### Step 4: Referential Integrity & Cleanup
- Drop orphaned events (label_id not in silver.labels)
- Log orphaned event count
- Add to NICE_TO_HAVE: capture to `silver.tracking_events_orphaned` table

### Step 5: Validation Checks
- Row counts: labels ~5000, events ~18000+ (after deduplication)
- NULLs: no unexpected NULLs in required columns
- Flags: all booleans (0/1)
- Referential integrity: all event.label_id exist in labels
- Print validation summary

---

## Implementation Sequence: Phase 2 (dbt, if time permits)

### Step 1: dbt Setup
- Initialize dbt project
- Configure Databricks connection in profiles.yml
- Set up directory structure (models, tests, macros)

### Step 2: Create Staging Models
- `stg_raw_labels.sql`: type conformance, basic cleaning
- `stg_raw_events.sql`: type conformance, event_at parsing, merge event codes

### Step 3: Create Mart Models
- `silver_labels.sql`: collapse CDC, add fraud flags, set inserted_at
- `silver_events.sql`: deduplicate, add all flags, referential integrity

### Step 4: Add dbt Tests
- Generic tests: schema, uniqueness on label_id/event_id, relationships (referential integrity)
- Singular tests: fraud flag distributions, malformed timestamp count, etc.
- Great Expectations or dbt-native assertions

### Step 5: Documentation & Deploy
- README with dbt commands (dbt run, dbt test, dbt docs)
- Tag models, add descriptions to columns
- Deploy to Databricks via Databricks Asset Bundle (if time)

---

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| **Notebook first** | Iterate quickly, test logic before formalizing in dbt |
| **OVERWRITE write mode** | Simple, safe, idempotent (no incremental complexity in MVP) |
| **Keep all rows** | Preserve audit trail; flag suspicious data instead of dropping |
| **Parse event_at with fallback** | Maximize data retention; use event_received_at if malformed |
| **Collapse CDC to latest** | Single row per label (what analytics want); history in Bronze if needed |
| **Fraud flags, not quarantine** | Transparent: data available downstream for investigation |
| **Phase 2 = dbt** | Industry standard; enables testing, lineage, documentation |

---

## Testing Strategy

### Phase 1 (Notebook):
- SQL validation queries at end of notebook
- Row counts, NULLs, referential integrity checks
- Fraud flag distributions (sanity check)

### Phase 2 (dbt):
- dbt generic tests (schema, uniqueness, relationships)
- Custom singular tests for edge cases
- Great Expectations or dbt assertions

---

## Success Criteria

- [ ] Notebook MVP reads Bronze, writes Silver (idempotent)
- [ ] All fraud flags computed correctly
- [ ] Timestamps parsed and validated
- [ ] Referential integrity maintained
- [ ] Validation checks pass
- [ ] Row counts reasonable (~5000 labels, ~18000+ events after dedup)
- [ ] (Optional) dbt migration complete with tests

---

## Deployment

### Phase 1:
- Notebook runs on-demand or via Databricks job
- Tables written to `workspace.raw.labels`, `workspace.raw.tracking_events` (via config)

### Phase 2 (if included):
- Package as dbt project
- Deploy via Databricks Asset Bundle (`databricks bundle deploy`)
- Tables managed by dbt DAG
