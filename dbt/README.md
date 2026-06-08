# Skullport dbt (Silver + Gold)

dbt project that builds the **Silver** and **Gold** layers on Databricks,
deployed via a Databricks Asset Bundle.

## What it does

- Reads the Bronze tables `skullport.raw.{labels,tracking_events}`
- Builds the Silver models into **`skullport.silver`**:
  - `labels` — CDC collapse + quality/fraud flags
  - `tracking_events` — dedup, canonical `event_name`, UTC-normalized `event_at`
- Builds the Gold model into **`skullport.gold`**:
  - `delivery_performance` — one row per label with the on-time metric
- Runs generic tests (`unique`, `not_null`, `relationships`, `accepted_values`)

dbt is the production transformation layer that owns Silver and Gold.
Models and tests run together via `dbt build`.

## How it runs (no local cluster needed)

It runs as a **dbt task in a Databricks Job**, executing models against a SQL warehouse. The connection profile
is generated from the warehouse.

From the repo root (see the top-level `QUICK_START.md` for full setup):

```bash
databricks bundle deploy --var="warehouse_id=<warehouse-id>"
databricks bundle run skullport_dbt_build
```

## Layout

```
dbt/
├── dbt_project.yml
├── macros/
│   └── generate_schema_name.sql   # absolute schema names (silver / gold)
└── models/
    ├── silver/
    │   ├── _silver__sources.yml   # skullport.raw source
    │   ├── _silver__models.yml    # tests
    │   ├── labels.sql
    │   └── tracking_events.sql
    └── gold/
        ├── _gold__models.yml      # tests
        └── delivery_performance.sql
```
