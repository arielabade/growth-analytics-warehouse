"""Data access for the dashboard: a read-only DuckDB connection plus cached, in-memory working sets.

On first start, if the warehouse file is missing the whole (SYNTHETIC) platform is built; this is safe because
nothing here is real data.
"""
from __future__ import annotations

import threading
from functools import lru_cache

import duckdb
import pandas as pd

from src.analysis import a3_concentration as a3
from src.analysis import a4_limits as a4
from src.analysis.common import analysis_cfg, load_result
from src.pipeline.run import DB_PATH
from src.pipeline.transforms import funnel_ratios

_lock = threading.Lock()
_con: duckdb.DuckDBPyConnection | None = None


def ensure_db() -> None:
    global _con
    with _lock:
        if _con is not None:
            return
        if not DB_PATH.exists():
            from src.build import build

            build(images=False)
        _con = duckdb.connect(str(DB_PATH), read_only=True)


def cur() -> duckdb.DuckDBPyConnection:
    ensure_db()
    return _con.cursor()  # type: ignore[union-attr]


def df(sql: str, params: list | None = None) -> pd.DataFrame:
    return cur().execute(sql, params or []).df()


@lru_cache(maxsize=None)
def cfg() -> dict:
    return analysis_cfg()


@lru_cache(maxsize=None)
def bounds() -> dict:
    r = df("SELECT (SELECT as_of_date FROM v_as_of) AS as_of, MIN(month_start) AS first_month FROM mart_funnel_country").iloc[0]
    return {"as_of": pd.Timestamp(r.as_of), "first_month": pd.Timestamp(r.first_month)}


@lru_cache(maxsize=None)
def countries() -> list[str]:
    return df("SELECT country_code FROM dim_country ORDER BY country_code").country_code.tolist()


@lru_cache(maxsize=None)
def ad_rows() -> pd.DataFrame:
    """Campaign x country x month rows (reconstructed export R05) with month_start."""
    from src.pipeline.sqlio import run_query

    d = run_query(cur(), "R05")
    d["month_start"] = pd.to_datetime(d.reporting_period.str[:10])
    return d.rename(columns={"subscriptions": "signups", "link_clicks": "link_clicks"})


def filter_ads(countries_sel, start, end) -> pd.DataFrame:
    d = ad_rows()
    d = d[d.month_start.between(pd.Timestamp(start), pd.Timestamp(end))]
    return d[d.country.isin(countries_sel)] if countries_sel else d


def ratios_by(d: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    cols = ["spend_eur", "impressions", "reach", "link_clicks", "landing_page_views", "signups"]
    return funnel_ratios(d.groupby(by, as_index=False)[cols].sum())


@lru_cache(maxsize=None)
def usage_users(window: int) -> pd.DataFrame:
    return a3.user_level(cur(), window)


def pareto_from_users(u: pd.DataFrame) -> pd.DataFrame:
    """Recompute rank and cumulative shares on a filtered population (filtering changes the Pareto)."""
    u = u.sort_values(["total_assets", "user_key"], ascending=[False, True]).reset_index(drop=True).copy()
    u["volume_rank"] = u.index + 1
    u["cum_share_users"] = u.volume_rank / len(u)
    u["cum_share_assets"] = u.total_assets.cumsum() / u.total_assets.sum()
    return u


@lru_cache(maxsize=None)
def limit_tables() -> dict:
    """Pre-aggregate, per limit and country, everything the live simulator needs, so slider moves are instant."""
    con = cur()
    day = a4.free_day_rows(con)
    totals = a4.user_totals(day)
    prices = a4.starter_prices(con)
    grid = a4.simulation_grid(con)[["limit_type", "limit_value"]].drop_duplicates()
    rows = []
    for kind, v in grid.itertuples(index=False):
        g = a4.blocked_share(day, totals, v, kind)
        g["e_price"] = g.e * g.country_code.map(prices)
        a = g.groupby("country_code").agg(users_affected=("e", "size"), sum_e_price=("e_price", "sum"), excess=("excess", "sum")).reset_index()
        a.insert(0, "limit_value", v)
        a.insert(0, "limit_type", kind)
        rows.append(a)
    pop = totals.groupby("country_code").agg(users=("user_key", "size"), volume=("total", "sum")).reset_index()
    return {"agg": pd.concat(rows, ignore_index=True), "pop": pop, "grid": grid}


def simulate_limits(kind: str, countries_sel: list[str] | None, conv_max: float, loss_prob: float, value: float) -> pd.DataFrame:
    t = limit_tables()
    a = t["agg"][t["agg"].limit_type == kind]
    pop = t["pop"]
    if countries_sel:
        a, pop = a[a.country_code.isin(countries_sel)], pop[pop.country_code.isin(countries_sel)]
    g = a.groupby("limit_value", as_index=False).agg(users_affected=("users_affected", "sum"), sum_e_price=("sum_e_price", "sum"), excess=("excess", "sum"))
    g["pct_users_affected"] = g.users_affected / pop.users.sum()
    g["pct_volume_excess"] = g.excess / pop.volume.sum()
    g["expected_conversions"] = None
    g["mrr_gain"] = conv_max * g.sum_e_price
    g["mrr_loss"] = loss_prob * g.users_affected * value
    g["incremental_mrr"] = g.mrr_gain - g.mrr_loss
    g["expected_users_lost"] = loss_prob * g.users_affected
    return g.drop(columns="expected_conversions")


def model_results() -> dict | None:
    return load_result(cur(), "propensity")


def headline() -> dict | None:
    return load_result(cur(), "headline")


# ---- cached analysis frames for the retention / unit-economics and monitoring pages -------------------
@lru_cache(maxsize=None)
def unit_economics() -> pd.DataFrame:
    from src.analysis import a2_unit_economics as a2

    return a2.table(cur(), cfg())


@lru_cache(maxsize=None)
def sensitivity() -> pd.DataFrame:
    from src.analysis import a2_unit_economics as a2

    return a2.sensitivity(unit_economics(), cfg())


@lru_cache(maxsize=None)
def survival(kind: str):
    from src.analysis import a5_retention as a5

    return a5.survival_curves(cur(), kind)


@lru_cache(maxsize=None)
def churn_series() -> pd.DataFrame:
    from src.analysis import a5_retention as a5

    return a5.churn_by_country_month(cur())


def triangle(countries_sel: list[str] | None) -> pd.DataFrame:
    sql = ("SELECT signup_month_key, months_since_signup, SUM(active_users) * 1.0 / SUM(cohort_size) AS v "
           "FROM mart_retention_cohorts WHERE country_code IN (SELECT unnest(?::VARCHAR[])) GROUP BY 1, 2")
    d = df(sql, [countries_sel or countries()])
    return d.pivot(index="signup_month_key", columns="months_since_signup", values="v")


def kpi_monthly(countries_sel: list[str] | None) -> pd.DataFrame:
    cs = countries_sel or countries()
    ue = df("""SELECT month_key, month_start, SUM(spend_eur) spend_eur, SUM(ad_signups) signups, SUM(new_users) new_users,
                      SUM(spend_eur) FILTER (WHERE is_mature_90d) spend_mature,
                      SUM(paid_source_customers_90d) FILTER (WHERE is_mature_90d) cust_mature,
                      SUM(paying_end) paying_end, SUM(mrr_end) mrr_end, SUM(cancels) cancels, SUM(paying_start) paying_start
               FROM mart_unit_economics_country_month WHERE country_code IN (SELECT unnest(?::VARCHAR[]))
               GROUP BY 1, 2 ORDER BY 1""", [cs])
    mau = df("""SELECT d.month_key, COUNT(DISTINCT f.user_key) AS mau
                FROM fact_user_daily_usage f JOIN dim_date d ON d.date_key = f.date_key
                JOIN dim_user u ON u.user_key = f.user_key JOIN dim_country c ON c.country_key = u.country_key
                WHERE c.country_code IN (SELECT unnest(?::VARCHAR[])) GROUP BY 1""", [cs])
    k = ue.merge(mau, on="month_key", how="left")
    k["cost_per_signup"] = k.spend_eur / k.signups.replace(0, float("nan"))
    k["paid_cac"] = k.spend_mature / k.cust_mature.replace(0, float("nan"))
    k["churn"] = k.cancels / k.paying_start.replace(0, float("nan"))
    r = k[["spend_mature", "cust_mature", "mrr_end", "paying_end", "cancels", "paying_start"]].fillna(0).rolling(6, min_periods=6).sum()
    margin = cfg()["unit_economics"]["gross_margin"]
    arpu, churn, cac = r.mrr_end / r.paying_end, r.cancels / r.paying_start, r.spend_mature / r.cust_mature
    k["ltv_cac"] = (arpu * margin / churn) / cac
    return k
