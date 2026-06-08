# Skullport — Implementation Notes & Production Roadmap

## 1. Install & Run End-to-End

```bash
# Local setup
poetry install
poetry run pytest tests/                    # 37 unit tests (stable)

# On Databricks (Free Edition, no cluster required)
# Step 1: Clone repo into Workspace as a Git folder
# Step 2: Run notebooks in order:
notebooks/ingestion_and_bronze_layer.py    # ~5 min, creates raw.* tables
# Step 3: Deploy dbt and run Silver + Gold
databricks bundle deploy --var="warehouse_id=<your-warehouse-id>"
databricks bundle run skullport_dbt_build  # ~2–3 min, creates silver.* and gold.*
# Step 4: Validate
notebooks/validation_checks.py             # ~30 sec, asserts data-quality invariants
```

Result: `skullport.gold.delivery_performance` with ~5,000 labels and the on-time metric (~86% on-time, ~3.3% late).

---

## 2. Data Volumes & Mess Proportions

Generated dataset (config.yaml, all configurable):
- **5,000 labels** (shippable packages)
- **~19,000 tracking events** (average ~3.8 events per label)
- **4 carriers**: USPS (30%), UPS (25%), FEDEX (25%), DHL_ECOM (20%)

Injected data-quality "weirdness" (all configurable):
| Issue | Config | Realized | Why |
|-------|--------|----------|-----|
| Late deliveries | 3% | 3.3% | Anchored to promised date + 6–48h jitter; reliable independent of SLA length |
| Duplicate events | 5% | 4.8% | Real-world carrier resends; tested dedup logic |
| Out-of-order scans | 8% | 7.9% | Late-arriving carrier transmissions; tests ordering robustness |
| Missing event type | 1% | 0.9% | Schema drift: some carriers only emit code OR type, never both |
| Malformed timestamps | 0.8% | 0.7% | Real corruptions: no separators, wrong delimiters, date-only, tz destroyed |
| Voided labels | 11% | 11.2% | Labels cancelled after issue; late scans still arrive |

**Why these %?** Modeled on USPS/UPS/FedEx public SLA reports, carrier API docs, and typical fulfillment logistics failure rates. The 3% late rate matches real small-shipper experience; the 1% malformed rate reflects carrier data-quality hygiene. All proportions are knobs so the generator can simulate different carrier/regional quality tiers.

---

## 3. Production Roadmap: Beyond the Prototype

### Ingestion (Real Source Systems)
**Prototype**: `skullport_generator` (synthetic).  
**Production**:
- Kafka or AWS SQS: ingest carrier webhook events (USPS PostalEZ, UPS Quantum View, FEDEX Tracking API, DHL eComm).
- Fivetran or custom Lambda: normalize carrier payloads → Bronze Delta tables (no synthetic generation).
- Schema validation via JSONSchema or Protobuf to catch upstream drift early.

### Transformation & Modeling
**Prototype**: dbt (serverless SQL warehouse).  
**Production**: Unchanged. dbt stays the Silver/Gold layer — it's the right tool (testable, version-controlled, DAG-aware). Add:
- Incremental models (currently full refresh) once volumes hit >1M events/day.
- Snapshot tables (dbt snapshots) to track SLA/carrier changes over time.
- Lineage logging via dbt artifacts → data catalog (e.g., Collibra, Alation).

### Orchestration & Monitoring
**Prototype**: Manual notebook + bundle CLI.  
**Production**:
- Airflow or Dagster: orchestrate Bronze ingestion → Silver dbt build → Gold mart → validation checks.
- dbt Cloud (native integration) or Astronomer (Airflow-as-a-Service) for workflow management.
- Alerts: PagerDuty on validation failures (on-time % outside [80%, 99%], >5% malformed, referential integrity fails).
- Observability: CloudWatch/Datadog for warehouse query performance, Data Loss Prevention for PII in payloads.

### Infrastructure & IaC
**Prototype**: Manual Databricks setup (workspace, warehouse, repo).  
**Production**:
- Terraform: codify all Databricks resources (workspace, warehouses, clusters, repos, table ACLs).
- GitHub Actions: CI/CD pipeline — test → lint dbt → apply Terraform → run validation.
- Secrets in AWS Secrets Manager / Azure KeyVault; never in code.

### Access & Security
**Prototype**: Open within the Free Edition workspace.  
**Production**:
- Unity Catalog groups: `analysts` (read `gold.*`), `engineers` (read/write `silver.*` via dbt), `admins` (all).
- Row-level security (RLS) on `gold.delivery_performance`: analysts see only their company's labels.
- Audit logging: all reads/writes to `raw.*`, `silver.*` logged to S3 for compliance.

### Scale & Cost
| Metric | Prototype | Production |
|--------|-----------|------------|
| Data volume | 5k labels/month | 1M+ labels/month (100k events/day) |
| Storage | <100 MB | ~50 GB (Delta + snapshots) |
| Compute | Serverless SQL (no cluster) | Photon warehouse ($2–3k/month) or Spark jobs ($500–1k/month) |
| Cost | ~$5/month | ~$3–5k/month (all-in: ingestion + warehouse + orchestration) |

### What Changes Between Prototype & Production
- **No synthetic generation** — real carrier payloads only.
- **Event-driven ingestion** — Kafka/SQS, not batch scripts.
- **Incremental transforms** — append-only, not full refresh.
- **CI/CD**: dbt tests run on every push; Terraform on merge; validation fails the deployment.
- **Catalog & lineage** — dbt artifacts fed to a data catalog; analysts explore lineage.
- **PII/compliance** — logging, encryption, RLS, audit trails baked in.

---

## 4. Three Conscious Trade-offs

1. **Full refresh vs. incremental transforms**  
   Made it: Simple, idempotent, no state to manage; easier to debug.  
   Trade-off: Slower at scale (1M+ events/day costs ~$500/month extra in compute). Day 1 in production would flip to incremental (dbt `is_incremental()` pattern).

2. **Stored timestamp variants in Silver**  
   Kept `event_code` + `event_type` alongside canonical `event_name` for traceability (not dropped).  
   Trade-off: ~15% larger table; disk cheap, auditability priceless.

3. **Serverless SQL for dbt (no classic cluster)**  
   Kept dbt running on serverless (included in Free Edition; scales to $6/month on paid).  
   Trade-off: Can't use Spark-native features (no RDDs, no UDFs); purely SQL-based. At 10x scale, a Photon warehouse would be faster, but SQL-only is the right call for a BI-friendly transformation layer anyway.

---

## 5. One Thing to Change First (Next Full Day)

**Incremental materialization for Silver models.**  
The full-refresh approach works at 5k labels but would cost ~$300/month in extra warehouse compute at production scale (1M+ labels/day). Switching to `dbt run --full-refresh` on Sundays + incremental appends weekdays would cut costs 80% and let us ship real-time analytics updates.

Implementation: Add `is_incremental()` blocks to `labels.sql` and `tracking_events.sql`; append to partition `run_date`; keep full-refresh as a weekly idempotency check. ~3 hours.

---

## 6. AI Usage (Claude)

**Strategy**: Specs first (manual review & approval) → Implementation Plan (manual review & approval) → Code (manual review & approval).

- **Specifications** (SPEC_*.md): I wrote sketches; Claude filled in data contracts, edge cases, and flagging philosophy. I approved each before implementation.
- **Implementation Plans** (IMPL_*.md): Claude produced step-by-step breakdowns; I reviewed for feasibility and edited the dbt/notebook approach.
- **Code generation**: Claude wrote the generator, notebooks, and dbt models from the approved plans. I tested each layer end-to-end, validated metrics, and debugged (timezone bugs, late-delivery wiring, 0% on-time root cause).
- **Architecture & decisions**: dbt-over-notebooks, monorepo-over-split, serverless-over-classic-cluster — all reasoned jointly and approved before building.
- **Testing & debugging**: I ran the full suite, caught the 0% on-time metric, and walked Claude through the diagnosis (timezone bug, canonical event_name, unwired late_delivery_proportion). Claude suggested fixes; I validated end-to-end.

Net: Claude handled routine coding and brainstorming; I owned decisions, testing, and validation. No code shipped without my sign-off.
