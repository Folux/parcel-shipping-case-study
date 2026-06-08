# Bronze Layer Specification (4b.1)

## Overview

Build a production-grade data pipeline in Databricks that transforms synthetic data from Section 4a into analytics-ready mart tables. The pipeline processes `raw.labels` and `raw.tracking_events` through three layers (Bronze, Silver, Gold) with explicit handling of data quality issues.

---

## Getting Bronze Tables to Databricks (Step 1: Deploy Generator)

**Step 1: Push to GitHub**
- Commit and push the project to GitHub (public repo)

**Step 2: Create Databricks Workspace**
- Sign up for Databricks Free Edition
- Create workspace
- Get workspace URL

**Step 3: Connect GitHub to Databricks**
- In Databricks: Settings → Developer → Personal access tokens
- Generate token and authenticate with GitHub
- Grant Databricks repo access

**Step 4: Clone Repo into Databricks**
- In Databricks: Repos → Add Repo
- Paste GitHub URL
- Clone repo into workspace

**Step 5: Run Generator Notebook**
- Open `notebooks/skullport_generator.py` in Databricks
- Click "Run all"
- Wait for completion

**Step 6: Verify Bronze Tables (Generator Output)**
- Check Databricks Catalog
- Verify tables exist:
  - `pirate_ship.bronze.labels` (should have ~5000 rows)
  - `pirate_ship.bronze.tracking_events` (should have ~30000 rows)

**Note**: The generator creates the Bronze tables directly. In data lake terminology, these are the "landing zone" tables (idempotent, schema as-is from source).

---

