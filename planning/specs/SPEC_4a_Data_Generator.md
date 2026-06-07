# Specification: 4a. Synthetic Data Generator

## Overview

Build a production-grade Python project that generates synthetic data for the Delivery Performance Mart case study. The generator creates two Delta tables (`raw.labels` and `raw.tracking_events`) with realistic, messy data that exercises the Bronze → Silver → Gold pipeline.

**Target**: Databricks Free Edition with Unity Catalog
**Output**: Two Delta tables representing raw data from Skullport Logistics backend systems

---

## Table 1: `raw.labels`

### Schema

| Column | Type | Nullable | Description |
|---|---|---|---|
| `label_id` | STRING | no | Shipping label ID, format: `lbl_<24 hex chars>` |
| `customer_id` | STRING | no | Customer ID, format: `cust_<12 hex chars>` |
| `carrier` | STRING | no | Carrier: USPS, UPS, FEDEX, or DHL_ECOM |
| `service_class` | STRING | no | Carrier-specific service (e.g., USPS_PRIORITY, UPS_GROUND) |
| `origin_zip` | STRING | no | 5-digit US origin ZIP code |
| `dest_zip` | STRING | no | 5-digit US destination ZIP code |
| `weight_oz` | INT | no | Weight in ounces (1 to 1180 oz; 1-33 kg) |
| `declared_value_cents` | INT | yes | Insurance value in cents ($0-$500), or NULL if uninsured |
| `label_created_at` | TIMESTAMP | no | Label creation timestamp (UTC) |
| `carrier_promised_delivery_at` | TIMESTAMP | no | Carrier's promised delivery date (UTC) |
| `voided_at` | TIMESTAMP | yes | Voiding timestamp (NULL if active; set if cancelled) |
| `last_updated_at` | TIMESTAMP | no | CDC update timestamp (UTC; orders label history) |

### Normal Case Generation

**CDC Structure** (Change Data Capture):
- 70% of labels: No changes (1 row per label)
- 30% of labels: Get at least one change (multiple rows per label)
  - Each change creates a new row with the same `label_id` but newer `last_updated_at`
  - Example: label created → carrier changed → voided = 3 rows in order of `last_updated_at`

**Carrier Mix**:
- USPS: 50%
- UPS: 30%
- FEDEX: 15%
- DHL_ECOM: 5%

**Service Classes** (per carrier):
- USPS: 90% USPS_STANDARD, 10% USPS_PRIORITY
- UPS: 90% UPS_GROUND, 10% UPS_2ND_DAY
- FEDEX: 90% FEDEX_NORMAL, 10% FEDEX_2_DAY
- DHL_ECOM: 90% DHL_ECOM_FLEX, 10% DHL_ECOM_EXPRESS

**Promised Delivery Calculation**:
- `carrier_promised_delivery_at` = `label_created_at` + max SLA for service class
- USPS_PRIORITY: +3 days
- USPS_STANDARD: +5 days
- UPS_2ND_DAY: +2 days
- UPS_GROUND: +7 days
- FEDEX_2_DAY: +2 days
- FEDEX_NORMAL: +7 days
- DHL_ECOM_EXPRESS: +3 days
- DHL_ECOM_FLEX: +5 days

**Insurance** (Business Data):
- 15% of labels have declared_value_cents > 0
- 85% have declared_value_cents = NULL (no insurance)
- Of insured labels, values range from $50 to $500

**ZIP Codes**:
- Valid 5-digit US ZIP codes for origin and destination

### Edge Cases & Data Quality Issues

| Issue | Pattern | Proportion |
|---|---|---|
| **Weight fraud** | Random weight generated 1-1180 oz; if > 1120 oz (system limit), adjusted to random 1000-1120 oz to evade detection | ~5% of labels report fraudulent weight |
| **Voided - immediate** | Label voided within minutes/hours of creation (customer regret) | 90% of voided labels |
| **Voided - fraud** | Label voided 2-5 days after creation (after shipping, to avoid payment) | 10% of voided labels |
| **Insurance edge case** | Insured label has declared_value_cents = 0 (inconsistent) | 5% of insured labels |

### Configuration Parameters

| Parameter | Description | Example |
|---|---|---|
| `num_labels` | Total labels to generate | 5000, 10000, 50000 |
| `changed_labels_proportion` | Fraction of labels that get ≥1 update | 0.30 (30%) |
| `changed_voided_proportion` | Of changed labels, fraction that result in void | 0.30 (30% of changed) |
| `voided_fraud_proportion` | Of voided labels, fraction with 2-5 day lifecycle | 0.10 (10% of voided) |
| `service_class_express_proportion` | Fraction using express service (vs ground/standard) | 0.10 (10%) |
| `insurance_proportion` | Fraction with declared_value_cents > 0 | 0.15 (15%) |
| `insurance_0_value_proportion` | Of insured, fraction with value = 0 | 0.05 (5% of insured) |
| `carrier_distribution` | Proportion of each carrier | {USPS: 0.50, UPS: 0.30, FEDEX: 0.15, DHL_ECOM: 0.05} |
| `date_range_days` | Days back to generate creation dates | 30, 90 |
| `catalog_name` | Unity Catalog target | "pirate_ship_demo" |
| `schema_name` | Schema name within catalog | "raw" |
| `random_seed` | Seed for reproducibility (required) | 42 |

---

## Table 2: `raw.tracking_events`

### Schema

| Column | Type | Nullable | Description |
|---|---|---|---|
| `event_id` | STRING | no | Event ID, UUID-style (usually unique but NOT guaranteed) |
| `label_id` | STRING | no | Label ID; joins to `raw.labels.label_id` |
| `carrier` | STRING | no | Carrier: USPS, UPS, FEDEX, or DHL_ECOM |
| `event_code` | STRING | yes | Carrier event code (NULL if carrier uses event_type) |
| `event_type` | STRING | yes | Carrier event type (NULL if carrier uses event_code) |
| `event_at` | STRING | no | ISO 8601 timestamp of the event (STRING, format varies by carrier) |
| `event_received_at` | TIMESTAMP | no | When our system received the scan (UTC, TIMESTAMP) |
| `location_zip` | STRING | yes | ZIP code of scan location (some carriers omit) |
| `raw_payload` | STRING | yes | Stringified JSON of original carrier payload |

### Normal Case Generation

**Event Sequence**:
- All labels follow the same 4-event sequence: `picked_up` → `in_transit` → `out_for_delivery` → `delivered`
- Delivered labels: 4 events
- Incomplete labels: 1-3 events (stuck before `delivered`)
- Voided labels: 0-3 events depending on when voided

**Event Timing** (proportional to SLA):
- SLA = `carrier_promised_delivery_at` - `label_created_at` (in days)
- Event timestamps are distributed across the SLA window:
  - `picked_up`: label_created_at + 15% of SLA ± small randomness (hours)
  - `in_transit`: label_created_at + 40% of SLA ± small randomness
  - `out_for_delivery`: label_created_at + 75% of SLA ± small randomness
  - `delivered`: label_created_at + 95% of SLA ± small randomness
- **Late delivery** (3% of shipments): delivered timestamp exceeds promised_delivery_at by 1-3 days
- **On-time delivery** (97% of shipments): delivered timestamp ≤ promised_delivery_at

**Events per Label**:
- Average: 3.5-4.5 events per label (accounting for incomplete/voided labels)
- Timing: Events space out realistically across the SLA window (2-7 days per service class)

**Voided Label Behavior**:
- Immediately voided (customer cancels quickly): 0 tracking events (carrier never scanned)
- Late-voided (2-5 days, potential fraud): 50% have 1-3 events before voiding, 50% have 0 events

**Timezone Handling**:
- USPS: ISO 8601 with offset (e.g., `2026-06-06T10:30:00-05:00`)
- UPS: ISO 8601 with Z (e.g., `2026-06-06T10:30:00Z`)
- FEDEX: ISO 8601 without timezone (e.g., `2026-06-06T10:30:00`)
- DHL_ECOM: ISO 8601 with US timezone abbreviation (e.g., `2026-06-06T10:30:00 EST`)

**Schema Drift**:
- USPS: populates `event_code`, `event_type` is NULL
- UPS: populates `event_type`, `event_code` is NULL
- FEDEX: populates `event_type`, `event_code` is NULL
- DHL_ECOM: populates `event_code`, `event_type` is NULL

**Event Code/Type Values** (represents the 4-event sequence):
- USPS (uses `event_code`): "0300" (picked_up), "0301" (in_transit), "0310" (out_for_delivery), "0320" (delivered)
- UPS (uses `event_type`): "PICKUP", "IN_TRANSIT", "OUT_FOR_DELIVERY", "DELIVERED"
- FEDEX (uses `event_type`): "PICKUP", "IN_TRANSIT", "OUT_FOR_DELIVERY", "DELIVERED"
- DHL_ECOM (uses `event_code`): "PU", "IT", "OFD", "DL"

### Edge Cases & Data Quality Issues

| Issue | Pattern | Proportion |
|---|---|---|
| **Duplicate events** | Same logical scan (same label_id, event field, event_at) with different event_id | 3-5% of events |
| **Late-arriving events** | event_at is far before event_received_at (e.g., scan June 5, received June 8) | 5-10% of events |
| **Out-of-order rows** | Events for a label arrive out of chronological sequence (all events shuffled randomly). Timestamps remain unchanged | 20-30% of labels with 2+ events are shuffled |
| **Missing fields** | Both event_code and event_type are NULL | 1% of events |
| **Unparseable timestamp** | event_at in invalid ISO 8601 format (no separators / missing time / wrong separators) | 1% of events |
| **Missing required fields** | event_id or label_id is missing | <0.5% of events |
| **Voided label tracking** | Voided label still receives tracking events (late carrier scan) | 5% of voided labels |
| **Incomplete sequence** | Label never reaches "delivered" status (stuck in transit) | 1% of labels |

**Malformed Timestamp Examples** (1% of events):
- No separators: `20260606T103000` (from valid `2026-06-06T10:30:00`)
- Missing time: `2026-06-06` (from valid `2026-06-06T10:30:00`)
- Wrong separators: `2026/06/06T10:30:00` (from valid `2026-06-06T10:30:00`)

### Configuration Parameters

| Parameter | Description | Example |
|---|---|---|
| `num_events` | Total tracking events to generate | 50000, 100000, 300000 |
| `avg_events_per_label` | Average events per label (accounting for incomplete/voided) | 3.5, 4, 4.5 |
| `late_delivery_proportion` | Fraction of shipments delivered after promised_delivery_at | 0.03 (3%) |
| `event_duplicates_proportion` | Fraction of exact duplicate events | 0.03-0.05 (3-5%) |
| `event_late_arrivals_proportion` | Fraction of events where event_at << event_received_at | 0.05-0.10 (5-10%) |
| `event_out_of_order_proportion` | Of labels with 2+ events, fraction with out-of-order row(s) | 0.20-0.30 (20-30%) |
| `event_malformed_proportion` | Fraction of malformed rows (missing/unparseable fields) | 0.01-0.02 (1-2%) |
| `event_schema_drift_by_carrier` | Field used per carrier (code / type) | {USPS: "code", UPS: "type", FEDEX: "type", DHL_ECOM: "code"} |
| `event_timezone_format_by_carrier` | Timestamp format per carrier | {USPS: "offset", UPS: "utc_z", FEDEX: "utc_plain", DHL_ECOM: "tz_abbr"} |
| `timezone_weirdness_proportion` | Fraction with inconsistent timezone formatting | 0.02-0.05 (2-5%) |
| `voided_label_tracking_proportion` | Fraction of voided labels that still get events | 0.05 (5% of voided labels) |
| `late_voided_events_proportion` | Of late-voided labels, fraction that have events before voiding | 0.50 (50%) |
| `incomplete_labels_proportion` | Fraction of labels with incomplete sequences (never delivered) | 0.01 (1%) |
| `event_sequence_pattern` | Standard 4-event sequence all carriers use | ["picked_up", "in_transit", "out_for_delivery", "delivered"] |
| `date_range_days` | Days back to generate event timestamps | 30, 90 |
| `random_seed` | Seed for reproducibility (required) | 42 |

---

## Generator Requirements

The generator must be a **production-grade Python project**:

1. **Project Layout**: Clear module boundaries, not everything-in-one-file
2. **Reproducible Environment**: Single command to install dependencies; all versions locked
3. **Type Hints**: All functions have input and return type annotations
4. **Re-runnability**: Running twice in a row does not corrupt tables (DROP and recreate, or MERGE)
5. **Honest Configuration**: Volumes, proportions, and catalog name configurable (not hardcoded)
6. **Error Handling**: Validate config at startup; handle Databricks failures gracefully; log progress

See `implementation-plan/IMPLEMENTATION_PLAN_4a.md` for implementation details.

---

## Reproducibility

The generator must produce **deterministic, reproducible output** controlled by a single seed:

1. **Seed initialization** (at startup):
   - Load `random_seed` from config
   - Call `random.seed(random_seed)` (Python's built-in `random` module)

2. **Deterministic generation**:
   - All randomness (label IDs, carriers, weights, event timings, quality issues, etc.) is controlled by the seed
   - All `random.randint()`, `random.choice()`, `random.uniform()` calls are deterministic

3. **Reproducibility guarantee**:
   - Run 1: `random_seed=42` → generates labels and events (set A)
   - Run 2: `random_seed=42` → generates identical labels and events (set A)
   - Run 3: `random_seed=99` → generates different labels and events (set B)
   - Expected use: Tests and documentation run with a fixed seed (e.g., 42) to produce consistent datasets

4. **Implementation**:
   - Module 1 (Config): Load and validate `random_seed`
   - Module 3 (Labels Generator): Receive seed, call `random.seed(seed)` before generating any labels
   - Module 4 (Events Generator): Receive seed, call `random.seed(seed)` before generating any events
   - Note: Seeding is done per-module to ensure clear boundaries

---

## Output & Storage

The generator writes two Delta tables to Unity Catalog in Databricks Free Edition:
- **Format**: Delta tables (Databricks native format with ACID guarantees)
- **Location**: Unity Catalog (`catalog.schema.table`)
- **Storage**: Databricks Free Edition provides managed storage automatically — no infrastructure setup needed
- **Configuration**: Catalog and schema names are configurable

Implementation uses PySpark to write DataFrames to Delta tables. Databricks handles storage provisioning transparently.

---

## Success Criteria

✅ Two Delta tables created with exact schemas  
✅ Data quantity and proportions match configuration  
✅ Generator runs end-to-end in Databricks Free Edition  
✅ Generator is re-runnable without data corruption  
✅ Code is well-structured, typed, and documented  
✅ Configuration is externalized (not hardcoded)  
✅ Error handling is graceful and informative  

---

## Known Constraints & Decisions

- **Volume Target**: 10K-50K labels + 50K-300K events (exercises pipeline without overwhelming Free Edition)
- **Timestamp Format**: `event_at` kept as STRING to preserve raw carrier inconsistency (realistic for Bronze layer)
- **Soft Deletes**: Voided labels marked with `voided_at` (not hard-deleted) to preserve history
- **Deduplication**: Exact duplicate events exist in raw.tracking_events; Silver layer deduplicates
- **Carrier Data**: Realistic carrier codes and SLAs; intentionally not perfect to test data quality

---

## Next Steps

After generator implementation:
1. Build Bronze layer: idempotent ingestion of raw.labels and raw.tracking_events
2. Build Silver layer: cleanse, deduplicate, conform schemas
3. Build Gold layer: delivery performance mart for Analytics team
