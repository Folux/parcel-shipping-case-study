# Skullport dbt (Silver layer — spike)

Minimal dbt project that builds the **Silver** layer on Databricks. This is a
spike to validate the dbt-on-serverless deployment path via Databricks Asset
Bundles before porting the full pipeline.

## What it does

- Reads the existing Bronze tables `skullport.raw.{labels,tracking_events}`
- Builds two models into **`skullport.silver_dbt`** (separate schema, so it does
  not touch the notebook-built `skullport.silver.*`):
  - `labels` — CDC collapse + quality/fraud flags
  - `tracking_events` — dedup, canonical `event_name`, UTC-normalized `event_at`
- Runs generic tests (`unique`, `not_null`, `relationships`, `accepted_values`)

Models and tests run together via `dbt build`.

## How it runs (no local cluster needed)

dbt does **not** run locally. It runs as a **dbt task in a Databricks Job**
(serverless), executing models against a serverless SQL warehouse. Databricks
auto-generates the connection profile from the warehouse — no credentials in
this repo.

From the repo root:

```bash
databricks bundle validate -t dev
databricks bundle deploy   -t dev
databricks bundle run skullport_dbt_silver -t dev --var="warehouse_id=<warehouse-id>"
```

`<warehouse-id>`: SQL Warehouses → your serverless warehouse → Connection details.

> Edit `databricks.yml` → `targets.dev.workspace.host` to your Free Edition URL,
> or deploy with a configured CLI profile (`-p <profile>`).

## Layout

```
dbt/
├── dbt_project.yml
└── models/silver/
    ├── _silver__sources.yml   # skullport.raw source
    ├── _silver__models.yml    # tests
    ├── labels.sql
    └── tracking_events.sql
```
