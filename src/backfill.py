"""
Historical backfill for the Energy Mix Tracker.

Fetches historical generation mix data from the Carbon Intensity API
and inserts it into PostgreSQL. Idempotent — re-running skips existing
periods.

The API returns data in 30-minute blocks. We chunk requests in 14-day
windows (API limit) and iterate.

Run:
    python -m src.backfill
    python -m src.backfill --days 60
"""

import argparse
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

# Add project root to path (for `python src/backfill.py` usage)
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.db import get_session, init_db
from src.models import DimCountry, DimEnergySource, FactEnergyMix, RawGeneration


API_BASE = "https://api.carbonintensity.org.uk"
COUNTRY_CODE = "UK"
CHUNK_DAYS = 14  # API max window for the intensity endpoint
SLEEP_BETWEEN_REQUESTS = 1.0  # seconds, to be polite to the API


def fetch_generation_range(start: datetime, end: datetime) -> dict:
    """Fetch generation mix for a time range (max 14 days)."""
    start_str = start.strftime("%Y-%m-%dT%H:%MZ")
    end_str = end.strftime("%Y-%m-%dT%H:%MZ")
    url = f"{API_BASE}/generation/{start_str}/{end_str}"
    print(f"  → {start_str} to {end_str}")
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.json()


def parse_timestamps(period_str: str) -> datetime:
    """Parse ISO 8601 timestamp from the API."""
    return datetime.fromisoformat(period_str.replace("Z", "+00:00"))


def ingest_chunk(session, country_id: int, source_map: dict, data_item: dict) -> int:
    """Insert one period's fuel mix. Returns number of rows inserted."""
    period_from = parse_timestamps(data_item["from"])
    period_to = parse_timestamps(data_item["to"])
    mix = data_item["generationmix"]

    period_start_naive = period_from.replace(tzinfo=None)
    period_end_naive = period_to.replace(tzinfo=None)

    inserted = 0
    for item in mix:
        fuel = item["fuel"]
        if fuel not in source_map:
            continue

        stmt = pg_insert(FactEnergyMix).values(
            country_id=country_id,
            source_id=source_map[fuel].id,
            period_start=period_start_naive,
            period_end=period_end_naive,
            percentage=round(float(item["perc"]), 2),
        ).on_conflict_do_nothing(constraint="uq_fact_energy_mix")

        result = session.execute(stmt)
        if result.rowcount > 0:
            inserted += 1

    return inserted


def backfill(days: int = 30) -> dict:
    """Fetch the last N days of historical data."""
    init_db()
    session = get_session()

    try:
        # Look up dimensions
        country = session.execute(
            select(DimCountry).where(DimCountry.code == COUNTRY_CODE)
        ).scalar_one()

        source_map = {
            s.name: s
            for s in session.execute(select(DimEnergySource)).scalars()
        }

        # Compute time range
        end = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        start = end - timedelta(days=days)

        print(f"Backfilling from {start.isoformat()} to {end.isoformat()}")
        print(f"Chunk size: {CHUNK_DAYS} days\n")

        total_inserted = 0
        total_periods = 0
        current = start

        while current < end:
            chunk_end = min(current + timedelta(days=CHUNK_DAYS), end)

            try:
                payload = fetch_generation_range(current, chunk_end)
                items = payload.get("data", [])
                print(f"     received {len(items)} periods")

                # Store raw response
                raw = RawGeneration(
                    fetched_at=datetime.now(timezone.utc).replace(tzinfo=None),
                    api_from=current.replace(tzinfo=None),
                    api_to=chunk_end.replace(tzinfo=None),
                    raw_json=json.dumps(payload)[:500000],  # cap size
                )
                session.add(raw)

                for item in items:
                    total_inserted += ingest_chunk(session, country.id, source_map, item)
                    total_periods += 1

                session.commit()

            except Exception as e:
                session.rollback()
                print(f"    ERROR: {e}")
                raise

            current = chunk_end
            time.sleep(SLEEP_BETWEEN_REQUESTS)

        print(f"\n Backfill complete.")
        print(f"   Periods fetched:  {total_periods}")
        print(f"   Rows inserted:    {total_inserted}")

        return {
            "days": days,
            "periods": total_periods,
            "rows_inserted": total_inserted,
        }

    finally:
        session.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=30, help="Days of history to fetch")
    args = parser.parse_args()

    result = backfill(days=args.days)
    print(f"\nResult: {result}")
