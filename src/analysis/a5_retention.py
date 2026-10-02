"""A5. Retention: monthly churn by country, cohort retention triangle, survival curves.

SYNTHETIC data. Paid churn = cancels / paying customers at the start of the month (ratio of sums).
"""
from __future__ import annotations

import pandas as pd

from . import stats
from .common import q


def churn_by_country_month(con) -> pd.DataFrame:
    return q(con, "R06")


def churn_summary(con) -> pd.DataFrame:
    return q(con, "A04")[["country_code", "monthly_churn", "arpu", "paying_customers_now"]]


def cohort_triangle(con, metric: str = "active_retention") -> pd.DataFrame:
    t = q(con, "A11")
    p = t.pivot(index="signup_month_key", columns="months_since_signup", values=metric)
    return p


def cohort_triangle_by_country(con, country: str | None = None) -> pd.DataFrame:
    sql = "SELECT signup_month_key, months_since_signup, SUM(active_users) * 1.0 / SUM(cohort_size) AS active_retention FROM mart_retention_cohorts"
    args: list = []
    if country:
        sql += " WHERE country_code = ?"
        args.append(country)
    sql += " GROUP BY 1, 2 ORDER BY 1, 2"
    return con.execute(sql, args).df()


def survival_curves(con, kind: str = "paid") -> dict[str, pd.DataFrame]:
    """Kaplan-Meier curves per country plus 'ALL'. kind: 'paid' (subscription) or 'activity' (free usage)."""
    df = q(con, "A13" if kind == "paid" else "A14")
    ev = "cancelled" if kind == "paid" else "churned"
    out = {}
    for name, g in [("ALL", df)] + list(df.groupby("country_code")):
        t, s = stats.kaplan_meier(g.duration_days.to_numpy(), g[ev].to_numpy())
        out[name] = pd.DataFrame({"days": t, "survival": s})
    return out


def survival_table(curves: dict[str, pd.DataFrame], at_days=(30, 90, 180)) -> pd.DataFrame:
    rows = []
    for k, c in curves.items():
        rows.append({"country": k, **{f"S({d}d)": stats.survival_at(c.days.to_numpy(), c.survival.to_numpy(), d) for d in at_days}})
    return pd.DataFrame(rows)
