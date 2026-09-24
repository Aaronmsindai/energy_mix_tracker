"""
Seed the dimension tables with reference data.

Run once to populate dim_country and dim_energy_source.
"""

from src.db import get_session, init_db
from src.models import DimCountry, DimEnergySource


COUNTRIES = [
    {"code": "UK", "name": "United Kingdom"},
]

SOURCES = [
    {"name": "biomass",   "is_renewable": 1},
    {"name": "coal",      "is_renewable": 0},
    {"name": "imports",   "is_renewable": 0},
    {"name": "gas",       "is_renewable": 0},
    {"name": "nuclear",   "is_renewable": 0},
    {"name": "other",     "is_renewable": 0},
    {"name": "hydro",     "is_renewable": 1},
    {"name": "solar",     "is_renewable": 1},
    {"name": "wind",      "is_renewable": 1},
]


def seed() -> None:
    """Populate dimension tables idempotently."""
    init_db()
    session = get_session()

    try:
        for c in COUNTRIES:
            existing = session.query(DimCountry).filter_by(code=c["code"]).first()
            if not existing:
                session.add(DimCountry(**c))
                print(f"  + Country: {c['code']} - {c['name']}")

        for s in SOURCES:
            existing = session.query(DimEnergySource).filter_by(name=s["name"]).first()
            if not existing:
                session.add(DimEnergySource(**s))
                renewable = "renewable" if s["is_renewable"] else "non-renewable"
                print(f"  + Source:  {s['name']} ({renewable})")

        session.commit()
        print("\n Dimension tables seeded.")

    except Exception as e:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    seed()
