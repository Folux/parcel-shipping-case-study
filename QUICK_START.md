# Quick Start - Bronze Layer Deployment

## To get it running on  Databricks

- Log into your Databricks account
- Click **New** → **Git folder**
- Paste repo URL: `https://github.com/Folux/parcel-shipping-case-study.git`
- Click **Clone**
- From your Workspace home navigate to: `parcel-shipping-case-study/notebooks/skullport_generator.py`
- Click **Run all**
- Wait 5-10 minutes for completion
- Check Databricks Catalog:
  - `pirate_ship.bronze.labels` (~5000 rows)
  - `pirate_ship.bronze.tracking_events` (~30000 rows)
- Done! Bronze layer deployed ✅

## Next Steps

- Silver layer implementation: Coming soon
- For details, see: `planning/specs/SPEC_4b_Pipeline.md`
