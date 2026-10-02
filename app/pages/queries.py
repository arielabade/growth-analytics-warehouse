"""Monitoring page: SQL catalogue (query text) and schema diagram."""
import re
from pathlib import Path

import dash
from dash import dcc, html

from app import components as ui
from src.pipeline.sqlio import catalog

dash.register_page(__name__, path="/queries", name="Queries & schema", order=8, group="Monitoring")

ROOT = Path(__file__).resolve().parents[2]
MERMAID = re.search(r"```mermaid\n(.*?)```", (ROOT / "docs" / "SCHEMA.md").read_text(encoding="utf-8"), re.S).group(1)
ORDER = ["ddl", "staging", "marts", "analysis"]
TITLES = {"ddl": "DDL (snowflake schema)", "staging": "Staging → core loads", "marts": "Marts (views)",
          "analysis": "Analysis queries and reconstructed extractions"}


def _query_block(q: dict) -> html.Details:
    meta = [("Business question", q.get("business_question")), ("Tables", q.get("tables")), ("Grain", q.get("grain")),
            ("Output", q.get("output")), ("Replaces", q.get("replaces"))]
    tag = " · reconstructed" if q.get("kind") == "reconstructed" else ""
    return html.Details([html.Summary(f"{q['id']} · {q.get('name', q['id'])}{tag}"),
                         html.Table([html.Tr([html.Th(k), html.Td(v)]) for k, v in meta if v], className="tbl"),
                         html.P(q["path"], className="note"), html.Pre(q["sql"], className="sql")])


def _layout():
    cat = catalog()
    groups = [ui.section(TITLES[g], *[_query_block(q) for q in cat if q["folder"] == g]) for g in ORDER]
    return html.Div([
        ui.head("Monitoring · Queries & schema", "Every query is documented and runnable",
                "One file per query, each with a header: id, business question, tables, grain, output and the original analysis it replaces. "
                "'Reconstructed' queries rebuild, against the core tables, the extractions that would have produced the original input datasets."),
        ui.section("Schema (snowflake)", html.Img(src="/assets/schema.png", alt="Entity-relationship diagram", style={"maxWidth": "100%", "border": "1px solid rgba(5,5,5,.12)"}),
                   html.Details([html.Summary("Mermaid source"), html.Pre(MERMAID, className="sql")]),
                   dcc.Markdown("Grain, keys and design rationale: [docs/SCHEMA.md](https://github.com/arielabade/growth-analytics-warehouse/blob/main/docs/SCHEMA.md).")),
        *groups,
    ])


layout = _layout
