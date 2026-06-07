"""Main orchestration script for Pirate Ship synthetic data generator."""

import sys
import logging
import pandas as pd
from pathlib import Path

from pyspark.sql import SparkSession

from pirate_ship_generator.config import load_config
from pirate_ship_generator.labels_generator import (
    generate_base_labels,
    apply_cdc_changes,
)
from pirate_ship_generator.events_generator import generate_events
from pirate_ship_generator.writer import write_all, validate_written_data


# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main(config_path: str = "config.yaml") -> dict:
    """
    Main orchestration function for synthetic data generation.

    Workflow:
    1. Load configuration from YAML
    2. Create SparkSession
    3. Generate base labels
    4. Apply CDC changes (voiding, field updates)
    5. Generate tracking events
    6. Write both DataFrames to Delta tables
    7. Validate written data

    Args:
        config_path: Path to config.yaml file (default: "config.yaml")

    Returns:
        Dictionary with generation statistics:
        {
            "status": "success" or "error",
            "labels_count": int,
            "events_count": int,
            "labels_path": str,
            "events_path": str,
            "message": str
        }

    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If configuration is invalid
        Exception: If generation or writing fails
    """
    try:
        # ===== Step 1: Load Configuration =====
        logger.info(f"Loading configuration from {config_path}")
        config_path_obj = Path(config_path)
        if not config_path_obj.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        config = load_config(config_path)
        logger.info(f"✓ Configuration loaded")

        # ===== Step 2: Initialize Spark =====
        logger.info("Initializing SparkSession")
        spark = SparkSession.builder \
            .appName("pirate-ship-generator") \
            .config("spark.sql.adaptive.enabled", "true") \
            .getOrCreate()
        logger.info("✓ SparkSession initialized")

        # ===== Step 3: Generate Base Labels =====
        logger.info("Generating base labels")
        labels_df = generate_base_labels(config)
        logger.info(f"✓ Generated {len(labels_df)} base labels")

        # ===== Step 4: Apply CDC Changes =====
        logger.info("Applying CDC changes (voiding, field updates)")
        labels_df = apply_cdc_changes(labels_df, config)
        logger.info(f"✓ Applied CDC changes, now {len(labels_df)} label rows")

        # ===== Step 5: Generate Events =====
        logger.info("Generating tracking events")
        events_list = generate_events(labels_df, config)
        logger.info(f"✓ Generated {len(events_list)} events")

        # ===== Step 6: Convert Events to DataFrame =====
        logger.info("Converting events to DataFrame")
        events_df = pd.DataFrame(events_list)
        logger.info(f"✓ Events DataFrame has {len(events_df)} rows")

        # ===== Step 7: Write to Delta Tables (Bronze Layer) =====
        logger.info("Writing data to Bronze tables (landing zone)")
        labels_path = config.get("delta_labels_path", "/mnt/bronze/labels")
        events_path = config.get("delta_events_path", "/mnt/bronze/tracking_events")

        write_all(
            spark,
            labels_df,
            events_df,
            labels_path=labels_path,
            events_path=events_path,
            mode="overwrite"
        )
        logger.info("✓ Data written to Delta tables")

        # ===== Step 8: Validate Written Data =====
        logger.info("Validating written data")
        validation_results = validate_written_data(spark, labels_path, events_path)

        if validation_results["all_valid"]:
            logger.info("✓ All data validated successfully")
            status = "success"
        else:
            logger.warning("⚠ Some validation checks failed")
            status = "success_with_warnings"

        # ===== Summary =====
        summary = {
            "status": status,
            "labels_count": len(labels_df),
            "events_count": len(events_df),
            "labels_path": labels_path,
            "events_path": events_path,
            "message": f"Successfully generated {len(labels_df)} labels and {len(events_df)} events"
        }

        logger.info("=" * 70)
        logger.info("BRONZE LAYER COMPLETE (Data Landing Zone)")
        logger.info("=" * 70)
        logger.info(f"Bronze labels: {len(labels_df)} rows → {labels_path}")
        logger.info(f"Bronze events: {len(events_df)} rows → {events_path}")
        logger.info(f"Status: {status}")
        logger.info("Ready for Silver layer (transformations)")

        return summary

    except FileNotFoundError as e:
        logger.error(f"❌ Configuration error: {e}")
        return {
            "status": "error",
            "message": str(e),
            "error_type": "FileNotFoundError"
        }

    except ValueError as e:
        logger.error(f"❌ Configuration validation error: {e}")
        return {
            "status": "error",
            "message": str(e),
            "error_type": "ValueError"
        }

    except Exception as e:
        logger.error(f"❌ Generation failed: {e}", exc_info=True)
        return {
            "status": "error",
            "message": str(e),
            "error_type": type(e).__name__
        }


if __name__ == "__main__":
    # Parse command-line arguments
    if len(sys.argv) > 1:
        config_file = sys.argv[1]
    else:
        config_file = "config.yaml"

    # Run main orchestration
    result = main(config_file)

    # Exit with appropriate code
    if result["status"] == "success":
        sys.exit(0)
    elif result["status"] == "success_with_warnings":
        sys.exit(0)  # Still exit 0, but logged warnings
    else:
        sys.exit(1)
