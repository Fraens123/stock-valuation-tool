from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .models import Base
# Import table modules so their models are registered on Base.metadata before create_all.
from . import ai_review_models as _ai_review_models  # noqa: F401


DEFAULT_DB_PATH = Path("data/stock_valuation.db")


def build_engine(db_path: Path = DEFAULT_DB_PATH):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{db_path}", future=True)


engine = build_engine()
SessionLocal = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)


def init_database() -> None:
    Base.metadata.create_all(engine)


def get_session() -> Session:
    return SessionLocal()
