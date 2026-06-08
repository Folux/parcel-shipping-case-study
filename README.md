# Skullport — Parcel Shipping Data Pipeline

A synthetic **parcel-shipping data pipeline** for the Delivery Performance Mart
case study, built on Databricks (Free Edition compatible). It generates messy,
realistic carrier data and refines it through a medallion architecture into an
analytics-ready mart that answers: **what % of shipments are delivered on time, and where do delays cluster?**

```
 PySpark generator        dbt (Asset Bundle)              Databricks SQL
┌──────────────────┐   ┌────────────────────────────┐   ┌────────────────┐
│  Bronze (raw)    │──▶│  Silver         Gold        │──▶│  validation    │
│  raw.labels      │   │  silver.labels  gold.       │   │  checks        │
│  raw.tracking_…  │   │  silver.track…  delivery_…  │   │  (assertions)  │
└──────────────────┘   └────────────────────────────┘   └────────────────┘
```

All tables live in the Unity Catalog catalog **`skullport`** (auto-created).

## Architecture & tool choices

The case study asks for a real combination of **PySpark, Databricks SQL, and dbt** — each used where it earns its place:

| Layer | Tool | Why |
|-------|------|-----|
| **Bronze** — generate synthetic `raw.labels` & `raw.tracking_events` | **PySpark** (`src/skullport_generator/`) | Procedural data generation with carrier-specific formats, CDC history, and injected data-quality issues is naturally imperative Python; writes Delta via Spark. |
| **Silver + Gold** — clean / conform / model | **dbt** (`dbt/`) | Declarative, testable, version-controlled SQL with a dependency DAG (`ref`), generic tests, and bundle-based deployment. The production transformation layer. |
| **Validation** — data-quality gate | **Databricks SQL** (`notebooks/validation_checks.py`) | Ad-hoc, range-based assertions (on-time band, no impossible states, referential integrity) run interactively as a gate, beyond what generic dbt tests express. |

**Medallion layers**

- **Bronze** (`skullport.raw.*`) — raw landing zone, intentionally messy: CDC update rows, duplicates, late arrivals, four carrier timestamp formats (offset / Z / plain / tz-abbreviation), schema drift (per-carrier `event_code` vs `event_type`), malformed timestamps, missing fields, voided-label scans.
- **Silver** (`skullport.silver.*`) — cleaned & conformed: CDC collapse to latest state, dedup, **canonical `event_name`** (carrier codes → `picked_up`/…/`delivered`), **UTC-normalized `event_at`**, and explicit data-quality flags (keep all rows, flag rather than drop).
- **Gold** (`skullport.gold.delivery_performance`) — one row per label with the **`is_delivered_on_time`** metric and supporting facts/dimensions.

## Running it

See **[QUICK_START.md](QUICK_START.md)** for the full walkthrough. In short:

1. **Bronze** — run `notebooks/ingestion_and_bronze_layer.py` in Databricks.
2. **Silver + Gold** — deploy & run dbt via the Asset Bundle:
   ```bash
   databricks bundle deploy --var="warehouse_id=<id>"
   databricks bundle run skullport_dbt_build
   ```
3. **Validation** — run `notebooks/validation_checks.py`.

## Repository layout

```
src/skullport_generator/   # PySpark synthetic data generator (Bronze)
notebooks/                 # ingestion_and_bronze_layer.py, validation_checks.py
dbt/                       # Silver + Gold models, tests, macros
databricks.yml             # Asset Bundle: deploys the dbt job
config.yaml                # Generator volumes, mess proportions, target catalog
tests/                     # pytest unit tests for the generator
planning/                  # specs & implementation plans per layer
notes/                     # running project log
instructions/              # the original case study brief
```

## Local development

```bash
poetry install
poetry run pytest tests/        # 180 unit tests for the generator
```

The generator is configuration-driven (`config.yaml`): data volume, every
mess/edge-case proportion, carrier distribution, and the target
`catalog_name` / `schema_name` — nothing hard-coded. Reproducible via
`random_seed`. It can run locally for tests, but its production target is the
Databricks notebook wrapper.

## Testing

- **Generator** — `pytest tests/` (unit tests, deterministic via seed).
- **dbt** — generic tests (`unique`, `not_null`, `relationships`,
  `accepted_values`) run as part of `dbt build`.
- **Pipeline** — `notebooks/validation_checks.py` asserts cross-layer
  data-quality invariants on the built tables.

## Notes & future work

Post-MVP improvements are tracked in [`planning/NICE_TO_HAVE.md`](planning/NICE_TO_HAVE.md)
(incremental/merge loads, an orphaned-events table, richer timezone realism,
dbt test expansion, …). The running build log is in
[`notes/`](notes/Pirate_Ship_case_study_notes.md).
