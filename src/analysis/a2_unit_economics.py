"""A2. Unit economics by country: cost per signup vs paid CAC (kept separate), ARPU, churn, LTV, LTV/CAC, payback.

SYNTHETIC data. LTV = ARPU x gross margin / monthly churn. Paid CAC = spend / paying customers (mature cohorts).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import stats
from .common import analysis_cfg, q


def table(con, cfg: dict | None = None) -> pd.DataFrame:
    cfg = cfg or analysis_cfg()
    ue = cfg["unit_economics"]
    df = q(con, "A04").rename(columns={"paying_customers_mature_cohorts": "paying_customers"})
    margin = ue["gross_margin"]
    df["gross_margin"] = margin
    df["ltv"] = df.arpu * margin / df.monthly_churn
    df["ltv_cac"] = df.ltv / df.paid_cac
    df["payback_months"] = df.paid_cac / (df.arpu * margin)
    ci = df.paying_customers.fillna(0).astype(int).map(stats.poisson_ci)
    # CAC uncertainty from the small number of paying customers: spend is fixed, the count is Poisson
    df["paid_cac_low"] = df.spend_mature_cohorts / ci.map(lambda t: t[1])
    df["paid_cac_high"] = df.spend_mature_cohorts / ci.map(lambda t: max(t[0], 0.5))
    df["ltv_cac_low"] = df.ltv / df.paid_cac_high
    df["ltv_cac_high"] = df.ltv / df.paid_cac_low
    df["meets_target"] = df.ltv_cac >= ue["target_ltv_cac"]
    return df.sort_values("ltv_cac", ascending=False).reset_index(drop=True)


def blended(df: pd.DataFrame, margin: float) -> dict:
    """Portfolio view: ratio of sums across countries (not a mean of country ratios)."""
    spend, cust = df.spend_mature_cohorts.sum(), df.paying_customers.sum()
    paying_now = df.paying_customers_now.fillna(0)
    arpu = float((df.arpu * paying_now).sum() / paying_now.sum())
    churn = float((df.monthly_churn * paying_now).sum() / paying_now.sum())
    cac = float(spend / cust)
    ltv = arpu * margin / churn
    return {"paid_cac": cac, "arpu": arpu, "monthly_churn": churn, "ltv": ltv, "ltv_cac": ltv / cac,
            "payback_months": cac / (arpu * margin)}


def sensitivity(df: pd.DataFrame, cfg: dict | None = None) -> pd.DataFrame:
    """LTV/CAC per country under churn and CAC multipliers (long format)."""
    cfg = cfg or analysis_cfg()
    ue = cfg["unit_economics"]
    rows = []
    for _, r in df.iterrows():
        for cm in ue["sensitivity_churn_multipliers"]:
            for am in ue["sensitivity_cac_multipliers"]:
                ltv = r.arpu * r.gross_margin / (r.monthly_churn * cm)
                rows.append({"country_code": r.country_code, "churn_x": cm, "cac_x": am,
                             "ltv_cac": ltv / (r.paid_cac * am)})
    return pd.DataFrame(rows)


def sensitivity_matrix(sens: pd.DataFrame, country: str) -> pd.DataFrame:
    s = sens[sens.country_code == country]
    return s.pivot(index="churn_x", columns="cac_x", values="ltv_cac").round(2)


def cost_vs_cac(df: pd.DataFrame) -> pd.DataFrame:
    """Side-by-side of the two different costs and their ratio (paying customers per signup)."""
    out = df[["country_code", "cost_per_signup", "paid_cac"]].copy()
    out["signups_per_paying_customer"] = out.paid_cac / out.cost_per_signup
    out["implied_signup_to_paid"] = 1 / out.signups_per_paying_customer
    return out
