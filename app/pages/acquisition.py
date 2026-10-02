"""Analysis page: paid acquisition and funnel (filters: country, period)."""
import dash
import pandas as pd
from dash import Input, Output, callback, dcc, html

from app import components as ui
from app import data
from src.analysis import charts as C
from src.analysis import stats

dash.register_page(__name__, path="/", name="Acquisition & funnel", order=1, group="Analysis")

layout = html.Div([
    ui.head("A1 · Paid acquisition", "From spend to signups, by country",
            "Ratios are always recomputed from sums (CTR = total clicks / total impressions), never averaged across rows. "
            "Filters: country and period."),
    html.Div(id="acq-kpis"),
    ui.section("Spend and cost per signup", dcc.Graph(id="acq-spend", config={"displaylogo": False})),
    ui.section("Funnel conversion by country", dcc.Graph(id="acq-funnel", config={"displaylogo": False})),
    ui.section("Cost per signup with uncertainty", dcc.Graph(id="acq-ci", config={"displaylogo": False}),
               html.P("Bootstrap over campaign x month rows (95%). Cost per signup prices a free account; see the retention and unit-economics page "
                      "for paid CAC, which prices a paying customer.", className="note")),
    ui.section("Compare two countries", html.Div([
        dcc.Dropdown(id="acq-a", options=data.countries(), value="BR", clearable=False, style={"width": "120px", "display": "inline-block"}),
        html.Span("  vs  "),
        dcc.Dropdown(id="acq-b", options=data.countries(), value="MX", clearable=False, style={"width": "120px", "display": "inline-block"}),
    ]), html.Div(id="acq-compare"),
        html.P("The z-test treats every impression as an independent trial, so large volumes make tiny gaps 'significant'. "
               "The bootstrap CI resamples campaign x month rows and is the more conservative read.", className="note")),
])


def _sel(countries, start, end):
    return data.filter_ads(countries, start or data.bounds()["first_month"], end or data.bounds()["as_of"])


@callback(Output("acq-kpis", "children"), Output("acq-spend", "figure"), Output("acq-funnel", "figure"), Output("acq-ci", "figure"),
          Input("f-country", "value"), Input("f-dates", "start_date"), Input("f-dates", "end_date"))
def update(countries, start, end):
    d = _sel(countries, start, end)
    if d.empty:
        empty = C._fig("No data for this selection")
        return ui.kpis(), empty, empty, empty
    t = data.ratios_by(d.assign(k=1), ["k"]).iloc[0]
    kp = ui.kpis(ui.kpi("Spend", f"EUR {t.spend_eur:,.0f}"), ui.kpi("Signups", f"{int(t.signups):,}"),
                 ui.kpi("Cost per signup", f"EUR {t.cost_per_signup:.2f}"), ui.kpi("CTR", f"{t.ctr:.2%}", f"CPM EUR {t.cpm:.2f} · CPC EUR {t.cpc:.2f}"),
                 ui.kpi("Landing view rate", f"{t.lpv_rate:.1%}"), ui.kpi("Signup rate", f"{t.signup_rate:.1%}", "signups / landing views"))
    monthly = data.ratios_by(d, ["country", "month_start"]).rename(columns={"country": "country_code"})
    by_c = data.ratios_by(d, ["country"]).rename(columns={"country": "country_code"})
    rows = []
    for c, g in d.groupby("country"):
        est, lo, hi = stats.bootstrap_ratio_ci(g.spend_eur, g.signups, 500)
        rows.append({"country": c, "cost_per_signup": est, "ci_low": lo, "ci_high": hi})
    return kp, C.spend_monthly(monthly), C.funnel_rates(by_c), C.cost_per_signup_ci(pd.DataFrame(rows))


@callback(Output("acq-compare", "children"), Input("acq-a", "value"), Input("acq-b", "value"),
          Input("f-dates", "start_date"), Input("f-dates", "end_date"))
def compare(a, b, start, end):
    if a == b:
        return html.P("Pick two different countries.", className="note")
    d = data.filter_ads([a, b], start or data.bounds()["first_month"], end or data.bounds()["as_of"])
    t = data.ratios_by(d, ["country"]).set_index("country")
    ra, rb = d[d.country == a], d[d.country == b]
    rows = []
    for name, num, den in [("CTR", "link_clicks", "impressions"), ("Landing view rate", "landing_page_views", "link_clicks"),
                           ("Signup rate", "signups", "landing_page_views")]:
        z = stats.two_prop_ztest(int(t.loc[a, num]), int(t.loc[a, den]), int(t.loc[b, num]), int(t.loc[b, den]))
        _, lo, hi = stats.bootstrap_ratio_diff_ci(ra[num], ra[den], rb[num], rb[den], 800)
        rows.append({"metric": name, a: f"{z['p1']:.3%}", b: f"{z['p2']:.3%}", "difference": f"{z['diff']:+.3%}", "z-test p": f"{z['p_value']:.4f}",
                     "bootstrap 95% CI of diff": f"[{lo:+.3%}, {hi:+.3%}]"})
    _, lo, hi = stats.bootstrap_ratio_diff_ci(ra.spend_eur, ra.signups, rb.spend_eur, rb.signups, 800)
    rows.append({"metric": "Cost per signup (EUR)", a: f"{t.loc[a, 'cost_per_signup']:.2f}", b: f"{t.loc[b, 'cost_per_signup']:.2f}",
                 "difference": f"{t.loc[a, 'cost_per_signup'] - t.loc[b, 'cost_per_signup']:+.2f}", "z-test p": "n/a",
                 "bootstrap 95% CI of diff": f"[{lo:+.2f}, {hi:+.2f}]"})
    return ui.table(pd.DataFrame(rows))
