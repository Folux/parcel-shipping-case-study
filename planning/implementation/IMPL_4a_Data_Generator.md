# Implementation Plan: 4a. Synthetic Data Generator

## Overview

Build a production-grade Python project that generates synthetic data for `raw.labels` and `raw.tracking_events` Delta tables. The generator reads configuration from YAML, produces realistic messy data, and writes to Databricks Unity Catalog.

**Primary requirement**: `num_labels` (volume driver)
**Derived outcome**: Event count (naturally calculated from label characteristics)

---

## Project Structure

```
skullport-generator/
├── pyproject.toml                 # Project metadata, dependencies (Poetry)
├── poetry.lock                    # Locked dependency versions (committed to git)
├── .gitignore                     # Git ignore rules
├── README.md                      # Installation, usage, configuration guide
├── config.yaml                    # Example generator configuration
├── src/
│   └── skullport_generator/
│       ├── __init__.py
│       ├── config.py              # Configuration loading & validation (Pydantic)
│       ├── schemas.py             # PySpark StructType definitions
│       ├── labels_generator.py    # raw.labels data generation
│       ├── events_generator.py    # raw.tracking_events data generation
│       ├── writer.py              # Write to Databricks Unity Catalog
│       └── main.py                # Entrypoint (orchestration)
├── tests/
│   ├── __init__.py
│   ├── test_schemas.py            # Schema validation tests
│   └── test_data_quality.py       # Data quality spot-checks
└── notebooks/
    └── run_generator.py           # Databricks notebook wrapper
```

**Why this structure?**
- `src/` — Package code (standard Python project layout)
- `tests/` — Unit & integration tests (pytest discovers them automatically)
- `notebooks/` — Databricks-specific entrypoint (runs the generator in Databricks)
- Root files — Project metadata, config example, git rules

---

## Language & Environment

### Python Version
- **Requirement**: `python = "^3.10"` (3.10, 3.11, 3.12, 3.13, etc.)
- **Why 3.10+**:
  - Spark 3.5.2 officially requires Python 3.8+
  - Python 3.10 enables modern syntax (e.g., `int | None` union types)
  - Python 3.10+ represents production-ready baseline with modern features
  - Databricks Runtime 16.4 LTS supports 3.10+
  - Code already uses Python 3.10 syntax

### Databricks Runtime
- **Recommended**: Databricks Runtime 16.4 LTS
- **Spark Version**: 3.5.2
- **Support Until**: May 9, 2028 (long-term support)
- **Why 16.4 LTS**:
  - Current stable release (May 2025)
  - Spark 3.5.2 is modern and proven
  - Long-term support ensures stability during development and beyond
  - Free Edition likely supports this version

### Environment Compatibility
```
Databricks Runtime 16.4 LTS
  ↓
  Apache Spark 3.5.2
  ↓
  Python 3.10+ (supports modern syntax, includes union types)
  ↓
  PySpark, Pandas, Pydantic, PyYAML (all compatible)
```

---

## Dependencies (Poetry)

### pyproject.toml

```toml
[tool.poetry]
name = "skullport-generator"
version = "0.1.0"
description = "Synthetic data generator for Delivery Performance Mart"
authors = ["Your Name <you@example.com>"]

[tool.poetry.dependencies]
python = "^3.10"
pyspark = "^3.3"
pandas = "^1.5"
pydantic = "^2.0"
pyyaml = "^6.0"

[tool.poetry.dev-dependencies]
pytest = "^7.0"

[build-system]
requires = ["poetry-core"]
build-backend = "poetry.core.masonry.api"
```

### .gitignore

```
# Virtual environment
.venv/

# Python compiled files
__pycache__/
*.pyc

# Testing cache
.pytest_cache/

# Local environment variables
.env
```

**Workflow**:
```bash
poetry install      # Creates .venv/, installs deps, creates poetry.lock
poetry shell        # Activate virtual environment
poetry add <pkg>    # Add new dependency
poetry lock         # Update poetry.lock
```

**Commit to git**:
- ✅ `pyproject.toml` (dependency declaration)
- ✅ `poetry.lock` (exact versions)
- ❌ `.venv/` (ignore — generated locally)

---

## Module Breakdown & Dependencies

### Module 1: Configuration (`src/skullport_generator/config.py`)
**Purpose**: Load YAML config and return as a dictionary

**Inputs**: YAML file (e.g., `config.yaml`)
**Outputs**: Configuration dict
**Dependencies**: `PyYAML`

**Key Responsibilities**:
- Parse YAML into Python dict
- Raise errors for missing or empty files
- Return config dict for downstream modules

**Note**: Pydantic validation (type checking, proportion bounds, enum validation) is oversized for MVP. Keep as a **future nice-to-have** when config complexity warrants it.

**Example usage**:
```python
from skullport_generator.config import load_config

config = load_config("config.yaml")
# Returns: dict with num_labels, random_seed, carrier_distribution, etc.
num_labels = config["num_labels"]
random_seed = config["random_seed"]
```

---

### Module 2: Schemas (`src/skullport_generator/schemas.py`)
**Purpose**: Define PySpark StructTypes for both Delta tables (schema as code)

**Inputs**: None (static definitions)
**Outputs**: Two PySpark StructType objects
**Dependencies**: `pyspark.sql.types`

**What to Define**:
- `RAW_LABELS_SCHEMA` — StructType with 12 columns (label_id, customer_id, carrier, etc.)
- `RAW_TRACKING_EVENTS_SCHEMA` — StructType with 8 columns (event_id, label_id, event_code, etc.)

**Validation Function**:
- `validate_schemas()` — Check that schemas match spec exactly (column names, types, nullability)

**Example**:
```python
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, TimestampType

RAW_LABELS_SCHEMA = StructType([
    StructField("label_id", StringType(), False),
    StructField("customer_id", StringType(), False),
    StructField("carrier", StringType(), False),
    # ... etc
])
```

---

### Module 3: Labels Generator (`src/skullport_generator/labels_generator.py`)
**Purpose**: Generate synthetic `raw.labels` data with CDC structure, changes, voiding, fraud, etc.

**Inputs**: `GeneratorConfig`, random seed
**Outputs**: Pandas DataFrame with all labels (later converted to PySpark for writing)

**Key Logic**:
1. **Generate base labels** (algorithm):
   - Create list of `num_labels` dictionaries, one per label ID
   - For each label:
     1. Generate unique `label_id` (lbl_<24 hex>) and `customer_id` (cust_<12 hex>)
     2. Sample carrier from `carrier_distribution` (e.g., 50% USPS, 30% UPS)
     3. Sample service class based on carrier:
        - Generate random 0-1; if < 10%, pick express; else pick standard
        - Map to carrier-specific class (USPS_PRIORITY/STANDARD, UPS_2ND_DAY/GROUND, etc.)
     4. Generate origin/dest ZIPs: `str(random.randint(1, 99999)).zfill(5)`
     5. Generate weight: `random.randint(1, 1180)` (weight fraud happens later in step 4)
     6. Generate insurance: if random < 15%, generate value $50-$500; else NULL
     7. Generate `label_created_at` as random timestamp within `date_range_days`
     8. Calculate `carrier_promised_delivery_at` by adding service SLA to created_at
     9. Set `voided_at` = NULL, `last_updated_at` = `label_created_at`
   - Result: DataFrame with 1 row per label (base state)

2. **Apply CDC changes** (reach 30% changed labels):
   - Algorithm:
     1. Identify labels for changes: sample 30% of label IDs randomly
     2. For each sampled label, append new rows (one per change):
        a. **Decide voiding**: random 0-1; if < 0.30, mark for voiding; else not voided
        b. **If voided**:
           - Decide timing: if random < 0.90, void within 1 hour; else void 2-5 days later
           - Generate 1 voiding row with `voided_at` set, `last_updated_at` updated accordingly
           - **Stop here** (no further updates for this label)
        c. **If not voided**:
           - Generate 1-2 intermediate change rows (pick 1-2 fields to change: carrier, service_class)
           - Each change gets a new `last_updated_at` (strictly later than previous)
   - Result: DataFrame with multiple rows per changed label (CDC-style, chronologically ordered)

3. **Apply data quality issues**:
   - **Weight fraud** (~5%): For rows with weight > 1120, set weight = random(1000, 1120)
   - **Insurance edge case** (5% of insured): For 5% of insured labels, set declared_value_cents = 0

**Data Structure**:
- Pandas DataFrame
- Columns: [label_id, customer_id, carrier, service_class, origin_zip, dest_zip, weight_oz, declared_value_cents, label_created_at, carrier_promised_delivery_at, voided_at, last_updated_at]

**Helper Functions** (spec-driven):
- `generate_label_id()` → `lbl_<24 hex>` (spec: label_id format)
- `generate_customer_id()` → `cust_<12 hex>` (spec: customer_id format)
- `select_carrier(distribution)` → carrier based on proportions
- `select_service_class(carrier)` → service class for that carrier
- `calculate_promised_delivery_date(created, service_class)` → promised date
- `apply_cdc_changes(labels, config, seed)` → add CDC change rows
- `apply_weight_fraud(labels, config, seed)` → adjust weights
- `apply_insurance_edge_cases(labels, config, seed)` → zero out insured value for some labels

---

### Module 4: Events Generator (`src/skullport_generator/events_generator.py`)
**Purpose**: Generate synthetic `raw.tracking_events` data with duplicates, late arrivals, malformed timestamps, schema drift, timezone weirdness, etc.

**Inputs**: `GeneratorConfig`, labels Pandas DataFrame, random seed
**Outputs**: Pandas DataFrame with all events (later converted to PySpark for writing)

**Key Logic**:
1. **Generate base event sequences** (algorithm):
   - Create list to accumulate event rows
   - For each label in labels DataFrame:
     1. **Decide event sequence**: Check label's `voided_at` status and incompleteness:
        - If voided within 1 hour: 0 events (carrier never scanned, stop)
        - If voided 2-5 days later: random(0-3) events (some get scans before void, then stop)
        - If not voided:
          - For 1% of non-voided labels: truncate sequence at in_transit (2 events: picked_up, in_transit; never deliver)
          - For 99% of non-voided labels: full 4-event sequence (picked_up → in_transit → out_for_delivery → delivered)
     2. For each event in the sequence [picked_up, in_transit, out_for_delivery, delivered]:
        a. Generate `event_id` (UUID-style string, e.g., `uuid.uuid4().hex`)
        b. Generate `event_at`: timestamp based on spec-driven SLA proportions:
           - SLA = carrier_promised_delivery_at - label_created_at (in days)
           - picked_up: label_created_at + (15% of SLA)
           - in_transit: label_created_at + (40% of SLA)
           - out_for_delivery: label_created_at + (75% of SLA)
           - delivered: label_created_at + (95% of SLA)
           - **Late delivery check** (3% of labels, per `late_delivery_proportion` config):
             - If this label marked for late delivery: delivered = label_created_at + SLA + random(1-3 days)
             - Else: use timestamp calculated above (on-time)
        c. Generate `event_received_at`: same as event_at (normal case; late arrivals applied later)
        d. Populate `event_code` OR `event_type` based on carrier (spec-driven mapping)
           - USPS uses event_code; others use event_type
           - Map sequence position to carrier-specific code/type
        e. Apply carrier-specific timezone formatting to `event_at`:
           - USPS: add offset (e.g., `-05:00`)
           - UPS: add `Z`
           - FEDEX: plain ISO 8601
           - DHL: add timezone abbreviation (e.g., ` EST`)
        f. Set `location_zip`: random ZIP or NULL (per carrier habit)
        g. Set `raw_payload`: NULL or minimal JSON string
        h. Append row to events list
   - Result: DataFrame with all normal events

2. **Apply out-of-order rows** (20-30% of labels with 2+ events):
   - Algorithm:
     1. Filter to labels with 2+ events (multi-event shipments)
     2. For each: random 0-1; if < 0.25, mark for shuffling
     3. For marked labels: randomly shuffle all event rows
        - Example: [picked_up, in_transit, out_for_delivery, delivered]
        - After shuffle: [out_for_delivery, picked_up, delivered, in_transit]
     4. Keep row order as-is after shuffling (don't re-sort)
   - Result: Events out of chronological sequence (but timestamps unchanged)

3. **Apply data quality issues** (sequential corruption):
   - Algorithm:
     1. **Duplicates** (3-5% of rows): For random 3-5% of events, append exact duplicate with new event_id
     2. **Late arrivals** (5-10% of rows): For random 5-10%, set `event_received_at` = `event_at` + random(2-8 days)
     3. **Malformed timestamps** (1% of rows): For random 1%, corrupt `event_at`:
        - Pick corruption type randomly: no separators / missing time / wrong separators
        - Apply malformation (e.g., remove dashes, remove time portion, replace `-` with `/`)
     4. **Missing fields** (1% of rows): For random 1%, set both event_code and event_type to NULL
     5. **Timezone weirdness** (2-5% of rows): For random 2-5%, apply different timezone format than expected
     6. **Voided label tracking** (5% of voided labels): For 5% of voided labels, append 1-2 events anyway (late carrier scan)
   - Result: DataFrame with realistic data quality issues
   - Note: Incomplete sequences decided upfront in step 1, not applied here

**Data Structure**:
- Pandas DataFrame
- Columns: [event_id, label_id, carrier, event_code, event_type, event_at, event_received_at, location_zip, raw_payload]

**Helper Functions** (spec-driven):
- `generate_event_id()` → UUID-style string (spec: event_id format, "usually unique but NOT guaranteed")
- `decide_event_sequence(label, config, seed)` → determine event count and type (full 4, incomplete 2, or voided 0-3)
- `generate_event_sequence(label, config, seed)` → list of 0-4 events based on decision
- `format_event_at(timestamp, carrier, config)` → ISO 8601 STRING with carrier-specific timezone
- `apply_out_of_order_rows(events, config, seed)` → shuffle intermediate event rows per label
- `apply_duplicates(events, config, seed)` → add duplicate events
- `apply_late_arrivals(events, config, seed)` → adjust received_at
- `apply_malformed_timestamps(events, config, seed)` → corrupt event_at
- `apply_schema_drift(events, config)` → populate code OR type per carrier
- `apply_timezone_weirdness(events, config, seed)` → inconsistent formatting
- `apply_voided_label_tracking(events, labels, config, seed)` → add events to voided labels

---

### Module 5: Writer (`src/skullport_generator/writer.py`)
**Purpose**: Write DataFrames to Delta tables in Databricks Unity Catalog

**Inputs**: Two Pandas/PySpark DataFrames, `GeneratorConfig`
**Outputs**: Two Delta tables in Unity Catalog

**Key Responsibilities**:
- Connect to Databricks (assumes running IN Databricks or Databricks Connect)
- CREATE catalog if not exists
- CREATE schema if not exists
- DROP existing tables (idempotent re-runnability)
- CREATE tables with correct schemas
- Write data to tables
- Validate tables were created correctly (row counts, schema)

**Implementation Strategy**:
- Use PySpark to read/write (native Databricks support)
- Use SQL for DDL (CREATE CATALOG, CREATE SCHEMA, DROP TABLE)
- Validate on write success

**Example Code**:
```python
def write_to_delta(labels_df, events_df, config: GeneratorConfig, spark):
    catalog = config.catalog_name
    schema = config.schema_name
    
    # Create catalog and schema
    spark.sql(f"CREATE CATALOG IF NOT EXISTS {catalog}")
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {catalog}.{schema}")
    
    # Drop and recreate tables
    spark.sql(f"DROP TABLE IF EXISTS {catalog}.{schema}.labels")
    spark.sql(f"DROP TABLE IF EXISTS {catalog}.{schema}.tracking_events")
    
    # Write tables
    labels_df.write.format("delta") \
        .mode("overwrite") \
        .option("mergeSchema", "false") \
        .saveAsTable(f"{catalog}.{schema}.labels")
    
    events_df.write.format("delta") \
        .mode("overwrite") \
        .saveAsTable(f"{catalog}.{schema}.tracking_events")
    
    # Validate
    labels_count = spark.sql(f"SELECT COUNT(*) FROM {catalog}.{schema}.labels").collect()[0][0]
    events_count = spark.sql(f"SELECT COUNT(*) FROM {catalog}.{schema}.tracking_events").collect()[0][0]
    
    return {
        "labels_count": labels_count,
        "events_count": events_count
    }
```

---

### Module 6: Main Entrypoint (`src/skullport_generator/main.py`)
**Purpose**: Orchestrate the generator: load config, generate data, write to Delta

**Inputs**: Config file path (e.g., `config.yaml`)
**Outputs**: Two Delta tables in Databricks

**Orchestration Flow**:
```
1. Load config (config.py)
2. Validate schemas exist (schemas.py)
3. Initialize RNG with seed: random.seed(config.random_seed)
   - Must be done BEFORE generating labels/events (spec-driven)
   - Ensures reproducibility: same seed → same data
4. Generate labels (labels_generator.py)
   - Receives config.random_seed, uses seeded random for all generation
5. Generate events (events_generator.py)
   - Receives config.random_seed, uses seeded random for all generation
6. Convert to PySpark DataFrames
7. Write to Delta (writer.py)
8. Log results & validation counts
```

**Example**:
```python
def main(config_path: str):
    # Load config
    config = load_config(config_path)
    
    # Get Spark session
    spark = SparkSession.builder.appName("skullport-generator").getOrCreate()
    
    # Validate schemas
    validate_schemas()
    
    # Generate data
    print(f"Generating {config.num_labels} labels...")
    labels = generate_labels(config)
    
    print(f"Generating tracking events...")
    events = generate_events(config, labels)
    
    # Convert to PySpark
    labels_df = spark.createDataFrame(labels, schema=RAW_LABELS_SCHEMA)
    events_df = spark.createDataFrame(events, schema=RAW_TRACKING_EVENTS_SCHEMA)
    
    # Write
    print(f"Writing to {config.catalog_name}.{config.schema_name}...")
    results = write_to_delta(labels_df, events_df, config, spark)
    
    print(f"Done! Generated {results['labels_count']} labels and {results['events_count']} events")

if __name__ == "__main__":
    import sys
    config_path = sys.argv[1] if len(sys.argv) > 1 else "config.yaml"
    main(config_path)
```

---

### Module 7: Databricks Notebook Wrapper (`notebooks/run_generator.py`)
**Purpose**: Run generator from Databricks notebook

**Implementation**:
```python
# Notebook: notebooks/run_generator.py
%pip install -e /Workspace/Repos/your-username/skullport-generator

from skullport_generator.main import main

# Run generator
main("config.yaml")
```

---

## Implementation Sequence

### Phase 1: Foundation
1. **Module 2: Schemas**
   - Define StructTypes for both tables
   - Write validation function
   - Test: assert schemas are correct

2. **Module 1: Configuration**
   - Create Pydantic models
   - Implement YAML loader
   - Test: load example config, validate, catch errors

**Milestone**: Can parse config and validate it ✓

---

### Phase 2: Data Generation
3. **Module 3: Labels Generator**
   - Start simple: generate base labels (no changes, no voiding)
   - Test: 100 labels, check columns, types
   - Add CDC changes logic
   - Test: verify 30% have multiple rows
   - Add voiding logic
   - Test: verify voiding rows created correctly
   - Add weight fraud, insurance edge cases
   - Test: verify proportions

4. **Module 4: Events Generator**
   - Start simple: generate 4-event sequences for delivered labels
   - Test: each label has correct events
   - Add voiding/incompleteness logic
   - Test: voided labels have 0 events, incomplete have 2 (in_transit)
   - Add out-of-order row shuffling
   - Test: verify 20-30% of multi-event labels have shuffled rows
   - Add duplicates
   - Test: verify 3-5% are duplicates
   - Add late arrivals
   - Test: verify event_received_at > event_at for some
   - Add malformed timestamps
   - Test: verify corrupt timestamps exist
   - Add schema drift
   - Test: verify event_code/event_type per carrier
   - Add timezone weirdness
   - Test: verify format per carrier

**Milestone**: Can generate realistic labels and events ✓

---

### Phase 3: Integration
5. **Module 5: Writer**
   - Implement CREATE catalog/schema
   - Implement DROP tables
   - Implement write to Delta
   - Test in Databricks: write 100 labels, 400 events, verify tables exist
   - Test idempotency: run twice, verify data not duplicated

6. **Module 6: Main**
   - Wire up all modules
   - Test end-to-end: config → labels → events → Delta

7. **Module 7: Notebook**
   - Create notebook wrapper
   - Test in Databricks

**Milestone**: Full end-to-end generator working ✓

---

### Phase 4: Testing & Validation
8. **Tests** (`tests/`)
   - `test_schemas.py`: Validate generated data matches schemas
   - `test_data_quality.py`: Spot-check proportions (voided %, duplicates %, etc.)

**Milestone**: Tests passing ✓

---

## Testing Strategy

### Unit Tests (`tests/test_data_quality.py`)
- Validate data proportions match config
- Example: `num_voided = count(voided_at is not null) / num_labels`
  - Assert: `num_voided ≈ changed_labels * changed_voided_proportion`
- Example: duplicate events proportion
  - Assert: `duplicates / total_events ≈ event_duplicates_proportion`

### Integration Tests
- End-to-end: config → Delta tables in Databricks
- Verify row counts
- Verify schemas match spec

### Manual Testing
- Run with 1000 labels, inspect results
- Increase to 10K, verify volumes reasonable
- Spot-check data: read 10 labels, verify changes/voiding logic
- Verify timestamps sensible (no future dates, voided_at > created_at)

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| **Weight fraud logic bug** | Medium | Medium | Unit test: verify ~5% exceed 1120, all adjusted to 1000-1120 |
| **Event-to-label ratio wrong** | Medium | Low | Monitor actual avg events per label; adjust params if needed |
| **Out-of-order event row shuffling bug** | Medium | Medium | Test: manually verify shuffled events still have correct timestamps |
| **Databricks connection fails** | Low | High | Test in Databricks early (Module 5); clear error messages |
| **PySpark schema mismatch** | Low | High | Validate schemas in Module 2; catch mismatches on write |
| **Performance: slow data generation** | Low | Medium | Start with small volumes (1000 labels); profile if slow |
| **Timezone formatting bugs** | Medium | Low | Test each carrier format; spot-check output |
| **Seed reproducibility fails** | Low | High | Test: same config + seed → same data twice |

---

## Key Decisions

1. **Pandas for generation, PySpark for writing** (not PySpark throughout)
   - Rationale: Pandas easier for complex logic; PySpark native to Databricks for writing
   - Risk: Convert between formats; mitigate with clear types

2. **DROP and recreate tables** (not MERGE)
   - Rationale: Simpler logic; idempotent; test data doesn't need upsertion
   - Downside: Loses history; acceptable for test data

3. **YAML config** (not Python class or CLI args)
   - Rationale: Flexible, human-readable, reproducible across teams
   - Downside: Need YAML parser; mitigate with Pydantic validation

4. **Pydantic for validation** (not manual checks)
   - Rationale: Strong typing, clear errors, reusable
   - Downside: Requires Pydantic dependency; acceptable for production-grade

5. **One `num_labels` parameter, no `num_events`**
   - Rationale: Events derive from label characteristics (voiding, incompleteness)
   - Benefit: Natural, realistic event counts; no impossible configs

---

## Next Steps (After Implementation)

1. **Run test generator**: 1000 labels → verify event count reasonable
2. **Increase volumes**: 10K labels, measure runtime
3. **Adjust parameters**: Tune proportions for desired data distribution
4. **Document**: Add README with setup, usage, config examples
5. **CI/CD**: Add GitHub Actions to validate on every commit
