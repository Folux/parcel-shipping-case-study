# Gold Layer Specification (4b.3)

## Overview

Transform clean Silver data into an analytics-ready operational mart that answers business questions about delivery performance. The mart provides one row per label with delivery metrics and dimensions optimized for BI/analytics consumption.

**Purpose**: Enable answering: "What % of shipments delivered on-time? Which carriers/regions have the best performance?"

**Phase 1 MVP**: Single mart table with one metric (`is_delivered_on_time`) + supporting dimensions and facts. Additional analytical marts and aggregations deferred to Phase 2 (dbt) once this foundation is solid.

---

## Gold Mart: `skullport.gold.delivery_performance`

**Grain**: One row per label (shipment)

**Purpose**: Operational mart for delivery performance analysis by shipment

### Columns (12 total)

| Column | Type | Nullable | Source | Notes |
|--------|------|----------|--------|-------|
| `label_id` | STRING | NO | `silver.labels` | Primary key |
| `customer_id` | STRING | NO | `silver.labels` | Dimension: customer |
| `carrier` | STRING | NO | `silver.labels` | Dimension: USPS, UPS, FEDEX, DHL_ECOM |
| `service_class` | STRING | NO | `silver.labels` | Dimension: Express, Ground, etc. |
| `origin_zip` | STRING | YES | `silver.labels` | Dimension: origin region |
| `dest_zip` | STRING | YES | `silver.labels` | Dimension: destination region |
| `label_created_at` | TIMESTAMP | NO | `silver.labels` | Fact: when label was created |
| `carrier_promised_delivery_at` | TIMESTAMP | NO | `silver.labels` | Fact: promised delivery date per SLA |
| `actual_delivery_at` | TIMESTAMP | YES | `silver.tracking_events` | Fact: when "delivered" event occurred (latest) |
| `is_delivered` | BOOLEAN | NO | Derived | Flag: has a delivery event? |
| `is_delivered_on_time` | BOOLEAN | NO | Derived | **Metric**: delivered on or before promised date? |
| `inserted_at` | TIMESTAMP | NO | Derived | Metadata: when row was generated |

### Transformations

1. **Join Silver tables**:
   - LEFT JOIN `silver.tracking_events` on `silver.labels.label_id`
   - Find "delivered" event per label (latest by `event_at` where `event_name` = "delivered")

2. **Calculate delivery metrics**:
   - `is_delivered`: BOOLEAN flag — TRUE if any delivery event exists
   - `actual_delivery_at`: TIMESTAMP — the `event_at` of the latest "delivered" event (NULL if not delivered)
   - `is_delivered_on_time`: BOOLEAN — TRUE if `actual_delivery_at <= carrier_promised_delivery_at`; FALSE otherwise

3. **One row per label**:
   - Collapse delivery events to one per label in a CTE using `ROW_NUMBER() OVER (PARTITION BY label_id ORDER BY event_at DESC)` (keep `rn = 1`), then LEFT JOIN that to `silver.labels`
   - **No `DISTINCT`** — duplication is prevented at the source by deduping the delivery events, not masked after a fan-out join
   - Preserve all dimension columns from `silver.labels`
   - All metrics are atomic (per-label), not aggregated

4. **Data quality**:
   - If a label has no delivery event, `actual_delivery_at` is NULL, `is_delivered` = FALSE, `is_delivered_on_time` = FALSE (not delivered, so not on-time)
   - If a label has multiple delivery-like events (shouldn't happen after Silver dedup, but defensive), the window function keeps the **latest by `event_at`**
   - Preserve all rows (never filter out incomplete shipments) — they're important for "% on-time" calculation

---

## Expected Metric Distribution

The on-time rate is driven by the synthetic data generator, so the mart's output should fall in a predictable range:

- **Late deliveries** are controlled by `late_delivery_proportion` in `config.yaml` (default **3%**). The generator places late shipments' `delivered` event at `carrier_promised_delivery_at + 6–48h`, so ~3% of *delivered* labels land after the promised date.
- **Undelivered labels** (~10–12%): voided, incomplete (stuck before delivery), or never delivered → counted as not-on-time.

Resulting ballpark (5,000 labels, default config):

| Metric | Expected |
|--------|----------|
| Delivered | ~88–89% of labels |
| On-time *of delivered* | ~96–97% |
| **On-time overall** (vs. all labels) | **~85–86%** |

This comfortably satisfies the case study's "80%+ of delivered shipments on-time" check, while still showing a visible late-delivery signal. A reading near **0% or 100% indicates a bug** (e.g. unparsed timestamps or a non-matching `event_name`), not a data artifact.

---

## Phase 1 vs. Phase 2

### Phase 1 MVP (this spec)
- Single operational mart: `skullport.gold.delivery_performance` (one row per label)
- One metric: `is_delivered_on_time`
- Supporting facts: `actual_delivery_at`, `is_delivered`
- All dimensions from Bronze/Silver
- Answers: "What % of labels delivered on-time? Which carriers/regions?"

### Phase 2 (dbt, deferred)
- Analytical aggregation marts (different grains):
  - `skullport.gold.delay_analysis` — one row per carrier+service_class+region (aggregated counts, %, avg days late)
  - `skullport.gold.data_freshness` — one row per label age bucket (tracking data recency metrics)
- Additional metrics (added as columns to main mart):
  - `days_late` = DATEDIFF(actual_delivery_at, carrier_promised_delivery_at)
  - `days_to_first_scan` = DATEDIFF(first_event_at, label_created_at)
  - `event_count` = count of events per label
  - `has_data_quality_issues` — rollup of Silver quality flags
- Incremental refresh strategy (merge instead of OVERWRITE)

---

## Idempotency & Refresh

**Mode**: `CREATE OR REPLACE TABLE` (idempotent, full refresh)

**Rationale**:
- MVP simplicity: clean slate each run
- Re-aggregating all labels is fast (5000 rows, small dataset)
- Enables safe re-runs and historical audit trail (each run is complete)
- Merge/upsert deferred to Phase 2 when incremental volumes matter

---

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| **One metric (MVP)** | Start with the #1 business question: on-time %. Add others in Phase 2 after proving the pattern. |
| **Operational mart** (one row per label) | Direct translation of Silver dimensions + one metric. Easy to extend with new metric columns. Different analytical questions (clustering, freshness) become separate marts with different grains. |
| **LEFT JOIN to events** | Preserves labels with no delivery event (important for accurate "% on-time" — undelivered = not on-time). |
| **Latest delivery event** | Use `MAX(event_at)` to handle any duplicates safely (shouldn't exist after Silver dedup, but defensive). |
| **Never filter rows** | Incomplete/problematic shipments are part of the metric; excluding them would bias analysis. |
| **Full refresh (OVERWRITE)** | Simple, safe, idempotent. Incremental logic deferred to Phase 2. |

---

## Success Criteria

- [ ] Mart reads from `skullport.silver.labels` and `skullport.silver.tracking_events`
- [ ] One row per unique `label_id` (no duplicates)
- [ ] `is_delivered_on_time` correctly computed (on-time if delivered <= promised date)
- [ ] Undelivered labels have `is_delivered=FALSE`, `actual_delivery_at=NULL`, `is_delivered_on_time=FALSE`
- [ ] Rows with data quality issues from Silver are preserved (not filtered)
- [ ] Metric is repeatable: same input = same output (idempotent)
- [ ] Sample queries work:
  - `SELECT COUNT(*) FROM skullport.gold.delivery_performance;` — total labels
  - `SELECT SUM(CASE WHEN is_delivered_on_time THEN 1 ELSE 0 END) / COUNT(*) * 100 FROM skullport.gold.delivery_performance;` — % on-time
  - `SELECT carrier, SUM(CASE WHEN is_delivered_on_time THEN 1 ELSE 0 END) / COUNT(*) * 100 AS pct_on_time FROM skullport.gold.delivery_performance GROUP BY carrier;` — by carrier
