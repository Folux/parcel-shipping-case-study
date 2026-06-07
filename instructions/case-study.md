# Senior Data Engineer — Case Study

## Welcome aboard, Pirate ☠️

Thanks for taking the time to dig into this with us. This case study is the technical core of the Senior Data Engineer loop at **Pirate Ship**. Your work here will anchor a 60–90 minute walkthrough with two members of the Data Platform crew.

A few principles up front:

- **Time-box: about 6 focused hours.** Treat it like a sprint, not a thesis. We'd rather see deliberate scope cuts than an over-engineered submission.
- **It's a take-home, not a trap.** There is no single correct answer. We care as much about *how* you reason about trade-offs as *what* you build.
- **Use the tools you'd reach for at work.** AI assistants are explicitly allowed — see Section 5.

The scenario itself is set at a fictional company so we can talk about real architecture without any NDA dance. The shape of the problem is very close to what you'd encounter on the team.

---

## 1. The setting

You've just joined the Data Platform team at **Skullport Logistics**, a fictional US-based shipping marketplace. Skullport sells discounted shipping labels (USPS, UPS, FedEx, …) to small businesses and ships parcels at meaningful scale.

---

## 2. The problem

The Customer Success team has been complaining for months: when a customer calls about a "late package", nobody can confidently tell them whether the shipment is *actually* late, or whether the carrier is simply slow to report a scan. The Analytics team has a notebook-stitched dashboard that lies often enough that nobody trusts it.

Leadership has asked the Data Platform team to ship a **Delivery Performance Mart** that Analytics can build their dashboards on top of. Stakeholders want to answer questions like:

- What % of shipments were delivered on or before the carrier's promised date, broken down by carrier and service level?
- Where do delays cluster — origin region, lane, day-of-week, service class?
- How fresh and complete is our tracking data — for what fraction of recent shipments do we have a recent tracking event?

You are **not** building dashboards. You are building the data foundation that makes those dashboards trivial.

---

## 3. What you'll start with

We are deliberately not handing you a dataset. You'll generate it yourself (Section 4a). What we *are* giving you is:

1. **The fixed schemas of the two raw sources** (below). Your generator must produce data that matches them. How you represent the schemas inside Python is your call.
2. **The categories of mess we'd expect in real carrier data.** We don't specify proportions — pick what you can defend. The dataset should include a representative subset of:
   - Duplicate tracking events (same logical event, multiple landings)
   - Late-arriving tracking events (events whose `event_at` is far before `event_received_at`)
   - Malformed rows (bad timestamps, missing required fields, JSON that won't parse)
   - Schema drift between carriers (see the schema notes)
   - Voided labels that still receive downstream tracking events
   - Timezone weirdness in `event_at`

We do **not** specify volumes. Pick volumes that exercise the modeling problems you care about and that run cleanly on Databricks Free Edition. State your choice in the README.

### Schema — `raw.labels` (Delta table)

A daily CDC-style export from the Skullport application. One row per label, plus additional rows for label updates over time — ordered by `last_updated_at`.

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `label_id` | STRING | no | Format `lbl_<24 hex>` |
| `customer_id` | STRING | no | Format `cust_<12 hex>` |
| `carrier` | STRING | no | One of `USPS`, `UPS`, `FEDEX`, `DHL_ECOM` |
| `service_class` | STRING | no | Carrier-specific (e.g. `USPS_PRIORITY`, `UPS_GROUND`) |
| `origin_zip` | STRING | no | 5-digit US ZIP |
| `dest_zip` | STRING | no | 5-digit US ZIP |
| `weight_oz` | INT | no | 1 to 1120 (70 lb cap) |
| `declared_value_cents` | INT | yes | 0 or null when no insurance was purchased |
| `label_created_at` | TIMESTAMP | no | UTC |
| `carrier_promised_delivery_at` | TIMESTAMP | no | UTC, carrier's estimate at purchase time |
| `voided_at` | TIMESTAMP | yes | UTC, populated if the customer voided the label |
| `last_updated_at` | TIMESTAMP | no | UTC, CDC update timestamp. Use this to determine the latest row per `label_id` |

### Schema — `raw.tracking_events` (Delta table)

Carrier scan events as they land in our system. Semi-structured; carriers don't agree on a single shape.

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `event_id` | STRING | no | UUID-style. Usually unique but **not** guaranteed |
| `label_id` | STRING | no | Joins to `raw.labels.label_id` |
| `carrier` | STRING | no | Same enum as labels |
| `event_code` | STRING | yes | Carrier-specific code. **Schema drift:** some carriers populate `event_type` rather than `event_code` |
| `event_type` | STRING | yes | See above |
| `event_at` | STRING | no | ISO 8601. **Timezone offset is sometimes present, sometimes missing** depending on carrier |
| `event_received_at` | TIMESTAMP | no | UTC, when our system received the event |
| `location_zip` | STRING | yes | Scan location ZIP, some carriers omit |
| `raw_payload` | STRING | yes | Stringified JSON of the original carrier payload; shape varies by carrier |

> **Why STRING and not TIMESTAMP for `event_at`?** Because real carrier payloads are inconsistent and Bronze should keep raw fidelity. Parsing the timestamp is part of Silver's job.

The target catalog/schema/table names are illustrative. You decide the exact names in your workspace; document your choice in the README.

---

## 4. What we want you to build

Three things, in this order — plus an optional bonus.

### 4a. A synthetic-data generator (Python)

A standalone Python project that, when run inside Databricks Free Edition, **creates the Unity Catalog assets from Section 3** (catalog, schema, and Delta tables) and populates them with synthetic data.

Treat this generator as production-grade Python. Concretely, we expect:

- **A project layout** you'd be comfortable shipping to a colleague — clear module boundaries, no everything-in-one-file.
- **Reproducible environment.** A single command (or two) should be enough to install dependencies and run the generator. Dependencies should be locked.
- **Type hints** where they earn their keep.
- **Re-runnability** — running the generator twice in a row should not leave the catalog in a broken state.
- **Honest configuration** — volumes, mess proportions, and the target catalog name should be configurable, not hard-coded constants buried in the code.

How you ship the generator into Databricks Free Edition (notebook, `%pip install` from a wheel, Databricks Connect, Repos, …) is up to you. Document the path you chose.

We don't prescribe libraries. Use what you'd reach for at work — including for project layout, dependency management, linting, and typing. Choosing well is itself signal.

### 4b. The Bronze → Silver → Gold pipeline

On top of the Delta tables your generator produced, build a working Bronze → Silver → Gold pipeline in the same Databricks Free Edition workspace.

- **Bronze**: idempotent landing/registration of the two raw sources. Schema preserved as-is.
- **Silver**: cleaned, deduplicated, conformed types, business keys resolved. Handle the obvious data-quality issues (duplicates, late events, voided labels, malformed rows) and make your handling explicit.
- **Gold**: at least one mart table that the Analytics team could query directly to answer the questions in Section 2.

The pipeline should be:

- **Idempotent.** Re-running a day should not double-count or corrupt downstream tables.
- **Resilient to late-arriving tracking events.** A scan that lands three days after the delivery date should still flow to the right place.
- **Tested.** At least three meaningful data-quality checks. Your choice of framework — Great Expectations, Soda, dbt tests, Delta constraints, hand-rolled — explain why.

We also require:

- **Databricks Asset Bundles** for packaging and deployment. We want to see your `databricks.yml`, the resources you define (jobs / pipelines / workflows), and a single command path that deploys the bundle to your Free Edition workspace.
- A real **combination of PySpark, Databricks SQL, and dbt** — use each where it earns its place. If you'd skip one, defend that call in the README rather than silently dropping it.

### 4c. The README

A short README in the repo that covers:

- **How to install the project and run the generator + pipeline end-to-end.** We'll run it with you during the walkthrough.
- **The volumes and mess proportions** your generator produced, and why those.
- **A "Project overview"** — two or three paragraphs (or a tight bulleted breakdown) describing how this pipeline would actually look beyond the prototype. Cover: ingestion path from real source systems, where transformation work lives, orchestration, observability, IaC, CI/CD, access. Be specific about tools at each seam. Note explicitly what changes between your prototype and the real thing — including the fact that at full scale you would *not* be generating your own data.
- **Three trade-offs** you made consciously.
- **One thing you'd change first** if you had another full day.
- **Your AI usage** (Section 5).

### 4d. Bonus — Provisioning groups, users, and grants with Pulumi (optional)

> **Strictly optional.** No penalty if you skip. Platform IaC is real Senior DE work at Pirate Ship — if you finish 4a–4c with energy in the tank, this is your chance to show that craft.

Build a **Pulumi project in TypeScript** that provisions, in your Databricks Free Edition workspace:

- **A sensible set of workspace groups.** Use your own judgment. We'd expect to see, at minimum, distinct groups for platform admins, data engineers, analytics engineers, analyst / consumer roles, and automation. Plus a deliberate **PII separation** — access to customer-identifying data (think `customer_id`, ZIP codes, addresses) should *not* be granted to every reader by default.
- **A handful of dummy users**, defined in **YAML config files** the Pulumi program reads at deploy time. Design the YAML schema yourself, but make it useful for governance at scale. Specifically, think about:
  - **User lifecycle.** What attributes tell future-you (or a SOC2 auditor) when a user was on-boarded, deactivated, and what happened to anything they owned? Take a position in the README on what your model does when a user is deactivated and they owned tables, jobs, or secrets — reassign, archive, soft-delete, fail loud. Don't handwave.
  - **HR / governance context.** Team, cost-center, manager — what would let the data platform correlate identities back to the rest of the org without it being painful.
  - **PII access basis.** Not just `pii_readers: true`. The justification — role, ticket, expiry — should live somewhere in the schema.
- **Group memberships** wired from the YAML. Adding or removing a user from a group should be a one-line YAML change, not a Pulumi-code change.
- **Catalog grants** that match the group model. At minimum: a non-PII catalog/schema readable by most groups, and a PII-segregated catalog/schema readable by the PII group only.

Treat this like the generator: project layout, locked dependencies, single command path (`pulumi up` should just work given a workspace URL and PAT). We'll explore the code the same way.

---

## 5. Working with AI

We use AI assistants every day. You should too on this exercise.

- **Encouraged**: Copilot, Cursor, Claude Code, ChatGPT, whatever you actually use. Treat this like a real work day.
- **Required**: include an "AI usage" section in your README — which tools you used, roughly where (e.g., *"Claude for the carrier-event deduplication logic; Copilot for boilerplate"*), and one or two places you pushed back on what the AI suggested.

The walkthrough will explore the code together, regardless of who wrote it. The goal is to understand and discuss the choices made. It's a collaborative review to understand the decisions behind the implementation.

---

## 6. Deliverables

When you're done, share with us a **Git repository** — a GitLab or GitHub link, or a clean archive if your repo is private — containing the generator, the pipeline, the README, and any supporting notebooks or scripts.

Please don't prepare slides — the walkthrough is a conversation around your repo and README, not a presentation.

---

## 7. What we won't be evaluating

To save you time, here's what we're explicitly *not* looking at:

- Slick visualizations or dashboards.
- Heavy IaC for the main pipeline. A README "project overview" is enough — the *bonus* task in Section 4d is the only place we want to see real IaC.
- Test coverage of every line. Three thoughtful DQ checks beat thirty trivial ones.
- A generator that perfectly mimics real carrier data. Representative noise is enough.

---

## 8. The walkthrough

- You walk us through the repo, the generator, and the project overview at your own pace. If you tackled the bonus, give us a brief tour of the IaC setup too.
- We dig into trade-offs, scale, edge cases, and what production would need.
- Your questions for us about the team, stack, and life at Pirate Ship.

---

## 9. Time budget & expectations

Plan on **about 6 hours of focused work**, spread across whatever days suit you. If you find yourself approaching eight, please stop, write down what you'd do next in the README, and submit. The missing pieces won't sink your candidacy.

Treat this as a guide, not a contract. If you find yourself two hours into the generator with no end in sight, that's the moment to cut. The bonus only makes sense if you have real time left after 4a–4c — never sacrifice the core task for it. **Hard stop at 8h total across everything.**
