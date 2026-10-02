"""Analysis page: retention and unit economics (filters: country)."""
import dash
from dash import Input, Output, callback, dcc, html

from app import components as ui
from app import data
from src.analysis import a2_unit_economics as a2
from src.analysis import charts as C

dash.register_page(__name__, path="/retention", name="Retention & unit economics", order=4, group="Analysis")

T = data.cfg()["kpi_targets"]

layout = html.Div([
    ui.head("A2 + A5 · Unit economics and retention", "Is a paying customer worth what it costs to win?",
            "LTV = ARPU x gross margin / monthly churn. Paid CAC = spend / paying customers (mature cohorts only), kept apart from cost per signup. "
            "Filter: country."),
    html.Div(id="ret-kpis"),
    ui.section("LTV / CAC", dcc.Graph(id="ret-ltvcac", config={"displaylogo": False}), html.Div(id="ret-table")),
    ui.section("Cost per signup vs paid CAC", dcc.Graph(id="ret-cvc", config={"displaylogo": False})),
    ui.section("Sensitivity", html.Div([html.Label("Country ", className="note"),
                                        dcc.Dropdown(id="ret-sens-country", options=data.countries(), value="BR", clearable=False, style={"width": "120px"})]),
               dcc.Graph(id="ret-sens", config={"displaylogo": False})),
    ui.section("Cohort retention", dcc.Graph(id="ret-tri", config={"displaylogo": False})),
    html.Div([html.Div(dcc.Graph(id="ret-surv-paid", config={"displaylogo": False}), style={"flex": 1, "minWidth": "320px"}),
              html.Div(dcc.Graph(id="ret-surv-act", config={"displaylogo": False}), style={"flex": 1, "minWidth": "320px"})],
             style={"display": "flex", "gap": "16px", "flexWrap": "wrap"}),
    ui.section("Monthly paid churn", dcc.Graph(id="ret-churn", config={"displaylogo": False})),
])


def _status(v):
    return "ok" if v >= T["ltv_cac"]["ok"] else ("warn" if v >= T["ltv_cac"]["warn"] else "alert")


@callback(Output("ret-kpis", "children"), Output("ret-ltvcac", "figure"), Output("ret-table", "children"), Output("ret-cvc", "figure"),
          Output("ret-tri", "figure"), Output("ret-surv-paid", "figure"), Output("ret-surv-act", "figure"), Output("ret-churn", "figure"),
          Input("f-country", "value"), Input("f-dates", "start_date"), Input("f-dates", "end_date"))
def update(countries, start, end):
    ue = data.unit_economics()
    if countries:
        ue = ue[ue.country_code.isin(countries)]
    if ue.empty:
        e = C._fig("No data")
        return ui.kpis(), e, "", e, e, e, e, e
    b = a2.blended(ue, data.cfg()["unit_economics"]["gross_margin"])
    kp = ui.kpis(ui.kpi("Paid CAC", f"EUR {b['paid_cac']:,.0f}", "spend / paying customers"), ui.kpi("ARPU", f"EUR {b['arpu']:.2f}", "per paying customer / month"),
                 ui.kpi("Monthly churn", f"{b['monthly_churn']:.1%}", "paid logo churn"),
                 ui.kpi("LTV", f"EUR {b['ltv']:,.0f}", f"margin {data.cfg()['unit_economics']['gross_margin']:.0%}"),
                 ui.kpi("LTV / CAC", f"{b['ltv_cac']:.2f}x", f"target {T['ltv_cac']['ok']:.0f}x", _status(b["ltv_cac"])),
                 ui.kpi("Payback", f"{b['payback_months']:.1f} months", f"target ≤ {data.cfg()['unit_economics']['target_payback_months']}"))
    tbl = ue[["country_code", "cost_per_signup", "paid_cac", "arpu", "monthly_churn", "ltv", "ltv_cac", "payback_months", "paying_customers"]].copy()
    tbl["status"] = [ui.badge(_status(v), f"{v:.2f}x") for v in ue.ltv_cac]
    fmt = {"monthly_churn": lambda v: f"{v:.1%}", "ltv": lambda v: f"{v:,.0f}", "paid_cac": lambda v: f"{v:,.0f}", "payback_months": lambda v: f"{v:.1f}",
           "paying_customers": lambda v: f"{int(v)}", "ltv_cac": lambda v: f"{v:.2f}", "status": lambda v: v}
    table = ui.table(tbl, fmt)
    cvc = a2.cost_vs_cac(ue)
    cs = countries or data.countries()
    tri = C.triangle(data.triangle(countries))
    sp = {k: v for k, v in data.survival("paid").items() if k in cs or k == "ALL"}
    sa = {k: v for k, v in data.survival("activity").items() if k in cs or k == "ALL"}
    ch = data.churn_series()
    ch = ch[ch.country_code.isin(cs)]
    ch = ch[(ch.paying_at_start > 0)]
    return (kp, C.ltv_cac(ue, T["ltv_cac"]["ok"]), table, C.cost_vs_cac(cvc), tri,
            C.survival(sp, "Paid subscription survival (Kaplan-Meier)", ("ALL",)), C.survival(sa, "Free-user activity survival (inactive 14d = churn)", ("ALL",)),
            C.churn_by_country(ch))


@callback(Output("ret-sens", "figure"), Input("ret-sens-country", "value"))
def sens(country):
    return C.sensitivity_heatmap(a2.sensitivity_matrix(data.sensitivity(), country), country)
