"""A4. Free-tier limit simulation plus an explicit, assumption-driven monetisation layer.

SYNTHETIC data. The usage side (who is affected, how much volume) is measured from the warehouse.
The monetisation side (conversion of blocked users, activation loss, value of a retained free user)
is NOT measured: it comes from scenario assumptions in config/analysis.yaml and must be read as such.

Model for a candidate limit L and each affected free user i (usage above the limit):
  e_i      = share of the user's 30d usage that would be blocked (0..1)
  P(conv)  = conv_max * e_i           # heavier blocking -> likelier to buy
  P(loss)  = loss_prob                # any blocking creates some risk of leaving
  d MRR    = P(conv) * starter_price(country) - P(loss) * free_user_value
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .common import analysis_cfg, q


def free_day_rows(con) -> pd.DataFrame:
    """Daily insertions of currently-free users in the trailing 30 days (the simulation population)."""
    return con.execute("""
        SELECT f.user_key, l.country_code, f.assets_inserted AS assets
        FROM fact_user_daily_usage f
        JOIN dim_date d ON d.date_key = f.date_key
        JOIN mart_user_lifecycle l ON l.user_key = f.user_key
        CROSS JOIN v_as_of a
        WHERE NOT l.is_paying_now AND d.date BETWEEN a.as_of_date - 29 AND a.as_of_date""").df()


def starter_prices(con) -> pd.Series:
    df = con.execute("""SELECT c.country_code, p.list_price_eur * c.price_index AS price
                        FROM dim_country c CROSS JOIN dim_plan p WHERE p.plan_name = 'starter'""").df()
    return df.set_index("country_code").price


def simulation_grid(con) -> pd.DataFrame:
    return con.execute("SELECT * FROM mart_free_limit_simulation ORDER BY limit_type, limit_value").df()


def candidates(con) -> pd.DataFrame:
    return q(con, "A09")


def user_totals(day_rows: pd.DataFrame) -> pd.DataFrame:
    return day_rows.groupby("user_key").agg(total=("assets", "sum"), max_day=("assets", "max"),
                                            country_code=("country_code", "first")).reset_index()


def blocked_share(day_rows: pd.DataFrame, totals: pd.DataFrame, limit: float, kind: str) -> pd.DataFrame:
    """Per affected user: blocked volume and share e_i for a daily or monthly limit."""
    if kind == "daily":
        ex = (day_rows.assets - limit).clip(lower=0)
        g = day_rows.assign(ex=ex).groupby("user_key").agg(excess=("ex", "sum"), total=("assets", "sum"),
                                                         country_code=("country_code", "first")).reset_index()
    else:
        g = totals[["user_key", "total", "country_code"]].copy()
        g["excess"] = (g.total - limit).clip(lower=0)
    g = g[g.excess > 0].copy()
    g["e"] = g.excess / g.total
    return g


def monetization(day_rows, totals, prices: pd.Series, limit: float, kind: str, scen: dict) -> dict:
    """Expected incremental MRR (EUR/month) of one limit under one scenario."""
    g = blocked_share(day_rows, totals, limit, kind)
    n_all = len(totals)
    conv = (scen["conv_max"] * g.e).clip(upper=1.0)
    gain = float((conv * g.country_code.map(prices)).sum())
    loss = float(scen["loss_prob"] * len(g) * scen["free_user_value_eur"])
    return {"limit_type": kind, "limit_value": limit, "users_affected": len(g), "pct_users_affected": len(g) / n_all,
            "expected_conversions": float(conv.sum()), "expected_users_lost": float(scen["loss_prob"] * len(g)),
            "mrr_gain": gain, "mrr_loss": loss, "incremental_mrr": gain - loss,
            "excess_volume": float(g.excess.sum()), "pct_volume_excess": float(g.excess.sum() / totals.total.sum())}


def scenario_grid(con, cfg: dict | None = None) -> pd.DataFrame:
    """Expected incremental MRR over the whole limit grid for every scenario (long format)."""
    cfg = cfg or analysis_cfg()
    day_rows = free_day_rows(con)
    totals = user_totals(day_rows)
    prices = starter_prices(con)
    grid = simulation_grid(con)[["limit_type", "limit_value"]].drop_duplicates()
    rows = []
    for name, scen in cfg["limits"]["scenarios"].items():
        for kind, v in grid.itertuples(index=False):
            r = monetization(day_rows, totals, prices, v, kind, scen)
            r["scenario"] = name
            rows.append(r)
    return pd.DataFrame(rows)


def recommend(grid: pd.DataFrame, cfg: dict | None = None) -> dict:
    """Pick the limit maximising BASE-scenario incremental MRR subject to the affected-users guardrail."""
    cfg = cfg or analysis_cfg()
    cap = cfg["limits"]["guardrail_max_pct_users_affected"]
    ok = grid[grid.pct_users_affected <= cap]
    base = ok[ok.scenario == "base"].sort_values("incremental_mrr", ascending=False)
    best = base.iloc[0]
    at_best = grid[(grid.limit_type == best.limit_type) & (grid.limit_value == best.limit_value)].set_index("scenario")
    optima = {}
    for s in grid.scenario.unique():
        top = ok[ok.scenario == s].sort_values("incremental_mrr", ascending=False).iloc[0]
        optima[s] = {"limit_type": top.limit_type, "limit_value": float(top.limit_value), "incremental_mrr": float(top.incremental_mrr)}
    return {"limit_type": best.limit_type, "limit_value": float(best.limit_value),
            "pct_users_affected": float(best.pct_users_affected),
            "incremental_mrr_by_scenario": {s: float(at_best.loc[s, "incremental_mrr"]) for s in at_best.index},
            "scenario_optima": optima, "guardrail": cap,
            "robust_positive": bool((at_best.incremental_mrr > 0).all()),
            "note": "Usage effects are measured; conversion, loss and user value are scenario assumptions."}
