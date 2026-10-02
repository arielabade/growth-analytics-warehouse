"""Plotly figures shared by the notebook, the exported README images and the Dash app.

Every figure uses the ABADE template from ``app/theme.py`` (Ivory background, Carbon text, Cobalt accent on
the series that answers the question, Lato). Data is SYNTHETIC.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from app import theme as T

T.register_template()
NEUTRAL = T.STEEL_TINT


def _fig(title: str, height: int = 380, **kw) -> go.Figure:
    f = go.Figure()
    f.update_layout(template="abade", title_text=title, height=height, **kw)
    return f


# ---- A1 acquisition ------------------------------------------------------------------------
def cost_per_signup_ci(ci: pd.DataFrame, focus: tuple[str, ...] = ("BR", "MX")) -> go.Figure:
    f = _fig("Cost per signup by country, with 95% bootstrap CI (EUR)")
    colors = [T.COBALT if c in focus else T.STEEL for c in ci.country]
    f.add_trace(go.Scatter(x=ci.country, y=ci.cost_per_signup, mode="markers", marker=dict(size=11, color=colors),
                           error_y=dict(type="data", symmetric=False, array=ci.ci_high - ci.cost_per_signup,
                                        arrayminus=ci.cost_per_signup - ci.ci_low, color=T.GRAPHITE, thickness=1.4),
                           hovertemplate="%{x}: EUR %{y:.2f}<extra></extra>"))
    f.update_yaxes(title="EUR per signup", rangemode="tozero")
    return f


def funnel_rates(by_country: pd.DataFrame, focus: tuple[str, ...] = ("BR", "MX")) -> go.Figure:
    f = _fig("Funnel step conversion by country (ratio of sums)", height=400)
    for col, name in [("ctr", "CTR"), ("lpv_rate", "Landing view rate"), ("signup_rate", "Signup rate")]:
        f.add_trace(go.Bar(name=name, x=by_country.country_code, y=by_country[col],
                           marker_color={"ctr": T.COBALT, "lpv_rate": T.GRAPHITE, "signup_rate": T.AURUM}[col]))
    f.update_layout(barmode="group", yaxis_tickformat=".0%")
    return f


def spend_monthly(monthly: pd.DataFrame, countries: list[str] | None = None) -> go.Figure:
    f = _fig("Monthly spend and cost per signup", height=400)
    m = monthly if not countries else monthly[monthly.country_code.isin(countries)]
    g = m.groupby("month_start", as_index=False).agg(spend=("spend_eur", "sum"), signups=("signups", "sum"))
    g["cps"] = g.spend / g.signups
    f.add_trace(go.Bar(x=g.month_start, y=g.spend, name="Spend (EUR)", marker_color=T.STEEL_TINT))
    f.add_trace(go.Scatter(x=g.month_start, y=g.cps, name="Cost per signup (EUR)", yaxis="y2",
                           line=dict(color=T.COBALT, width=3)))
    f.update_layout(yaxis=dict(title="Spend (EUR)"), yaxis2=dict(title="EUR per signup", overlaying="y", side="right",
                                                                 showgrid=False, rangemode="tozero"),
                    legend=dict(orientation="h", y=1.12))
    return f


# ---- A2 unit economics ---------------------------------------------------------------------
def ltv_cac(ue: pd.DataFrame, target: float = 3.0) -> go.Figure:
    f = _fig("LTV / paid CAC by country (error bars: Poisson CI on paying-customer count)")
    colors = [T.COBALT if v >= target else T.STEEL for v in ue.ltv_cac]
    f.add_trace(go.Bar(x=ue.country_code, y=ue.ltv_cac, marker_color=colors,
                       error_y=dict(type="data", symmetric=False, array=ue.ltv_cac_high - ue.ltv_cac,
                                    arrayminus=ue.ltv_cac - ue.ltv_cac_low, color=T.GRAPHITE),
                       hovertemplate="%{x}: %{y:.2f}x<extra></extra>"))
    f.add_hline(y=target, line_dash="dash", line_color=T.GRAPHITE, annotation_text=f"{target:.0f}x threshold")
    f.update_yaxes(title="LTV / CAC")
    return f


def cost_vs_cac(cv: pd.DataFrame) -> go.Figure:
    f = _fig("Cost per signup is not CAC: price of a free account vs a paying customer (EUR)")
    f.add_trace(go.Bar(name="Cost per signup", x=cv.country_code, y=cv.cost_per_signup, marker_color=T.STEEL))
    f.add_trace(go.Bar(name="Paid CAC", x=cv.country_code, y=cv.paid_cac, marker_color=T.COBALT))
    f.update_layout(barmode="group", yaxis_title="EUR")
    return f


def sensitivity_heatmap(matrix: pd.DataFrame, country: str) -> go.Figure:
    f = _fig(f"{country}: LTV/CAC sensitivity to churn and CAC", height=320)
    f.add_trace(go.Heatmap(z=matrix.values, x=[f"CAC x{c}" for c in matrix.columns], y=[f"churn x{r}" for r in matrix.index],
                           text=matrix.values, texttemplate="%{text:.2f}", colorscale=[[0, T.IVORY], [1, T.COBALT]],
                           showscale=False))
    return f


# ---- A3 usage ----------------------------------------------------------------------------------
def lorenz(points: dict[int, pd.DataFrame]) -> go.Figure:
    f = _fig("Usage concentration: cumulative share of volume by share of users (heaviest first)", height=420)
    f.add_trace(go.Scatter(x=[0, 1], y=[0, 1], mode="lines", line=dict(color=T.STEEL, dash="dot"), name="Equal usage"))
    for w, color in zip(sorted(points), [T.COBALT, T.GRAPHITE]):
        p = points[w]
        f.add_trace(go.Scatter(x=p.cum_share_users, y=p.cum_share_assets, mode="lines", name=f"{w}d window",
                               line=dict(color=color, width=3)))
    f.add_hline(y=0.8, line_dash="dash", line_color=T.AURUM_DARK, annotation_text="80% of volume")
    f.update_layout(xaxis_tickformat=".0%", yaxis_tickformat=".0%", xaxis_title="Share of active users",
                    yaxis_title="Share of inserted assets")
    return f


def quartile_volume(q: pd.DataFrame, window: int = 30) -> go.Figure:
    d = q[q.window_days == window]
    f = _fig(f"Share of volume by usage quartile ({window}d); Q4 = heaviest 25% of users")
    f.add_trace(go.Bar(x=[f"Q{i}" for i in d.usage_quartile], y=d.share_of_volume,
                       marker_color=[T.STEEL_TINT, T.STEEL_TINT, T.STEEL, T.COBALT], text=d.share_of_volume.map("{:.0%}".format),
                       textposition="outside"))
    f.update_yaxes(tickformat=".0%", range=[0, 1])
    return f


def histogram(h: dict, title: str = "Free users: 30-day-normalised volume (Freedman-Diaconis bins, clipped at P99)") -> go.Figure:
    f = _fig(title)
    centers = (h["edges"][:-1] + h["edges"][1:]) / 2
    f.add_trace(go.Bar(x=centers, y=h["counts"], marker_color=T.COBALT, width=h["bin_width"] * 0.95))
    f.update_layout(xaxis_title="Assets per 30 days", yaxis_title="Users")
    return f


def active_day_bands(b: pd.DataFrame, window: int = 90) -> go.Figure:
    d = b[b.window_days == window]
    f = _fig(f"Users and volume by days active ({window}d window)")
    f.add_trace(go.Bar(name="Share of users", x=d.band, y=d.share_of_users, marker_color=T.STEEL))
    f.add_trace(go.Bar(name="Share of volume", x=d.band, y=d.share_of_volume, marker_color=T.COBALT))
    f.update_layout(barmode="group", yaxis_tickformat=".0%", xaxis_title="Active days in window")
    return f


# ---- A4 limits -------------------------------------------------------------------------------------
def limit_curves(grid: pd.DataFrame, kind: str) -> go.Figure:
    d = grid[grid.limit_type == kind]
    f = _fig(f"{kind.title()} limit: share of active free users affected and share of volume above the limit")
    f.add_trace(go.Scatter(x=d.limit_value, y=d.pct_users_affected, name="Users affected", mode="lines+markers",
                           line=dict(color=T.COBALT, width=3)))
    f.add_trace(go.Scatter(x=d.limit_value, y=d.pct_volume_excess, name="Volume above limit", mode="lines+markers",
                           line=dict(color=T.GRAPHITE, width=2, dash="dot")))
    f.update_layout(xaxis_type="log", xaxis_title=f"{kind} limit (assets)", yaxis_tickformat=".0%", legend=dict(orientation="h", y=1.12))
    return f


def mrr_scenarios(sg: pd.DataFrame, kind: str, guardrail: float | None = None, recommended: float | None = None) -> go.Figure:
    d = sg[sg.limit_type == kind]
    f = _fig(f"Expected incremental MRR by {kind} limit and scenario (ASSUMPTION-DRIVEN, EUR/month)", height=420)
    colors = {"low": T.STEEL, "base": T.COBALT, "high": T.GRAPHITE}
    for s in ["low", "base", "high"]:
        x = d[d.scenario == s].sort_values("limit_value")
        f.add_trace(go.Scatter(x=x.limit_value, y=x.incremental_mrr, name=s, mode="lines+markers",
                               line=dict(color=colors[s], width=3 if s == "base" else 2)))
    f.add_hline(y=0, line_color=T.STEEL)
    if recommended:  # drawn by hand: add_vline misbehaves on log axes
        f.add_shape(type="line", x0=recommended, x1=recommended, y0=0, y1=1, yref="paper",
                    line=dict(color=T.AURUM_DARK, dash="dash", width=2))
        f.add_annotation(x=float(np.log10(recommended)), y=1, yref="paper", text="recommended", showarrow=False,
                         xanchor="left", yanchor="bottom", font=dict(color=T.AURUM_DARK))
    f.update_layout(xaxis_type="log", xaxis_title=f"{kind} limit (assets)", yaxis_title="EUR / month")
    return f


# ---- A5 retention ----------------------------------------------------------------------------------
def triangle(p: pd.DataFrame, title: str = "Cohort active-user retention by months since signup") -> go.Figure:
    f = _fig(title, height=480)
    f.add_trace(go.Heatmap(z=p.values, x=list(p.columns), y=[f"{str(int(k))[:4]}-{str(int(k))[4:]}" for k in p.index],
                           colorscale=[[0, T.IVORY], [1, T.COBALT]], zmin=0, zmax=1, colorbar=dict(tickformat=".0%"),
                           hovertemplate="cohort %{y}, month %{x}: %{z:.1%}<extra></extra>"))
    f.update_layout(xaxis_title="Months since signup", yaxis=dict(autorange="reversed", type="category"),
                    margin=dict(l=84, r=24, t=56, b=48))
    return f


def survival(curves: dict[str, pd.DataFrame], title: str, highlight: tuple[str, ...] = ("ALL",)) -> go.Figure:
    f = _fig(title, height=420)
    for k, c in curves.items():
        hl = k in highlight
        f.add_trace(go.Scatter(x=c.days, y=c.survival, mode="lines", name=k, line_shape="hv",
                               line=dict(color=T.COBALT if hl else None, width=4 if hl else 1.6)))
    f.update_layout(xaxis_title="Days", yaxis_title="Survival", yaxis_tickformat=".0%", yaxis_range=[0, 1.02])
    return f


def churn_by_country(churn: pd.DataFrame) -> go.Figure:
    f = _fig("Monthly paid churn by country (cancels / paying customers at start of month)")
    for c, g in churn.groupby("country_code"):
        f.add_trace(go.Scatter(x=g.month_label, y=g.churn_rate, name=c, mode="lines"))
    f.update_layout(yaxis_tickformat=".0%")
    return f


# ---- A6 model ----------------------------------------------------------------------------------------
def lift(lt: pd.DataFrame) -> go.Figure:
    f = _fig("Hold-out lift by score decile (10 = highest propensity)")
    f.add_trace(go.Bar(x=lt.decile, y=lt.lift, marker_color=[T.COBALT if d >= 9 else T.STEEL_TINT for d in lt.decile]))
    f.add_hline(y=1, line_color=T.GRAPHITE, line_dash="dash", annotation_text="base rate")
    f.update_layout(xaxis=dict(title="Score decile", dtick=1), yaxis_title="Lift vs base rate")
    return f


def calibration(cal: pd.DataFrame, raw: pd.DataFrame | None = None) -> go.Figure:
    f = _fig("Calibration on the hold-out: predicted vs observed conversion rate (log axes)", height=400)
    mx = max(cal.mean_predicted.max(), cal.observed_rate.max()) * 1.1
    f.add_trace(go.Scatter(x=[1e-4, mx], y=[1e-4, mx], mode="lines", line=dict(color=T.STEEL, dash="dot"), name="Perfect"))
    if raw is not None:
        f.add_trace(go.Scatter(x=raw.mean_predicted, y=raw.observed_rate, mode="markers", name="Uncalibrated GB",
                               marker=dict(color=T.STEEL, size=8)))
    f.add_trace(go.Scatter(x=cal.mean_predicted, y=cal.observed_rate, mode="lines+markers", name="Selected model",
                           line=dict(color=T.COBALT, width=3)))
    f.update_layout(xaxis=dict(type="log", title="Mean predicted"), yaxis=dict(type="log", title="Observed rate"))
    return f


def profit(pc: pd.DataFrame, threshold: float) -> go.Figure:
    f = _fig("Expected profit by contact threshold (hold-out, EUR); threshold chosen on the validation fold")
    f.add_trace(go.Scatter(x=pc.contacted, y=pc.profit_eur, mode="lines", line=dict(color=T.COBALT, width=3)))
    f.add_hline(y=0, line_color=T.STEEL)
    f.update_layout(xaxis_title="Users contacted", yaxis_title="Expected profit (EUR)")
    return f


def importance(imp: pd.DataFrame) -> go.Figure:
    d = imp.sort_values("pr_auc_drop")
    f = _fig("Permutation importance (drop in PR-AUC on hold-out)", height=380)
    f.add_trace(go.Bar(x=d.pr_auc_drop, y=d.feature, orientation="h", marker_color=T.COBALT))
    return f
