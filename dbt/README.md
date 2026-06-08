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

dbt does **not** run locally. It runs as a **dbt task in a Databricks Job**
(serverless), executing models against a SQL warehouse. The connection profile
is generated from the warehouse — no credentials in this repo.

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

## Schema routing

The bundle's dbt task sets the target schema to `silver`. The `gold` folder
overrides `+schema: gold` in `dbt_project.yml`, and the
`generate_schema_name` macro makes that an absolute name (not `silver_gold`).
