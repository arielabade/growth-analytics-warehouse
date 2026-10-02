"""raw (messy CSV) -> staging (clean tables in the DuckDB ``staging`` schema).

Every cleaning rule is a function from ``transforms.py``. Staging also materialises reference
tables (countries, plans, channels, campaigns, sources) from ``config/synthetic.yaml``.
"""
from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

from src.generate.config import ROOT

from . import transforms as T

RAW_DIR = ROOT / "data" / "raw"


def _read(raw_dir: Path, name: str) -> pd.DataFrame:
    return pd.read_csv(raw_dir / f"{name}.csv", dtype=str, keep_default_na=False)


def clean_ads(raw: pd.DataFrame) -> pd.DataFrame:
    df = T.drop_empty(raw)
    p = T.split_period(df["Reporting period"])
    out = pd.DataFrame({
        "campaign": df["Campaign name"].str.strip(),
        "channel": df["Channel"].str.strip(),
        "country": df["Country"].str.strip().str.upper(),
        "period_start": p.period_start, "period_end": p.period_end,
        "spend_eur": T.coerce_numeric(df["Amount spent (EUR)"]),
        "impressions": T.coerce_numeric(df["Impressions"]),
        "reach": T.coerce_numeric(df["Reach"]),
        "link_clicks": T.coerce_numeric(df["Link clicks"]),
        "landing_page_views": T.coerce_numeric(df["Landing page views"]),
        "signups": T.coerce_numeric(df["Subscriptions"]),
    })
    out = T.dedupe_exact(out).dropna(subset=["period_start", "period_end", "spend_eur"])
    for c in ["impressions", "reach", "link_clicks", "landing_page_views", "signups"]:
        out[c] = out[c].fillna(0).astype("int64")
    return out.sort_values(["period_start", "channel", "campaign", "country"]).reset_index(drop=True)


def clean_users(raw: pd.DataFrame) -> pd.DataFrame:
    """Consolidate accounts by normalized e-mail: earliest account wins attributes."""
    df = T.drop_empty(raw)
    df["email_norm"] = T.normalize_email(df["email"])
    df["signup_date"] = pd.to_datetime(df["signup_date"], format="%Y-%m-%d")
    df["country"] = df["country"].str.strip().str.upper()
    df = df.sort_values(["email_norm", "signup_date", "email"], kind="stable")
    n_acc = df.groupby("email_norm").size().rename("n_raw_accounts")
    first = df.groupby("email_norm", as_index=False).first()
    first = first.merge(n_acc, left_on="email_norm", right_index=True)
    first = first.rename(columns={"acquisition_source": "source", "plan": "raw_current_plan"})
    first = first.sort_values(["signup_date", "email_norm"], kind="stable").reset_index(drop=True)
    first["user_id"] = [f"U{i:06d}" for i in range(1, len(first) + 1)]
    first["email_hash"] = first.email_norm.map(T.hash_email)
    return first[["user_id", "email_norm", "email_hash", "signup_date", "country", "source",
                  "raw_current_plan", "n_raw_accounts"]]


def clean_usage(raw: pd.DataFrame, users: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    df = T.dedupe_exact(T.drop_empty(raw))
    df["email_norm"] = T.normalize_email(df["email"])
    df["usage_date"] = pd.to_datetime(df["usage_date"], format="%Y-%m-%d")
    df["assets_inserted"] = T.coerce_numeric(df["assets_inserted"]).fillna(0).astype("int64")
    df = df.merge(users[["email_norm", "user_id"]], on="email_norm", how="left")
    orphans = int(df.user_id.isna().sum())
    df = df.dropna(subset=["user_id"])
    out = T.consolidate_user_day(df, "user_id", "usage_date", "assets_inserted")
    return out, orphans


def clean_events(raw: pd.DataFrame, users: pd.DataFrame) -> pd.DataFrame:
    df = T.dedupe_exact(T.drop_empty(raw))
    df["email_norm"] = T.normalize_email(df["email"])
    df = df.merge(users[["email_norm", "user_id"]], on="email_norm", how="inner")
    out = pd.DataFrame({
        "user_id": df.user_id,
        "event_ts": pd.to_datetime(df["event_ts"], format="%Y-%m-%d %H:%M:%S"),
        "event_type": df["event_type"].str.strip().str.lower(),
        "plan_from": df["plan_from"].str.strip().str.lower() if "plan_from" in df else None,
        "plan_to": df["plan_to"].str.strip().str.lower(),
        "mrr_before_eur": T.coerce_numeric(df["mrr_before_eur"]).fillna(0.0),
        "mrr_after_eur": T.coerce_numeric(df["mrr_after_eur"]).fillna(0.0),
    })
    return out.sort_values(["event_ts", "user_id", "event_type"], kind="stable").reset_index(drop=True)


def reference_tables(cfg: dict) -> dict[str, pd.DataFrame]:
    countries = pd.DataFrame([{"country_code": k, "country_name": v["name"], "region_name": v["region"],
                               "currency": cfg["currency"], "price_index": v["price_index"]}
                              for k, v in cfg["countries"].items()])
    plans = pd.DataFrame([{"plan_name": p["name"], "tier_name": p["tier"], "list_price_eur": float(p["price"])}
                          for p in cfg["plans"]])
    channels = pd.DataFrame(cfg["channels"]).rename(columns={"name": "channel_name", "source": "source_name"})
    campaigns = pd.DataFrame([{"campaign_name": c["name"], "channel_name": c["channel"]} for c in cfg["campaigns"]])
    sources = pd.DataFrame(
        [{"source_name": c["source"], "is_paid": True, "channel_name": c["name"]} for c in cfg["channels"]]
        + [{"source_name": s, "is_paid": False, "channel_name": None}
           for s in ["organic_search", "referral", "direct"]])
    return {"stg_ref_country": countries, "stg_ref_plan": plans, "stg_ref_channel": channels,
            "stg_ref_campaign": campaigns, "stg_ref_source": sources}


def run_staging(con: duckdb.DuckDBPyConnection, cfg: dict, raw_dir: Path | None = None) -> dict:
    """Load + clean raw files and write them to ``staging``. Returns row counts for raw and staging."""
    raw_dir = Path(raw_dir or RAW_DIR)
    raw = {n: _read(raw_dir, n) for n in
           ["ad_performance_raw", "users_raw", "usage_daily_raw", "subscription_events_raw"]}
    ads = clean_ads(raw["ad_performance_raw"])
    users = clean_users(raw["users_raw"])
    usage, orphans = clean_usage(raw["usage_daily_raw"], users)
    events = clean_events(raw["subscription_events_raw"], users)

    con.execute("CREATE SCHEMA IF NOT EXISTS staging")
    tables = {"stg_ad_performance": ads, "stg_users": users, "stg_usage_daily": usage,
              "stg_subscription_events": events, **reference_tables(cfg)}
    for name, df in tables.items():
        con.register("_tmp_df", df)
        con.execute(f"CREATE OR REPLACE TABLE staging.{name} AS SELECT * FROM _tmp_df")
        con.unregister("_tmp_df")
    return {"raw": {k: len(v) for k, v in raw.items()},
            "staging": {k: len(v) for k, v in tables.items()},
            "orphan_usage_rows": orphans}
