"""A1. Paid acquisition: funnel by country and month, BR vs MX (and others) with tests and bootstrap CIs.

SYNTHETIC data. All ratios are ratios of sums (see src/pipeline/transforms.py).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import stats
from .common import q


def by_country(con) -> pd.DataFrame:
    return q(con, "A01")


def by_country_month(con) -> pd.DataFrame:
    return q(con, "A02")


def by_channel_country(con) -> pd.DataFrame:
    return q(con, "A03")


FUNNEL_STEPS = {  # step -> (numerator column, denominator column)
    "CTR (clicks / impressions)": ("link_clicks", "impressions"),
    "Landing view rate (views / clicks)": ("landing_page_views", "link_clicks"),
    "Signup rate (signups / views)": ("signups", "landing_page_views"),
}


def compare_two(con, a: str = "BR", b: str = "MX", n_boot: int = 2000, seed: int = 7) -> pd.DataFrame:
    """Funnel steps of country ``a`` vs ``b``: two-proportion z-test plus bootstrap CI of the difference.

    The z-test treats every impression/click/view as an independent trial. Real traffic is clustered by
    campaign and day, so the bootstrap (resampling campaign x period rows) is the more honest interval.
    """
    tot = by_country(con).set_index("country_code")
    rows = q(con, "R05")
    out = []
    for step, (num, den) in FUNNEL_STEPS.items():
        t = stats.two_prop_ztest(int(tot.loc[a, num]), int(tot.loc[a, den]), int(tot.loc[b, num]), int(tot.loc[b, den]))
        ra, rb = rows[rows.country == a], rows[rows.country == b]
        key = {"link_clicks": "link_clicks", "impressions": "impressions", "landing_page_views": "landing_page_views",
               "signups": "subscriptions"}
        d, lo, hi = stats.bootstrap_ratio_diff_ci(ra[key[num]], ra[key[den]], rb[key[num]], rb[key[den]], n_boot, seed)
        out.append({"step": step, f"{a}": t["p1"], f"{b}": t["p2"], "diff": t["diff"], "z": t["z"],
                    "p_value": t["p_value"], "boot_ci_low": lo, "boot_ci_high": hi})
    # cost per signup: no sampling model for spend, so bootstrap only
    ra, rb = rows[rows.country == a], rows[rows.country == b]
    d, lo, hi = stats.bootstrap_ratio_diff_ci(ra.spend_eur, ra.subscriptions, rb.spend_eur, rb.subscriptions, n_boot, seed)
    out.append({"step": "Cost per signup (EUR)", a: tot.loc[a, "cost_per_signup"], b: tot.loc[b, "cost_per_signup"],
                "diff": d, "z": np.nan, "p_value": np.nan, "boot_ci_low": lo, "boot_ci_high": hi})
    return pd.DataFrame(out)


def pairwise_vs_reference(con, ref: str = "BR", n_boot: int = 1000, seed: int = 7) -> pd.DataFrame:
    """Reference country vs every other country on signup rate and cost per signup, Holm-adjusted p-values."""
    tot = by_country(con).set_index("country_code")
    rows = q(con, "R05")
    out = []
    for c in [c for c in tot.index if c != ref]:
        t = stats.two_prop_ztest(int(tot.loc[ref, "signups"]), int(tot.loc[ref, "landing_page_views"]),
                                 int(tot.loc[c, "signups"]), int(tot.loc[c, "landing_page_views"]))
        ra, rb = rows[rows.country == ref], rows[rows.country == c]
        d, lo, hi = stats.bootstrap_ratio_diff_ci(ra.spend_eur, ra.subscriptions, rb.spend_eur, rb.subscriptions, n_boot, seed)
        out.append({"country": c, f"signup_rate_{ref}": t["p1"], "signup_rate_other": t["p2"], "p_value": t["p_value"],
                    "cost_per_signup_diff": d, "diff_ci_low": lo, "diff_ci_high": hi})
    df = pd.DataFrame(out)
    df["p_holm"] = stats.holm(df.p_value.tolist())
    return df


def cost_per_signup_ci(con, n_boot: int = 2000, seed: int = 7) -> pd.DataFrame:
    """Bootstrap CI of cost per signup for every country (ratio of sums over campaign x period rows)."""
    rows = q(con, "R05")
    out = []
    for c, g in rows.groupby("country"):
        est, lo, hi = stats.bootstrap_ratio_ci(g.spend_eur, g.subscriptions, n_boot, seed)
        out.append({"country": c, "cost_per_signup": est, "ci_low": lo, "ci_high": hi, "rows": len(g)})
    return pd.DataFrame(out).sort_values("cost_per_signup").reset_index(drop=True)
