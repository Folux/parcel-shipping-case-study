# Quick Start

Two ways to run the pipeline:

- **A. Notebooks** — Bronze → Silver → Gold, no extra tooling. Fastest way to see results.
- **B. dbt via Databricks Asset Bundle** — builds the Silver layer with dbt, deployed from the CLI (the packaging the case study asks for).

The notebooks auto-create the `skullport` Unity Catalog catalog, so no manual catalog setup is needed.

---

## A. Run the notebooks

1. Log into your Databricks workspace
2. **New** → **Git folder**
3. Repo URL: `https://github.com/Folux/parcel-shipping-case-study.git` → **Clone**
4. In `parcel-shipping-case-study/notebooks/`, run **Run all** on each, in order:
   - `ingestion_and_bronze_layer.py` → creates `skullport.raw.labels` (~5,000) and `skullport.raw.tracking_events` (~19,000)
   - `silver_layer.py` → `skullport.silver.labels`, `skullport.silver.tracking_events`
   - `gold_layer.py` → `skullport.gold.delivery_performance` (one row per label, on-time metric)
   - `validation_checks.py` → asserts data-quality checks across Silver + Gold (fails loudly if anything is off)
5. Done ✅

---

## B. Run the Silver layer with dbt (Asset Bundle)

This deploys a Databricks Job that runs the dbt Silver models. It reads the
existing `skullport.raw.*` tables (run **A** steps 1–4 first) and writes to
`skullport.silver_dbt.*` — a separate schema, so it won't disturb the notebook
output.

### 1. Install the Databricks CLI

```bash
# macOS / Linux (Homebrew)
brew install databricks/tap/databricks

# or via the universal install script
curl -fsSL https://raw.githubusercontent.com/databricks/setup-cli/main/install.sh | sh
```
Verify: `databricks --version` (needs v0.218+ for bundles).

### 2. Authenticate to your workspace

```bash
databricks auth login --host https://YOUR-WORKSPACE.cloud.databricks.com
```
Follow the browser prompt. This stores a profile the CLI reuses.

### 3. Configure a SQL warehouse

dbt executes its models against a SQL warehouse. You only need its **ID** — the
bundle's dbt task builds the connection from that (no local `profiles.yml`).

- In Databricks: **SQL** → **SQL Warehouses** → use an existing warehouse or **Create**.
- Open it → **Connection details**. The **warehouse ID is the last segment of the
  HTTP path**:

  ```
  HTTP path:  /sql/1.0/warehouses/0123456789abcde01
                                   ^^^^^^^^^^^^^^^^  ← this is your warehouse_id
  ```

  (Ignore Server hostname / JDBC URL / OAuth URL — those are for direct client
  connections, which this bundle does not use.)

### 4. Configure locally (one-time, nothing committed)

Workspace host and warehouse ID are environment-specific, so they live in a
gitignored `.env` — not in the repo:

```bash
cp .env.example .env
# edit .env:
#   DATABRICKS_CONFIG_PROFILE = your auth profile (see `databricks auth profiles`)
#   BUNDLE_VAR_warehouse_id   = the ID from step 3
source .env
```

- **Host** comes from your `databricks auth login` profile (step 2).
- **Warehouse ID** comes from `BUNDLE_VAR_warehouse_id`.

### 5. Deploy and run

From the repo root — `dev` is the default target, so no flags are needed:

```bash
databricks bundle validate
databricks bundle deploy
databricks bundle run skullport_dbt_silver
```

### 6. Verify

```sql
SELECT COUNT(*) FROM skullport.silver_dbt.labels;             -- ~5,000
SELECT event_name, COUNT(*)
FROM skullport.silver_dbt.tracking_events
GROUP BY event_name;                                          -- canonical names
```

See `dbt/README.md` for project layout and details.

---

## Catalog overview

| Table | Built by | Notes |
|-------|----------|-------|
| `skullport.raw.labels` / `…tracking_events` | Bronze notebook | Synthetic landing zone |
| `skullport.silver.labels` / `…tracking_events` | Silver notebook | Cleaned, conformed |
| `skullport.silver_dbt.labels` / `…tracking_events` | dbt (Asset Bundle) | Same logic, built by dbt |
| `skullport.gold.delivery_performance` | Gold notebook | One row per label, on-time metric |
