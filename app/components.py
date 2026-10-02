"""Small reusable UI pieces (KPI cards, tables, status badges)."""
from __future__ import annotations

import pandas as pd
from dash import dcc, html

from app import theme as T


def kpi(label: str, value: str, sub: str = "", status: str | None = None) -> html.Div:
    return html.Div([html.Div(label, className="l"), html.Div(value, className="v"), html.Div(sub, className="s")],
                    className=f"kpi {status or ''}".strip())


def kpis(*items) -> html.Div:
    return html.Div(list(items), className="kpis")


def badge(status: str, text: str | None = None) -> html.Span:
    return html.Span(text or status, className=f"badge {status}")


def table(df: pd.DataFrame, fmt: dict | None = None, max_rows: int = 200) -> html.Table:
    fmt = fmt or {}
    head = html.Thead(html.Tr([html.Th(c) for c in df.columns]))
    body = []
    for _, r in df.head(max_rows).iterrows():
        cells = []
        for c in df.columns:
            v = r[c]
            cells.append(html.Td(fmt[c](v) if c in fmt else (f"{v:,.2f}" if isinstance(v, float) else str(v))))
        body.append(html.Tr(cells))
    return html.Table([head, html.Tbody(body)], className="tbl")


def graph(fig, **kw) -> dcc.Graph:
    return dcc.Graph(figure=fig, config={"displaylogo": False, "responsive": True}, **kw)


def section(title: str, *children) -> html.Div:
    return html.Div([html.H2(title), *children])


def head(eyebrow: str, title: str, lead: str) -> html.Div:
    return html.Div([html.Div(eyebrow, className="eyebrow"), html.H1(title), html.P(lead, className="lead")])


def assumption(text: str) -> html.Div:
    return html.Div(text, className="assumption")


def status_color(status: str) -> str:
    return T.STATUS_COLORS.get(status, T.STEEL)
