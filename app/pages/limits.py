"""Analysis page: interactive free-tier limit simulator (filter: country)."""
import dash
from dash import Input, Output, callback, dcc, html

from app import components as ui
from app import data
from src.analysis import charts as C

dash.register_page(__name__, path="/limits", name="Free-limit simulator", order=3, group="Analysis")

SC = data.cfg()["limits"]["scenarios"]
GRID = data.limit_tables()["grid"]


def _slider(id_, lo, hi, step, val, fmt):
    return dcc.Slider(id=id_, min=lo, max=hi, step=step, value=val, marks={lo: fmt(lo), hi: fmt(hi), val: fmt(val)},
                      tooltip={"placement": "bottom", "always_visible": False})


layout = html.Div([
    ui.head("A4 · Free-tier limit", "What would a cap affect, and what is it worth?",
            "The usage side is measured: who is above the limit and by how much. The money side is NOT measured; it follows the scenario "
            "assumptions you set below. Filter: country."),
    ui.assumption("Assumptions drive the euro figures. Conversion = conv_max x share of the user's usage that would be blocked. "
                  "Loss = probability that an affected user leaves, valued at the MRR-equivalent of a retained free user."),
    html.Div([
        html.Div([html.Label("Limit type", className="note"),
                  dcc.RadioItems(id="lim-kind", options=[{"label": " Monthly (30d total)", "value": "monthly"}, {"label": " Daily", "value": "daily"}],
                                 value="monthly", inline=True, inputStyle={"marginLeft": "12px", "marginRight": "4px"})]),
        html.Div([html.Label("Limit value (assets)", className="note"), dcc.Slider(id="lim-value", min=0, max=1, step=1, value=0, marks={})],
                 style={"minWidth": "340px", "flex": 1}),
        html.Div([html.Label("Scenario preset", className="note"),
                  dcc.Dropdown(id="lim-preset", options=[{"label": k, "value": k} for k in SC], value="base", clearable=False, style={"width": "140px"})]),
    ], style={"display": "flex", "gap": "28px", "flexWrap": "wrap", "alignItems": "flex-end", "margin": "10px 0"}),
    html.Div([
        html.Div([html.Label("conv_max (conversion if 100% blocked)", className="note"), dcc.Slider(id="lim-conv", min=0, max=0.4, step=0.01, value=SC["base"]["conv_max"], marks={0: "0%", 0.2: "20%", 0.4: "40%"})], style={"flex": 1, "minWidth": "260px"}),
        html.Div([html.Label("loss_prob (affected user leaves)", className="note"), dcc.Slider(id="lim-loss", min=0, max=0.4, step=0.01, value=SC["base"]["loss_prob"], marks={0: "0%", 0.2: "20%", 0.4: "40%"})], style={"flex": 1, "minWidth": "260px"}),
        html.Div([html.Label("value of a retained free user (EUR MRR-equiv.)", className="note"), dcc.Slider(id="lim-val", min=0, max=10, step=0.5, value=SC["base"]["free_user_value_eur"], marks={0: "0", 5: "5", 10: "10"})], style={"flex": 1, "minWidth": "260px"}),
    ], style={"display": "flex", "gap": "28px", "flexWrap": "wrap"}),
    html.Div(id="lim-kpis"),
    ui.section("Usage impact (measured)", dcc.Graph(id="lim-impact", config={"displaylogo": False})),
    ui.section("Expected incremental MRR at the current assumptions", dcc.Graph(id="lim-mrr", config={"displaylogo": False}),
               html.P("The linear conversion model cannot represent backlash from mass blocking, so very low limits look better than they would be. "
                      "Use the 'users affected' guardrail (default 20%) when reading the curve.", className="note")),
])


@callback(Output("lim-value", "min"), Output("lim-value", "max"), Output("lim-value", "marks"), Output("lim-value", "value"), Input("lim-kind", "value"))
def grid_for_kind(kind):
    vals = sorted(GRID[GRID.limit_type == kind].limit_value.tolist())
    marks = {i: str(int(v)) for i, v in enumerate(vals) if i % 2 == 0 or i == len(vals) - 1}
    default = vals.index(50) if kind == "monthly" and 50 in vals else (vals.index(20) if 20 in vals else 0)
    return 0, len(vals) - 1, marks, default


@callback(Output("lim-conv", "value"), Output("lim-loss", "value"), Output("lim-val", "value"), Input("lim-preset", "value"))
def preset(p):
    s = SC[p]
    return s["conv_max"], s["loss_prob"], s["free_user_value_eur"]


@callback(Output("lim-kpis", "children"), Output("lim-impact", "figure"), Output("lim-mrr", "figure"),
          Input("lim-kind", "value"), Input("lim-value", "value"), Input("lim-conv", "value"), Input("lim-loss", "value"),
          Input("lim-val", "value"), Input("f-country", "value"))
def update(kind, idx, conv, loss, val, countries):
    vals = sorted(GRID[GRID.limit_type == kind].limit_value.tolist())
    limit = vals[min(int(idx or 0), len(vals) - 1)]
    g = data.simulate_limits(kind, countries, conv, loss, val)
    row = g[g.limit_value == limit].iloc[0]
    guard = data.cfg()["limits"]["guardrail_max_pct_users_affected"]
    status = "alert" if row.incremental_mrr < 0 else ("warn" if row.pct_users_affected > guard else "ok")
    kp = ui.kpis(ui.kpi("Limit", f"{limit:g} / {'day' if kind == 'daily' else '30d'}"),
                 ui.kpi("Active free users affected", f"{int(row.users_affected):,}", f"{row.pct_users_affected:.1%} of active free users",
                        "warn" if row.pct_users_affected > guard else None),
                 ui.kpi("Volume above the limit", f"{row.pct_volume_excess:.1%}", f"{row.excess:,.0f} assets / 30d"),
                 ui.kpi("Expected users lost", f"{row.expected_users_lost:,.0f}", "assumption-driven"),
                 ui.kpi("Expected incremental MRR", f"EUR {row.incremental_mrr:+,.0f}", f"gain {row.mrr_gain:,.0f} − loss {row.mrr_loss:,.0f}", status))
    impact = C._fig(f"{kind.title()} limit: users affected and volume above the limit", 360)
    import plotly.graph_objects as go

    from app import theme as T
    impact.add_trace(go.Scatter(x=g.limit_value, y=g.pct_users_affected, name="Users affected", mode="lines+markers", line=dict(color=T.COBALT, width=3)))
    impact.add_trace(go.Scatter(x=g.limit_value, y=g.pct_volume_excess, name="Volume above limit", mode="lines+markers", line=dict(color=T.GRAPHITE, dash="dot")))
    impact.add_trace(go.Scatter(x=[limit], y=[row.pct_users_affected], mode="markers", marker=dict(size=14, color=T.AURUM, line=dict(color=T.CARBON, width=2)), name="Selected", showlegend=False))
    impact.update_layout(xaxis_type="log", xaxis_title="limit (assets)", yaxis_tickformat=".0%", legend=dict(orientation="h", y=1.12))
    mrr = C._fig("Expected incremental MRR (EUR/month) at the current assumptions", 360)
    inside = g[g.pct_users_affected <= guard]
    mrr.add_trace(go.Scatter(x=g.limit_value, y=g.incremental_mrr, mode="lines+markers", line=dict(color=T.STEEL, width=2), name="all limits"))
    mrr.add_trace(go.Scatter(x=inside.limit_value, y=inside.incremental_mrr, mode="lines+markers", line=dict(color=T.COBALT, width=3), name=f"within {guard:.0%} guardrail"))
    mrr.add_trace(go.Scatter(x=[limit], y=[row.incremental_mrr], mode="markers", marker=dict(size=14, color=T.AURUM, line=dict(color=T.CARBON, width=2)), name="Selected"))
    mrr.add_hline(y=0, line_color=T.STEEL)
    mrr.update_layout(xaxis_type="log", xaxis_title="limit (assets)", yaxis_title="EUR / month", legend=dict(orientation="h", y=1.12))
    return kp, impact, mrr
