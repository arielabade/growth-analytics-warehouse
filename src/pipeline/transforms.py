"""Pure, unit-tested transformations used by the staging layer (all data here is SYNTHETIC).

Design rules enforced in this module:
* time windows are relative to an explicit ``as_of`` date, never ``datetime.now()``;
* ratios are recomputed from SUMS of numerators and denominators, never averaged row by row.
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

_PERIOD_RE = r"^\s*(\d{4}-\d{2}-\d{2})\s*-\s*(\d{4}-\d{2}-\d{2})\s*$"


def split_period(s: pd.Series) -> pd.DataFrame:
    """Split ``"YYYY-MM-DD - YYYY-MM-DD"`` into ``period_start`` / ``period_end`` datetimes."""
    parts = s.astype("string").str.extract(_PERIOD_RE)
    return pd.DataFrame({
        "period_start": pd.to_datetime(parts[0], format="%Y-%m-%d", errors="coerce"),
        "period_end": pd.to_datetime(parts[1], format="%Y-%m-%d", errors="coerce"),
    }, index=s.index)


def normalize_email(s: pd.Series) -> pd.Series:
    """Lowercase, trim and strip the ``+alias`` part of the local name (``Ab+x@Example.test`` -> ``ab@example.test``)."""
    s = s.astype("string").str.strip().str.lower()
    return s.str.replace(r"\+[^@]*(?=@)", "", regex=True)


def coerce_numeric(s: pd.Series) -> pd.Series:
    """Parse numbers stored as strings. A comma means decimal comma (``"1.234,5"`` -> 1234.5)."""
    t = s.astype("string").str.strip()
    has_comma = t.str.contains(",", regex=False, na=False)
    t = t.mask(has_comma, t.str.replace(".", "", regex=False).str.replace(",", ".", regex=False))
    return pd.to_numeric(t, errors="coerce")


def drop_empty(df: pd.DataFrame) -> pd.DataFrame:
    """Blank strings -> NA, then drop all-NA rows and all-NA (e.g. trailing blank) columns."""
    out = df.copy()
    for col in out.columns:
        if out[col].dtype == object or pd.api.types.is_string_dtype(out[col]):
            out[col] = out[col].astype("string").str.strip().replace("", pd.NA)
    out = out.loc[:, ~out.isna().all(axis=0)]
    return out.dropna(how="all").reset_index(drop=True)


def dedupe_exact(df: pd.DataFrame) -> pd.DataFrame:
    """Drop rows identical in every column (re-exported duplicates)."""
    return df.drop_duplicates().reset_index(drop=True)


def consolidate_user_day(df: pd.DataFrame, user: str, day: str, value: str) -> pd.DataFrame:
    """One row per user/day: sum the value (several accounts of one person collapse after e-mail normalization)."""
    return df.groupby([user, day], as_index=False, sort=True)[value].sum()


def window_bounds(as_of: str | pd.Timestamp, days: int) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Inclusive ``[start, end]`` of a trailing window of ``days`` days ending on ``as_of``."""
    end = pd.Timestamp(as_of).normalize()
    return end - pd.Timedelta(days=days - 1), end


def in_window(dates: pd.Series, as_of: str | pd.Timestamp, days: int) -> pd.Series:
    start, end = window_bounds(as_of, days)
    d = pd.to_datetime(dates)
    return (d >= start) & (d <= end)


def normalize_to_monthly(total, window_days: int, days_per_month: float = 30.0):
    """Scale a window total (e.g. 90d) to a 30-day-month equivalent."""
    return total * days_per_month / window_days


def filter_cohort(df: pd.DataFrame, signup_col: str, from_year: int) -> pd.DataFrame:
    """Keep users whose signup year is ``from_year`` or later."""
    return df[pd.to_datetime(df[signup_col]).dt.year >= from_year].copy()


def safe_div(num, den):
    num = np.asarray(num, dtype="float64")
    den = np.asarray(den, dtype="float64")
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(den > 0, num / den, np.nan)


def funnel_ratios(sums: pd.DataFrame) -> pd.DataFrame:
    """Add funnel ratios computed from SUMMED numerators/denominators.

    Expects columns spend_eur, impressions, reach, link_clicks, landing_page_views, signups
    (already summed to the desired grain). Averaging row-level ratios would weight a 100-impression
    row like a 10-million-impression row; ratio-of-sums weights every impression equally.
    Note: ``frequency`` = impressions / reach is an approximation once reach is summed across
    campaigns/periods (unique reach is not additive).
    """
    out = sums.copy()
    out["ctr"] = safe_div(out.link_clicks, out.impressions)
    out["cpc"] = safe_div(out.spend_eur, out.link_clicks)
    out["cpm"] = safe_div(out.spend_eur, out.impressions) * 1000
    out["lpv_rate"] = safe_div(out.landing_page_views, out.link_clicks)
    out["signup_rate"] = safe_div(out.signups, out.landing_page_views)
    out["cost_per_signup"] = safe_div(out.spend_eur, out.signups)
    out["frequency"] = safe_div(out.impressions, out.reach)
    return out


def sum_then_ratio(df: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    """Group, SUM the additive columns, then compute ratios (the correct order)."""
    cols = ["spend_eur", "impressions", "reach", "link_clicks", "landing_page_views", "signups"]
    return funnel_ratios(df.groupby(by, as_index=False)[cols].sum())


def hash_email(email_norm: str) -> str:
    """Stable pseudonymous key; warehouse tables never store addresses."""
    import hashlib

    return hashlib.sha256(email_norm.encode("utf-8")).hexdigest()[:16]


def looks_like_email(s: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", s))
