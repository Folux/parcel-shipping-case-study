# Skullport Parcel Generator

This app is a simulator for parcel shipping traffic among the United States.
It has 2 components
* A **parcel generator** for generating random shipping labels and tracking events with realistic data flaws.
* A **etl project** for cleaning the generated flaws in the data and building a data mart on top of it.

The app runs on Databricks as platform for running and storing and uses dbt for transforming the data

## 1. Install & Run

### Generate and ingest the data (bronze layer)

1. Log into your Databricks workspace
2. From the left pane select *New* → *Git folder* → repo URL https://github.com/Folux/parcel-shipping-case-study.git → *Clone*
3. In the cloned repo open *parcel-shipping-case-study/notebooks/ingestion_and_bronze_layer.py* → select your running instance → click *Run all*

Creates 2 tables *skullport.raw.labels* (~5,000) and *skullport.raw.tracking_events* (~19,000) in the  

### Transform the data into a data mart (silver and gold layer)

1. In yor local machine, clone the Github repo https://github.com/Folux/parcel-shipping-case-study.git
2. Get the Databricks CLI to run *databricks* commands
```
brew install databricks/tap/databricks
```
3. From Databricks chose or provision a SQL Warehose and get it's id
   1. Select yor SQL Warehouse
   2. Go to Connection details
   3. The warehouse ID is the last segment of the HTTP path
   ```
   HTTP path:  /sql/1.0/warehouses/0123456789abcde01
                                    ^^^^^^^^^^^^^^^^  ← this is your warehouse_id
   ```
4. In your terminal, replace *<your-warehouse-id>* in bellow command with your SQL Warehouse id and run it
```bash
databricks bundle deploy --var="warehouse_id=<your-warehouse-id>"
databricks bundle run skullport_dbt_build
```
It will create the tables for the silver and gold layer in your Datalake.

### Testing

#### Parcel generator
1. Install `Poetry`
2. Run the tests
```bash
poetry install
poetry run pytest tests/
```

#### Data tests

With running the dbt models on Databricks they already ran the dbt tests.

There is a notebook to run additional tests on the tables
In the cloned repo open *parcel-shipping-case-study/notebooks/validation_checks.py* → select your running instance → click *Run all*

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

---

## 3. Production Roadmap: Beyond the Prototype

### Ingestion (Real Source Systems)
**Prototype**: `skullport_generator` (random sample data).  
**Production**: Kafka or AWS SQS

### Transformation & Modeling
**Prototype**: dbt (serverless SQL warehouse)
- Table materialization - all data is processed at once
**Production**: dbt (providioned SQL warehouse)
- Incremental materialization

### Orchestration & Monitoring
**Prototype**: Manual notebook + bundle CLI.  
**Production**:
- Airflow
- Alerts
- Grafana for logging

### Infrastructure & IaC
**Prototype**: Manual Databricks setup  
**Production**:
- Terraform
- GitHub Actions for CI/CD
- Secrets in AWS Secrets Manager

## 4. Three Conscious Trade-offs

1. **Full refresh vs. incremental transforms**  
   I made it simple respecting the tight time.  
   Different order of arrival of scans and delayed transmission of the data is no longer a problem, because the data in it's total is always consistent.
   With incremental loads you would have to pick a different materialization strategy in dbt for merging late arriving events into existing objects.

2. **Raw layer and bronze layer is the same**  
   Because the raw layer, created by the generator, is identical to the bronze layer, I decided to merge them.
   It they were separate then you could use incremental loads for the bronze layer. Without incremental loads, the app would probably not manage huge production loads. And this way we lost the special handling of late arriving events, what was no longer needed.

3. **Only delivering 1 metric in the gold layer**  
   Being mindful with the time, I started only delivering one metric on the gold layer. This proves that everything works end to end.
   Adding more metrics to dbt models is easy and fast, I did not get to it, because the above 2 tradeoffs were more important than this one.
---

## 5. One Thing to Change First (Next Full Day)

For sure I would add incremental materialisation to the dbt models and separate the raw layer from the bronze layer to show the dynamics when loading incrementally and dealing with late arriving events. 

---

## 6. AI Usage (Claude)

Claude handled routine coding and brainstorming; I owned decisions, testing, and validation. No code shipped without my sign-off.

**Strategy**: Specs first (manual review & approval) → Implementation Plan (manual review & approval) → Code (manual review & approval).

- **Specifications** (SPEC_*.md): I wrote sketches; Claude filled in data contracts, edge cases, and flagging philosophy. I approved each before implementation.
- **Implementation Plans** (IMPL_*.md): Claude produced step-by-step breakdowns; I reviewed for feasibility and edited the dbt/notebook approach.
- **Code generation**: Claude wrote the generator, notebooks, and dbt models from the approved plans. I tested each layer end-to-end, validated metrics, and debugged (timezone bugs, late-delivery wiring, etc.).
- **Architecture & decisions**: dbt-over-notebooks, monorepo-over-split, serverless-over-classic-cluster — all reasoned jointly and approved before building.
- **Testing & debugging**: I ran the full suite, and walked Claude through the diagnosis (timezone bug, canonical event_name, unwired late_delivery_proportion). Claude suggested fixes; I validated end-to-end.
