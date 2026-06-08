# Quick Start

The pipeline has three stages, each using the tool that fits it best:

| Stage | Tool | How you run it |
|-------|------|----------------|
| **Bronze** (synthetic data → `skullport.raw.*`) | PySpark | Databricks notebook |
| **Silver + Gold** (`skullport.silver.*`, `skullport.gold.*`) | dbt | Asset Bundle (CLI) |
| **Validation** (data-quality assertions) | Databricks SQL | Databricks notebook |

The Bronze notebook auto-creates the `skullport` Unity Catalog catalog — no manual catalog setup.

---

## 1. Bronze — run the generator notebook

1. Log into your Databricks workspace
2. **New** → **Git folder** → repo URL
   `https://github.com/Folux/parcel-shipping-case-study.git` → **Clone**
3. Open `parcel-shipping-case-study/notebooks/ingestion_and_bronze_layer.py` → **Run all**
   - Creates `skullport.raw.labels` (~5,000) and `skullport.raw.tracking_events` (~19,000)

---

## 2. Silver + Gold — run dbt via the Asset Bundle

dbt builds `skullport.silver.*` and `skullport.gold.*` (with tests) from the
Bronze tables, deployed as a Databricks Job.

### 2.1 Install the Databricks CLI

```bash
# macOS / Linux (Homebrew)
brew install databricks/tap/databricks

# or via the universal install script
curl -fsSL https://raw.githubusercontent.com/databricks/setup-cli/main/install.sh | sh
```
Verify: `databricks --version` (needs v0.218+ for bundles).

### 2.2 Authenticate to your workspace

```bash
databricks auth login --host https://YOUR-WORKSPACE.cloud.databricks.com
```
Follow the browser prompt. This stores a profile the CLI reuses (the bundle
reads the workspace host from it, so no URL is committed to the repo).

### 2.3 Get a SQL warehouse ID

dbt executes its models against a SQL warehouse — you only need its **ID**.

- In Databricks: **SQL** → **SQL Warehouses** → use an existing warehouse or **Create**.
- Open it → **Connection details**. The **warehouse ID is the last segment of the
  HTTP path**:

  ```
  HTTP path:  /sql/1.0/warehouses/0123456789abcde01
                                   ^^^^^^^^^^^^^^^^  ← this is your warehouse_id
  ```

### 2.4 Deploy and run

From the repo root. `dev` is the default target, so no `-t` flag is needed; the
warehouse ID is passed on deploy and baked into the job:

```bash
databricks bundle validate
databricks bundle deploy --var="warehouse_id=<your-warehouse-id>"
databricks bundle run skullport_dbt_build
```

(If your auth profile isn't the DEFAULT one, add `-p <profile>` to the commands.)

### 2.5 Verify

```sql
-- Silver
SELECT COUNT(*) FROM skullport.silver.labels;                 -- ~5,000
SELECT event_name, COUNT(*)
FROM skullport.silver.tracking_events
GROUP BY event_name;                                          -- canonical names

-- Gold
SELECT COUNT(*) FROM skullport.gold.delivery_performance;     -- ~5,000
SELECT ROUND(100.0*SUM(CASE WHEN is_delivered_on_time THEN 1 ELSE 0 END)/COUNT(*),1) AS pct_on_time
FROM skullport.gold.delivery_performance;                     -- ~86%
```

See `dbt/README.md` for project layout and details.

---

## 3. Validation — run the checks notebook

Open `notebooks/validation_checks.py` → **Run all**. It asserts data-quality
checks across Silver + Gold (row counts, referential integrity, the on-time
band, no impossible states, …) and fails loudly if anything is off.

---

## Catalog overview

| Table | Built by | Notes |
|-------|----------|-------|
| `skullport.raw.labels` / `…tracking_events` | Bronze notebook (PySpark) | Synthetic landing zone |
| `skullport.silver.labels` / `…tracking_events` | dbt | Cleaned, deduplicated, conformed |
| `skullport.gold.delivery_performance` | dbt | One row per label, on-time metric |
