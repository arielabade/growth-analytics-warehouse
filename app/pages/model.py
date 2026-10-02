"""Analysis page: upgrade-propensity model (filter: country for the scored list)."""
import dash
import pandas as pd
from dash import Input, Output, callback, dcc, html

from app import components as ui
from app import data
from src.analysis import charts as C

dash.register_page(__name__, path="/model", name="Propensity model", order=5, group="Analysis")

M = data.model_results()


def _body():
    if not M:
        return html.P("Model results are missing. Run `make all`.", className="note")
    t = M["comparison"][M["chosen"]]["test"]
    lt = pd.DataFrame(M["lift_table"])
    a = M["assumptions"]
    comp = pd.DataFrame([{"model": k, "valid PR-AUC": v["validation"]["pr_auc"], "test PR-AUC": v["test"]["pr_auc"], "test ROC-AUC": v["test"]["roc_auc"],
                          "test Brier": v["test"]["brier"]} for k, v in M["comparison"].items()])
    pp = M["profit_test"]
    return html.Div([
        ui.kpis(ui.kpi("Selected model", M["chosen"].replace("_", " ")), ui.kpi("Hold-out PR-AUC", f"{t['pr_auc']:.3f}", f"base rate {t['base_rate']:.3%}"),
                ui.kpi("Top-decile lift", f"{lt.iloc[0].lift:.1f}x", f"top 2 deciles capture {lt.cum_capture.iloc[1]:.0%}"),
                ui.kpi("Hold-out ROC-AUC", f"{t['roc_auc']:.3f}"),
                ui.kpi("Expected profit at threshold", f"EUR {pp['threshold_policy_eur']:,.0f}", f"contact-all: EUR {pp['contact_all_eur']:,.0f}", "ok" if pp["threshold_policy_eur"] > 0 else "alert")),
        ui.assumption(f"Target: converts to paid in the NEXT 30 days; features only from the PRIOR 60 days (time-based split, purged). Profit assumptions: contact EUR {a['contact_cost_eur']}, "
                      f"nudge lifts conversion by {a['nudge_relative_lift']:.0%}, a customer is worth EUR {a['conversion_value_eur']} (config/analysis.yaml). "
                      f"Break-even precision {M['break_even_precision']:.2%}."),
        ui.section("Model comparison", ui.table(comp, {c: (lambda v: f"{v:.4f}") for c in comp.columns[1:]})),
        html.Div([html.Div(dcc.Graph(figure=C.lift(lt), config={"displaylogo": False}), style={"flex": 1, "minWidth": "320px"}),
                  html.Div(dcc.Graph(figure=C.calibration(pd.DataFrame(M["calibration"]["calibrated_gb_or_lr"]), pd.DataFrame(M["calibration"]["raw_gb"])), config={"displaylogo": False}), style={"flex": 1, "minWidth": "320px"})],
                 style={"display": "flex", "gap": "16px", "flexWrap": "wrap"}),
        html.Div([html.Div(dcc.Graph(figure=C.profit(pd.DataFrame(M["profit_curve_test"]), M["threshold"]), config={"displaylogo": False}), style={"flex": 1, "minWidth": "320px"}),
                  html.Div(dcc.Graph(figure=C.importance(pd.DataFrame(M["importance"])), config={"displaylogo": False}), style={"flex": 1, "minWidth": "320px"})],
                 style={"display": "flex", "gap": "16px", "flexWrap": "wrap"}),
        ui.section("Lift table (hold-out)", ui.table(lt, {"users": lambda v: f"{int(v):,}", "converters": lambda v: f"{int(v)}", "avg_score": lambda v: f"{v:.4f}",
                                                         "conversion_rate": lambda v: f"{v:.3%}", "lift": lambda v: f"{v:.2f}", "cum_capture": lambda v: f"{v:.1%}"})),
        ui.section("Why the target is never built from a feature", html.P(
            f"A deliberately leaky variant (label = 'heavy user' defined from assets_30d, with assets_30d as an input) reaches PR-AUC {M['leakage_demo']['leaky_pr_auc']:.2f} "
            f"and ROC-AUC {M['leakage_demo']['leaky_roc_auc']:.2f}. That looks excellent and means nothing.", className="note")),
        ui.section("Highest-scoring free users right now", html.Div(id="mdl-scores")),
    ])


layout = html.Div([
    ui.head("A6 · Upgrade propensity", "Who is likely to convert in the next 30 days?",
            "Gradient boosting vs logistic regression, compared on a time-based hold-out. Threshold chosen by expected profit, not accuracy. "
            "Filter: country (scored list only)."),
    _body(),
])


@callback(Output("mdl-scores", "children"), Input("f-country", "value"), prevent_initial_call=False)
def scores(countries):
    cs = countries or data.countries()
    d = data.df("""SELECT u.user_id, c.country_code, s.score, s.score_decile, l.signup_date,
                          (SELECT SUM(f.assets_inserted) FROM fact_user_daily_usage f JOIN dim_date d ON d.date_key = f.date_key
                           CROSS JOIN v_as_of a WHERE f.user_key = s.user_key AND d.date > a.as_of_date - 30) AS assets_30d
                   FROM fact_user_scores s JOIN dim_user u ON u.user_key = s.user_key JOIN dim_country c ON c.country_key = u.country_key
                   JOIN mart_user_lifecycle l ON l.user_key = s.user_key
                   WHERE c.country_code IN (SELECT unnest(?::VARCHAR[])) ORDER BY s.score DESC LIMIT 25""", [cs])
    if d.empty:
        return html.P("No scored users for this selection.", className="note")
    d["signup_date"] = d.signup_date.dt.strftime("%Y-%m-%d")
    return ui.table(d, {"score": lambda v: f"{v:.2%}", "score_decile": lambda v: f"{int(v)}", "assets_30d": lambda v: f"{int(v):,}"})
