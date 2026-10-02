"""Plotly Dash app (SYNTHETIC data): analysis pages plus monitoring pages.

Run locally: ``python -m app.main``   |   production: ``gunicorn app.main:server``
"""
from __future__ import annotations

import os
from pathlib import Path

import dash
from dash import Dash, Input, Output, dcc, html

from app import data, theme
from app.theme import SYNTHETIC_NOTICE

theme.register_template()
HERE = Path(__file__).parent
data.ensure_db()  # builds the synthetic warehouse on first start if it is missing

app = Dash(__name__, use_pages=True, pages_folder=str(HERE / "pages"), assets_folder=str(HERE / "assets"),
           suppress_callback_exceptions=True, title="Vaultly growth analytics (synthetic)",
           update_title=None, meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}])
server = app.server

b = data.bounds()
countries = data.countries()


def nav_links(pathname: str | None):
    pages = sorted(dash.page_registry.values(), key=lambda p: p.get("order", 99))
    out, last = [], None
    for p in pages:
        g = p.get("group", "")
        if g != last:
            out.append(html.Span(g, className="group"))
            last = g
        out.append(html.A(p["name"], href=p["path"], className="active" if p["path"] == pathname else ""))
    return out


def filter_bar():
    return html.Div([
        html.Div([html.Label("Country"),
                  dcc.Dropdown(id="f-country", options=[{"label": c, "value": c} for c in countries], value=[], multi=True,
                               placeholder="All countries", style={"minWidth": "260px"})]),
        html.Div([html.Label("Period (months)"),
                  dcc.DatePickerRange(id="f-dates", min_date_allowed=b["first_month"], max_date_allowed=b["as_of"],
                                      start_date=b["first_month"], end_date=b["as_of"], display_format="YYYY-MM-DD",
                                      minimum_nights=0)]),
        html.Div([html.Label("Plan (current)"),
                  dcc.Dropdown(id="f-plan", options=[{"label": "All plans", "value": "all"}, {"label": "Free", "value": "free"},
                                                     {"label": "Paid", "value": "paid"}], value="all", clearable=False,
                               style={"width": "160px"})]),
        html.Div(html.Span("Filters apply where meaningful; each page says which.", className="note")),
    ], className="filters")


app.layout = html.Div([
    dcc.Location(id="url"),
    html.Header([html.Img(src="/assets/symbol.svg", alt="A"), html.Span("Vaultly growth analytics", className="brand"),
                 html.Span("Synthetic data", className="tag")], className="app-header"),
    html.Nav(id="nav", className="nav"),
    filter_bar(),
    html.Main(dash.page_container, className="page"),
    html.Footer([html.Strong("SYNTHETIC DATA. "), SYNTHETIC_NOTICE.split(": ", 1)[1],
                 " Built by the project's generator (seeded); every number is produced by code in this repository. "
                 "Visual identity: ABADE (Carbon / Ivory / Cobalt, Lato)."], className="footer"),
])


@app.callback(Output("nav", "children"), Input("url", "pathname"))
def _nav(pathname):
    return nav_links(pathname)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8050)), debug=False)
