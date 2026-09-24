"""
SQLAlchemy models for the Energy Mix Tracker.

Schema:
    dim_country:         Country reference
    dim_energy_source:   Energy source reference
    raw_generation:      Raw API responses (audit log)
    fact_energy_mix:     Cleaned analytics-ready energy mix
"""

from datetime import datetime,
timezone

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class DimCountry(Base):
    __tablename__ = "dim_country"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(8), unique=True, nullable=False)
    name = Column(String(64), nullable=False)

    def __repr__(self) -> str:
        return f"<DimCountry {self.code}: {self.name}>"


class DimEnergySource(Base):
    __tablename__ = "dim_energy_source"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(32), unique=True, nullable=False)
    is_renewable = Column(Integer, nullable=False, default=0)

    def __repr__(self) -> str:
        renewable = "renewable" if self.is_renewable else "non-renewable"
        return f"<DimEnergySource {self.name} ({renewable})>"


class RawGeneration(Base):
    """Raw API responses stored as-is for audit purposes."""

    __tablename__ = "raw_generation"

    id = Column(Integer, primary_key=True, autoincrement=True)
    fetched_at = Column(DateTime, 
    default=lambda:
    Datetime.now(timezone.utc).replace(tzinfo=None),
    Nullable=False)
    api_from = Column(DateTime, nullable=False)
    api_to = Column(DateTime, nullable=False)
    raw_json = Column(String, nullable=False)

    def __repr__(self) -> str:
        return f"<RawGeneration {self.api_from} → {self.api_to}>"


class FactEnergyMix(Base):
    """Analytics-ready energy mix by source and period."""

    __tablename__ = "fact_energy_mix"

    id = Column(Integer, primary_key=True, autoincrement=True)
    country_id = Column(Integer, ForeignKey("dim_country.id"), nullable=False)
    source_id = Column(Integer, ForeignKey("dim_energy_source.id"), nullable=False)
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    percentage = Column(Numeric(5, 2), nullable=False)

    country = relationship("DimCountry")
    source = relationship("DimEnergySource")

    __table_args__ = (
        UniqueConstraint(
            "country_id", "source_id", "period_start",
            name="uq_fact_energy_mix",
        ),
    )

    def __repr__(self) -> str:
        return f"<FactEnergyMix {self.period_start:%Y-%m-%d} {self.percentage}%>"