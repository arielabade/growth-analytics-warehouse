"""Shared helpers for the analysis modules (SYNTHETIC data only)."""
from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pandas as pd
import yaml

from src.generate.config import ROOT, load_config
from src.pipeline.run import DB_PATH
from src.pipeline.sqlio import run_query

__all__ = ["connect", "q", "analysis_cfg", "synthetic_cfg", "save_result", "load_result", "ROOT"]


def connect(db: str | Path | None = None, read_only: bool = True) -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(db or DB_PATH), read_only=read_only)


def q(con, query_id: str) -> pd.DataFrame:
    """Run a catalogued query from ``sql/`` by id."""
    return run_query(con, query_id)


def analysis_cfg() -> dict:
    with open(ROOT / "config" / "analysis.yaml", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def synthetic_cfg() -> dict:
    return load_config()


def save_result(con, name: str, payload: dict) -> None:
    """Persist a JSON payload (model metrics, headline numbers) next to the warehouse tables."""
    con.execute("CREATE TABLE IF NOT EXISTS analysis_results (name VARCHAR PRIMARY KEY, payload VARCHAR, created_at TIMESTAMP DEFAULT now())")
    con.execute("DELETE FROM analysis_results WHERE name = ?", [name])
    con.execute("INSERT INTO analysis_results (name, payload) VALUES (?, ?)", [name, json.dumps(payload, default=float)])


def load_result(con, name: str) -> dict | None:
    try:
        row = con.execute("SELECT payload FROM analysis_results WHERE name = ?", [name]).fetchone()
    except duckdb.CatalogException:
        return None
    return json.loads(row[0]) if row else None
