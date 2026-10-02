"""Analysis page: usage concentration (filters: country, plan)."""
import dash
import numpy as np
import pandas as pd
from dash import Input, Output, callback, dcc, html

from app import components as ui
from app import data
from src.analysis import a3_concentration as a3
from src.analysis import charts as C

dash.register_page(__name__, path="/usage", name="Usage & Pareto", order=2, group="Analysis")

layout = html.Div([
    ui.head("A3 · Usage concentration", "Who produces the volume?",
            "Pareto, quartiles and the IQR long tail over a trailing window ending at the as-of date. Filters: country and current plan. "
            "Cumulative shares are recomputed for the filtered population."),
    html.Div([html.Label("Window", className="note"),
              dcc.RadioItems(id="use-window", options=[{"label": " 30 days", "value": 30}, {"label": " 90 days", "value": 90}], value=30,
                             inline=True, inputStyle={"marginLeft": "14px", "marginRight": "4px"})]),
    html.Div(id="use-kpis"),
    ui.section("Concentration curve", dcc.Graph(id="use-lorenz", config={"displaylogo": False})),
    html.Div([html.Div(dcc.Graph(id="use-quart", config={"displaylogo": False}), style={"flex": 1, "minWidth": "320px"}),
              html.Div(dcc.Graph(id="use-hist", config={"displaylogo": False}), style={"flex": 1, "minWidth": "320px"})],
             style={"display": "flex", "gap": "16px", "flexWrap": "wrap"}),
    ui.section("Days active vs volume", dcc.Graph(id="use-bands", config={"displaylogo": False})),
    ui.section("Pareto cutoffs", html.Div(id="use-cuts")),
])


@callback(Output("use-kpis", "children"), Output("use-lorenz", "figure"), Output("use-quart", "figure"), Output("use-hist", "figure"),
          Output("use-bands", "figure"), Output("use-cuts", "children"),
          Input("use-window", "value"), Input("f-country", "value"), Input("f-plan", "value"))
def update(window, countries, plan):
    u = data.usage_users(window)
    if countries:
        u = u[u.country_code.isin(countries)]
    if plan != "all":
        u = u[u.is_paying_now == (plan == "paid")]
    if len(u) < 20:
        e = C._fig("Not enough users for this selection")
        return ui.kpis(), e, e, e, e, html.P("Not enough users.", className="note")
    u = data.pareto_from_users(u)
    n = len(u)
    q1, med, q3, p95 = np.quantile(u.total_assets, [0.25, 0.5, 0.75, 0.95])
    fence = q3 + 1.5 * (q3 - q1)
    need = lambda c: int(np.searchsorted(u.cum_share_assets.to_numpy(), c) + 1)  # noqa: E731
    kp = ui.kpis(ui.kpi("Active users", f"{n:,}"), ui.kpi("Users for 80% of volume", f"{need(0.8) / n:.1%}", f"{need(0.8):,} users"),
                 ui.kpi("Median / P95 assets", f"{med:,.0f} / {p95:,.0f}", f"Q3 {q3:,.0f}"),
                 ui.kpi("Beyond IQR fence", f"{(u.total_assets > fence).mean():.1%}", f"carry {u.total_assets[u.total_assets > fence].sum() / u.total_assets.sum():.0%} of volume"))
    q = u.assign(usage_quartile=np.ceil(u.total_assets.rank(method="first") / n * 4).astype(int)).groupby("usage_quartile").total_assets.sum().reset_index()
    q["share_of_volume"] = q.total_assets / q.total_assets.sum()
    q["window_days"] = window
    bands = u.assign(band=np.select([u.active_days == 1, u.active_days <= 3, u.active_days <= 7, u.active_days <= 14, u.active_days <= 30], ["1", "2-3", "4-7", "8-14", "15-30"], "31+"))
    order = ["1", "2-3", "4-7", "8-14", "15-30", "31+"]
    b = bands.groupby("band").agg(users=("user_key", "size"), vol=("total_assets", "sum")).reindex(order).fillna(0).reset_index()
    b["share_of_users"], b["share_of_volume"], b["window_days"] = b.users / b.users.sum(), b.vol / b.vol.sum(), window
    cuts = [{"cutoff": f"{c:.0%}", "users needed": f"{need(c):,}", "share of active users": f"{need(c) / n:.1%}"} for c in (0.5, 0.75, 0.8, 0.9, 0.95)]
    return (kp, C.lorenz({window: a3.lorenz_points(u)}), C.quartile_volume(q, window),
            C.histogram(a3.monthly_histogram(u), f"{window}d volume normalised to 30 days (Freedman-Diaconis bins, clipped at P99)"),
            C.active_day_bands(b, window), ui.table(pd.DataFrame(cuts)))
