"""A3. Usage concentration: Pareto cutoffs, quartiles, IQR long tail, active-day bands, windows, cohorts.

SYNTHETIC data. Windows are relative to the warehouse as_of_date (30d and 90d); 90d totals can be
normalised to a 30-day month with ``monthly_assets``.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import stats
from .common import q


def pareto_cutoffs(con) -> pd.DataFrame:
    return q(con, "A05")


def quartiles(con) -> pd.DataFrame:
    return q(con, "A06")


def distribution(con) -> pd.DataFrame:
    return q(con, "A07")


def active_day_bands(con) -> pd.DataFrame:
    return q(con, "A08")


def by_country_cohort(con) -> pd.DataFrame:
    return q(con, "A10")


def user_level(con, window_days: int, free_only: bool = False) -> pd.DataFrame:
    where = "WHERE window_days = ?" + (" AND NOT is_paying_now" if free_only else "")
    return con.execute(f"SELECT * FROM mart_usage_pareto {where}", [window_days]).df()


def lorenz_points(users: pd.DataFrame, n: int = 200) -> pd.DataFrame:
    """Downsampled cumulative curve (share of users vs share of volume, heaviest first)."""
    u = users.sort_values("volume_rank")
    idx = np.unique(np.linspace(0, len(u) - 1, n).astype(int))
    return u.iloc[idx][["cum_share_users", "cum_share_assets"]].reset_index(drop=True)


def monthly_histogram(users: pd.DataFrame) -> dict:
    """Freedman-Diaconis histogram of 30-day-normalised volume (clipped at P99 for readability)."""
    x = users.monthly_assets.to_numpy()
    cap = np.quantile(x, 0.99)
    width, nbins = stats.freedman_diaconis_bins(x[x <= cap])
    counts, edges = np.histogram(x[x <= cap], bins=max(nbins, 1))
    return {"bin_width": width, "bins": nbins, "counts": counts, "edges": edges, "cap_p99": float(cap),
            "users_above_cap": int((x > cap).sum())}


def summary(con) -> dict:
    """Headline numbers used by the README and docs."""
    pc = pareto_cutoffs(con)
    d = distribution(con)
    out = {}
    for w in (30, 90):
        r80 = pc[(pc.window_days == w) & (pc.cutoff.round(2) == 0.8)].iloc[0]
        r50 = pc[(pc.window_days == w) & (pc.cutoff.round(2) == 0.5)].iloc[0]
        dd = d[(d.window_days == w) & (d.country_code == "ALL")].iloc[0]
        out[w] = {"active_users": int(r80.active_users), "pct_users_for_80pct": float(r80.pct_users_needed),
                  "pct_users_for_50pct": float(r50.pct_users_needed), "median": float(dd["median"]), "q3": float(dd.q3),
                  "p95": float(dd.p95), "iqr": float(dd.iqr), "upper_fence": float(dd.upper_fence),
                  "volume_share_beyond_fence": float(dd.volume_share_beyond_fence)}
    return out
