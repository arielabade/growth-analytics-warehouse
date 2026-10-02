"""Monitoring page: KPI tracking over time with targets and status colours (filters: country, period)."""
import dash
import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, callback, dcc, html

from app import components as ui
from app import data
from app import theme as T
from src.analysis import charts as C

dash.register_page(__name__, path="/kpis", name="KPI tracking", order=6, group="Monitoring")

TG = data.cfg()["kpi_targets"]

layout = html.Div([
    ui.head("Monitoring · KPIs", "Are we on target, month after month?",
            "Status colours compare the latest month with the targets in config/analysis.yaml: green = on target, amber = within 25% (or LTV/CAC >= 2x), red = off target. "
            "LTV/CAC is a rolling 6-month figure. Filters: country and period."),
    html.Div(id="kpi-cards"),
    html.Div(id="kpi-charts"),
])


def _line(k: pd.DataFrame, col: str, title: str, color=T.COBALT, target=None, fmt=None, bar=False) -> dcc.Graph:
    f = C._fig(title, 300)
    if bar:
        f.add_trace(go.Bar(x=k.month_start, y=k[col], marker_color=T.STEEL_TINT))
    else:
        f.add_trace(go.Scatter(x=k.month_start, y=k[col], mode="lines+markers", line=dict(color=color, width=3)))
    if target is not None:
        f.add_hline(y=target, line_dash="dash", line_color=T.GRAPHITE, annotation_text=f"target {fmt(target) if fmt else target}")
    if fmt and "%" in fmt(0.5):
        f.update_layout(yaxis_tickformat=".0%")
    f.update_layout(showlegend=False, yaxis_rangemode="tozero")
    return dcc.Graph(figure=f, config={"displaylogo": False}, style={"flex": "1 1 440px", "minWidth": "320px"})


def _card(label, value, prev, status, fmt, sub=""):
    delta = "" if prev is None or pd.isna(prev) or prev == 0 or pd.isna(value) else f"{(value / prev - 1):+.1%} vs previous month"
    return ui.kpi(label, "n/a" if pd.isna(value) else fmt(value), (sub + " " + delta).strip(), status if not pd.isna(value) else None)


@callback(Output("kpi-cards", "children"), Output("kpi-charts", "children"),
          Input("f-country", "value"), Input("f-dates", "start_date"), Input("f-dates", "end_date"))
def update(countries, start, end):
    k = data.kpi_monthly(countries)
    k = k[k.month_start.between(pd.Timestamp(start or "1900-01-01"), pd.Timestamp(end or "2999-01-01"))]
    if len(k) < 2:
        return ui.kpis(), html.P("Select a period with at least two months.", className="note")
    last, prev = k.iloc[-1], k.iloc[-2]
    cps_t, churn_t = TG["cost_per_signup_max_eur"], TG["logo_churn_max"]
    st_cps = T.status_for(last.cost_per_signup, cps_t, cps_t * 1.25, higher_is_better=False)
    st_ch = T.status_for(last.churn, churn_t, churn_t * 1.25, higher_is_better=False)
    st_lc = T.status_for(last.ltv_cac, TG["ltv_cac"]["ok"], TG["ltv_cac"]["warn"])
    eur, pct = (lambda v: f"EUR {v:,.0f}"), (lambda v: f"{v:.1%}")
    cards = ui.kpis(
        _card("Spend", last.spend_eur, prev.spend_eur, None, eur, last.month_start.strftime("%Y-%m")),
        _card("Signups", last.signups, prev.signups, None, lambda v: f"{int(v):,}"),
        _card("Cost per signup", last.cost_per_signup, prev.cost_per_signup, st_cps, lambda v: f"EUR {v:.2f}", f"target ≤ {cps_t:.0f}"),
        _card("Paid CAC (latest mature cohort)", k.paid_cac.dropna().iloc[-1] if k.paid_cac.notna().any() else float("nan"),
              k.paid_cac.dropna().iloc[-2] if k.paid_cac.notna().sum() > 1 else None, None, eur, "cohorts need 90d to mature"),
        _card("LTV / CAC (6m)", last.ltv_cac, prev.ltv_cac, st_lc, lambda v: f"{v:.2f}x", f"target ≥ {TG['ltv_cac']['ok']:.0f}x"),
        _card("Paid logo churn", last.churn, prev.churn, st_ch, pct, f"target ≤ {churn_t:.0%}"),
        _card("Monthly active users", last.mau, prev.mau, None, lambda v: f"{int(v):,}"),
        _card("MRR", last.mrr_end, prev.mrr_end, None, eur))
    charts = html.Div([
        _line(k, "spend_eur", "Spend (EUR)", bar=True), _line(k, "signups", "Signups", bar=True),
        _line(k, "cost_per_signup", "Cost per signup (EUR)", target=cps_t, fmt=lambda v: f"{v:g}"),
        _line(k, "paid_cac", "Paid CAC, mature cohorts (EUR)"),
        _line(k, "ltv_cac", "LTV / CAC, rolling 6 months", target=TG["ltv_cac"]["ok"], fmt=lambda v: f"{v:g}x"),
        _line(k, "churn", "Paid logo churn", target=churn_t, fmt=lambda v: f"{v:.0%}"),
        _line(k, "mau", "Monthly active users"), _line(k, "mrr_end", "MRR (EUR)"),
    ], style={"display": "flex", "flexWrap": "wrap", "gap": "12px"})
    return cards, charts
