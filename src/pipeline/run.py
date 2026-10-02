"""Pipeline orchestration: raw -> staging -> core (snowflake) -> marts, with run logging.

Full refresh and idempotent: every run drops and rebuilds staging, core and marts from the raw files,
so two runs on the same input produce identical core tables. Only the ops tables keep history.
"""
from __future__ import annotations

import os
import traceback
import uuid
from datetime import datetime
from pathlib import Path

import duckdb
import pandas as pd

from src.generate.config import ROOT, load_config

from . import quality, staging
from .sqlio import SQL_DIR

DB_PATH = Path(os.environ.get("GAW_DB", ROOT / "data" / "warehouse" / "gaw.duckdb"))

CORE_TABLES = ["dim_year", "dim_quarter", "dim_month", "dim_date", "dim_region", "dim_country", "dim_channel",
               "dim_campaign", "dim_acquisition_source", "dim_plan_tier", "dim_plan", "dim_user",
               "fact_ad_performance", "fact_user_daily_usage", "fact_subscription_event", "fact_user_scores"]
MARTS = ["mart_subscription_history", "mart_user_lifecycle", "mart_funnel_country",
         "mart_unit_economics_country_month", "mart_usage_pareto", "mart_free_limit_simulation",
         "mart_retention_cohorts", "mart_user_features"]


def _exec_dir(con, sub: str) -> None:
    for f in sorted((SQL_DIR / sub).glob("*.sql")):
        con.execute(f.read_text(encoding="utf-8"))


def _reset(con) -> None:
    for (v,) in con.execute("SELECT view_name FROM duckdb_views() WHERE NOT internal").fetchall():
        con.execute(f"DROP VIEW IF EXISTS {v}")
    for t in reversed(CORE_TABLES):
        con.execute(f"DROP TABLE IF EXISTS {t}")
    con.execute("DROP TABLE IF EXISTS warehouse_meta")


def _table_counts(con, names, layer) -> list[tuple[str, str, int]]:
    return [(layer, n, con.execute(f"SELECT COUNT(*) FROM {n}").fetchone()[0]) for n in names]


def run_pipeline(db_path: str | Path | None = None, raw_dir: str | Path | None = None,
                 cfg: dict | None = None) -> dict:
    cfg = cfg or load_config()
    db_path = Path(db_path or DB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path))
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
    as_of = cfg["as_of_date"]
    con.execute((SQL_DIR / "ddl" / "060_ops.sql").read_text(encoding="utf-8"))
    con.execute("INSERT INTO pipeline_runs (run_id, started_at, status, as_of_date) VALUES (?, ?, 'running', ?)",
                [run_id, datetime.now(), as_of])
    try:
        _reset(con)
        info = staging.run_staging(con, cfg, raw_dir)
        for f in sorted((SQL_DIR / "ddl").glob("*.sql")):
            if not f.name.startswith("060"):
                con.execute(f.read_text(encoding="utf-8"))
        cal_start = con.execute("SELECT MIN(d) FROM (SELECT MIN(signup_date) d FROM staging.stg_users "
                                "UNION ALL SELECT MIN(period_start) FROM staging.stg_ad_performance "
                                "UNION ALL SELECT MIN(usage_date) FROM staging.stg_usage_daily)").fetchone()[0]
        cal_start = pd.Timestamp(cal_start).replace(day=1).strftime("%Y-%m-%d")
        cal_end = f"{pd.Timestamp(as_of).year}-12-31"
        con.executemany("INSERT INTO warehouse_meta VALUES (?, ?)",
                        [("as_of_date", as_of), ("calendar_start", cal_start), ("calendar_end", cal_end),
                         ("synthetic", "true"), ("company", cfg["company"])])
        _exec_dir(con, "staging")
        _exec_dir(con, "marts")

        counts = [("raw", k, v) for k, v in info["raw"].items()]
        counts += [("staging", k, v) for k, v in info["staging"].items()]
        counts += _table_counts(con, CORE_TABLES, "core") + _table_counts(con, MARTS, "marts")
        results = quality.run_checks(con, info)
        now = datetime.now()
        con.executemany("INSERT INTO data_quality_results VALUES (?, ?, ?, ?, ?, ?)",
                        [(run_id, n, layer, st, d, now) for n, layer, st, d in results])
        con.executemany("INSERT INTO pipeline_run_tables VALUES (?, ?, ?, ?)",
                        [(run_id, layer, name, int(c)) for layer, name, c in counts])
        by_layer = {ly: sum(c for l2, _, c in counts if l2 == ly) for ly in ("raw", "staging", "core", "marts")}
        statuses = {r[2] for r in results}
        status = "failed" if "fail" in statuses else ("success_with_warnings" if "warn" in statuses else "success")
        con.execute("UPDATE pipeline_runs SET finished_at=?, status=?, raw_rows=?, staging_rows=?, core_rows=?, "
                    "mart_rows=?, message=? WHERE run_id=?",
                    [datetime.now(), status, by_layer["raw"], by_layer["staging"], by_layer["core"], by_layer["marts"],
                     f"{sum(r[2] == 'pass' for r in results)} pass / {sum(r[2] == 'warn' for r in results)} warn / "
                     f"{sum(r[2] == 'fail' for r in results)} fail", run_id])
        return {"run_id": run_id, "status": status, "counts": by_layer, "db": str(db_path),
                "failed": [r for r in results if r[2] == "fail"], "warned": [r for r in results if r[2] == "warn"]}
    except Exception as exc:  # record the failure, then surface it
        con.execute("UPDATE pipeline_runs SET finished_at=?, status='failed', message=? WHERE run_id=?",
                    [datetime.now(), (type(exc).__name__ + ": " + str(exc))[:500], run_id])
        traceback.print_exc()
        raise
    finally:
        con.close()
