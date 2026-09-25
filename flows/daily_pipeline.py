"""
Scheduled pipeline runner for the Energy Mix Tracker.

A lightweight scheduler that runs the ingestion on a fixed interval.
Replaces Prefect with a simple time-based loop — same outcome, zero
dependency conflicts.

Run once:
    python flows/daily_pipeline.py

Run continuously (every 30 min):
    python -c "from flows.daily_pipeline import run_forever; run_forever()"
"""

import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.ingest import ingest as run_ingest


DEFAULT_INTERVAL_MINUTES = 30


def run_once() -> dict:
    """Run the ingestion once and log the result."""
    started = datetime.now(timezone.utc).isoformat()
    print(f"[{started}] Starting pipeline run...")

    try:
        result = run_ingest()
        finished = datetime.now(timezone.utc).isoformat()
        print(
            f"[{finished}] Complete. "
            f"Inserted {result['inserted']} rows for period {result['period_from']}"
        )
        return result
    except Exception as e:
        print(f"[{datetime.now(timezone.utc).isoformat()}] ERROR: {e}")
        traceback.print_exc()
        raise


def run_forever(interval_minutes: int = DEFAULT_INTERVAL_MINUTES) -> None:
    """Run the pipeline on a fixed interval forever."""
    print(f"Pipeline scheduler started. Interval: {interval_minutes} min")
    print("Press Ctrl+C to stop.\n")

    while True:
        try:
            run_once()
        except Exception:
            # Swallow errors so the loop keeps running
            pass

        next_run = datetime.now(timezone.utc).isoformat()
        print(f"[{next_run}] Sleeping for {interval_minutes} minutes...\n")
        time.sleep(interval_minutes * 60)


if __name__ == "__main__":
    run_once()
