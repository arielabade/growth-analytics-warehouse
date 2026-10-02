"""Single source of truth for the ABADE visual identity (Carbon / Ivory / Cobalt, Lato, "A" symbol).

Exact hex values are reused from the owner's published brand tokens (portfolio README / site CSS):
Carbon #050505, Ivory #F6F5F0, Graphite #1B1C1F, Steel #7E8791, Cobalt #5B6CFF, Aurum #C8B680.

PROVISIONAL values (not defined by the brand book, derived here so a single file can swap them):
  * STATUS_* semantic colours (ok / warn / alert), chosen for >= 4.5:1 contrast on Ivory
  * COBALT_DARK / COBALT_TINT / AURUM_DARK / STEEL_TINT (tints and shades of brand colours for multi-series charts)
  * the "A" symbol geometry in assets/brand/symbol.svg (an outlined Lato Black "A" on a Carbon tile)
Keep app/assets/theme.css in sync with this file.

All data shown by this project is SYNTHETIC.
"""
from __future__ import annotations

import plotly.graph_objects as go
import plotly.io as pio

# --- brand tokens (exact) ---------------------------------------------------------------
CARBON = "#050505"
IVORY = "#F6F5F0"
GRAPHITE = "#1B1C1F"
STEEL = "#7E8791"
COBALT = "#5B6CFF"
AURUM = "#C8B680"

# --- provisional derived values -----------------------------------------------------------
COBALT_DARK = "#2E3AA8"
COBALT_TINT = "#A4ADFF"
AURUM_DARK = "#8A7B4A"
STEEL_TINT = "#C6CBD1"
STATUS_OK = "#1F7A4D"
STATUS_WARN = "#9A5B00"
STATUS_ALERT = "#B3261E"
PROVISIONAL = ["STATUS_OK", "STATUS_WARN", "STATUS_ALERT", "COBALT_DARK", "COBALT_TINT", "AURUM_DARK",
               "STEEL_TINT", "symbol.svg ('A' glyph)"]

FONT_FAMILY = "Lato, 'Helvetica Neue', Arial, sans-serif"
GRID = "rgba(5,5,5,0.08)"

# Charts start in neutrals; Cobalt marks the series that answers the question.
COLORWAY = [COBALT, GRAPHITE, STEEL, AURUM, COBALT_DARK, COBALT_TINT, AURUM_DARK, STEEL_TINT]
STATUS_COLORS = {"ok": STATUS_OK, "warn": STATUS_WARN, "alert": STATUS_ALERT}

SYNTHETIC_NOTICE = "SYNTHETIC DATA: a fictional company; no real customers, spend or results."


def build_template() -> go.layout.Template:
    axis = dict(gridcolor=GRID, zerolinecolor=GRID, linecolor=STEEL, tickcolor=STEEL,
                tickfont=dict(family=FONT_FAMILY, size=12, color=GRAPHITE), ticks="outside",
                title=dict(font=dict(family=FONT_FAMILY, size=12, color=GRAPHITE)))
    layout = go.Layout(
        font=dict(family=FONT_FAMILY, color=CARBON, size=13),
        paper_bgcolor=IVORY, plot_bgcolor=IVORY, colorway=COLORWAY,
        title=dict(font=dict(family=FONT_FAMILY, size=17, color=CARBON), x=0.0, xanchor="left"),
        xaxis=axis, yaxis=axis,
        legend=dict(font=dict(family=FONT_FAMILY, size=12, color=GRAPHITE), bgcolor="rgba(0,0,0,0)"),
        margin=dict(l=56, r=24, t=56, b=48),
        hoverlabel=dict(font=dict(family=FONT_FAMILY), bgcolor=CARBON, font_color=IVORY),
        colorscale=dict(sequential=[[0, IVORY], [1, COBALT]], sequentialminus=[[0, COBALT], [1, IVORY]]),
    )
    return go.layout.Template(layout=layout)


def register_template() -> str:
    """Register and activate the ``abade`` Plotly template; returns its name."""
    pio.templates["abade"] = build_template()
    pio.templates.default = "abade"
    return "abade"


def style_fig(fig: go.Figure, title: str | None = None, height: int | None = None) -> go.Figure:
    register_template()
    fig.update_layout(template="abade")
    if title:
        fig.update_layout(title_text=title)
    if height:
        fig.update_layout(height=height)
    return fig


def status_for(value: float | None, ok_at: float, warn_at: float, higher_is_better: bool = True) -> str:
    """Map a KPI value to 'ok' | 'warn' | 'alert' (or 'na')."""
    if value is None or value != value:
        return "na"
    if higher_is_better:
        return "ok" if value >= ok_at else ("warn" if value >= warn_at else "alert")
    return "ok" if value <= ok_at else ("warn" if value <= warn_at else "alert")
