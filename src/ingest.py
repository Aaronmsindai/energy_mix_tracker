"""
Ingestion script — pull UK energy mix data from the Carbon Intensity API
and store it in PostgreSQL.

Flow:
    1. Fetch latest generation mix from API
    2. Store raw JSON in raw_generation (audit)
    3. Parse fuel mix -> insert into fact_energy_mix
    4. Look up dimension IDs
    5. Idempotent: skip rows that already exist

Run:
    python -m src.ingest
"""

import json
from datetime import datetime, timezone

import requests
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.db import get_session, init_db
from src.models import DimCountry, DimEnergySource, FactEnergyMix, RawGeneration


API_URL = "https://api.carbonintensity.org.uk/generation"
COUNTRY_CODE = "UK"


def fetch_generation() -> dict:
    """Fetch current energy mix from the API."""
    print(f"Fetching from {API_URL}")
    response = requests.get(API_URL, timeout=15)
    response.raise_for_status()
    return response.json()["data"]


def parse_timestamps(period_str: str) -> datetime:
    """Parse ISO 8601 timestamp from the API."""
    return datetime.fromisoformat(period_str.replace("Z", "+00:00"))


def ingest() -> dict:
    """Run the full ingestion: fetch -> store raw -> insert fact rows (idempotent)."""
    init_db()
    session = get_session()

    try:
        # 1. Fetch
        data = fetch_generation()
        period_from = parse_timestamps(data["from"])
        period_to = parse_timestamps(data["to"])
        mix = data["generationmix"]

        print(f"   Period: {period_from.isoformat()} -> {period_to.isoformat()}")
        print(f"   Sources: {len(mix)}")

        # 2. Store raw JSON (audit trail)
        raw = RawGeneration(
            fetched_at=datetime.now(timezone.utc).replace(tzinfo=None),
            api_from=period_from.replace(tzinfo=None),
            api_to=period_to.replace(tzinfo=None),
            raw_json=json.dumps(data),
        )
        session.add(raw)
        session.flush()
        print(f"   Raw stored with id={raw.id}")

        # 3. Look up dimensions
        country = session.execute(
            select(DimCountry).where(DimCountry.code == COUNTRY_CODE)
        ).scalar_one()

        source_map = {
            s.name: s
            for s in session.execute(select(DimEnergySource)).scalars()
        }

        # 4. Insert one fact row per energy source, skip duplicates
        inserted = 0
        skipped = 0
        period_start_naive = period_from.replace(tzinfo=None)
        period_end_naive = period_to.replace(tzinfo=None)

        for item in mix:
            fuel = item["fuel"]
            if fuel not in source_map:
                print(f"   Unknown source: {fuel} - skipping")
                skipped += 1
                continue

            stmt = pg_insert(FactEnergyMix).values(
                country_id=country.id,
                source_id=source_map[fuel].id,
                period_start=period_start_naive,
                period_end=period_end_naive,
                percentage=round(float(item["perc"]), 2),
            ).on_conflict_do_nothing(
                constraint="uq_fact_energy_mix",
            )

            result = session.execute(stmt)
            if result.rowcount > 0:
                inserted += 1
            else:
                skipped += 1

        session.commit()
        print(f"\n Ingested {inserted} rows (skipped {skipped} duplicates)")

        return {
            "period_from": period_from.isoformat(),
            "period_to": period_to.isoformat(),
            "inserted": inserted,
            "skipped": skipped,
        }

    except Exception as e:
        session.rollback()
        print(f" Error: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    result = ingest()
    print(f"\nResult: {result}")
