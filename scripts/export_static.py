"""Export the dashboard as a single static page for GitHub Pages.

Why this exists
---------------
``app/`` is a Dash application: it needs a Python process, so it cannot be
opened from a repository link. The analyses, the charts and the brand template
are already written, and the only thing standing between a reader and the
result was a server.

This script reuses exactly those pieces — ``src.analysis.run_all.compute`` and
``.figures`` for the content, ``app.theme`` for the look — and writes one HTML
file that carries the figures inline. Plotly's own JavaScript comes from a CDN,
so hover, zoom and legend toggling all still work. Nothing is recomputed here
and nothing is restyled here; if a chart changes in the app, it changes here.

What this is NOT: the live simulator on the Limits page. Its sliders recompute
against the warehouse on every move, which needs the Python process. That page
links to the Dash app instead of pretending to be it.

Usage: ``python scripts/export_static.py`` (after ``make all``).
"""

from __future__ import annotations

import datetime as dt
import html
import json
import sys
from pathlib import Path

# Run as a script from anywhere: the repository root has to be importable
# before ``app`` and ``src`` resolve.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import plotly.io as pio

from app.theme import CARBON, COBALT, GRAPHITE, IVORY, STEEL, register_template
from src.analysis.common import ROOT, connect
from src.analysis.run_all import compute, figures, headline

OUT_DIR = ROOT / "docs" / "dashboard"
REPO_URL = "https://github.com/arielabade/growth-analytics-warehouse"

#: Which figures go on which tab, and what each one is for. The caption is the
#: part a static page has to carry that an interactive one can leave implicit.
TABS: dict[str, list[tuple[str, str]]] = {
    "Acquisition": [
        ("cost_per_signup_ci", "Cost per signup with bootstrap confidence intervals. Overlapping intervals mean the ranking is not evidence."),
        ("funnel_rates", "Where each country's funnel actually loses people."),
        ("spend_monthly", "Spend over time by country."),
    ],
    "Unit economics": [
        ("ltv_cac", "LTV/CAC by country against the 3x target. Only one country clears it."),
        ("cost_vs_cac", "Cost per signup against cost per paying customer: the two are not the same metric, and treating them as one is how paid media looks profitable where it is not."),
    ],
    "Usage": [
        ("lorenz", "Volume concentration. A minority of users produce most of the load."),
        ("quartile_volume", "Volume by usage quartile."),
        ("active_day_bands", "How many days a month users are actually active."),
    ],
    "Retention": [
        ("retention_triangle", "Cohort retention by months since signup."),
        ("survival_paid", "Paid subscription survival, Kaplan-Meier."),
        ("churn_by_country", "Churn over time by country."),
    ],
    "Model": [
        ("model_lift", "Upgrade-propensity lift by decile."),
        ("model_calibration", "Calibrated against raw scores. A score that drives a money decision has to behave like a probability."),
        ("model_profit", "Profit as a function of the contact threshold: the number that picks the cutoff."),
        ("model_importance", "What the model leans on."),
    ],
}

KPIS = (
    ("ltv_cac_blended", "Blended LTV/CAC", "{:.2f}x"),
    ("paid_cac", "Paid CAC", "EUR {:,.0f}"),
    ("cost_per_signup", "Cost per signup", "EUR {:,.2f}"),
    ("payback_months", "Payback", "{:.1f} months"),
    ("model_top_decile_lift", "Model top-decile lift", "{:.1f}x"),
    ("pct_users_80_30d", "Users producing 80% of volume", "{:.1%}"),
)

STYLE = f"""
*, *::before, *::after {{ box-sizing: border-box; }}
:root {{
  --carbon: {CARBON}; --ivory: {IVORY}; --graphite: {GRAPHITE};
  --steel: {STEEL}; --cobalt: {COBALT}; --line: rgba(5,5,5,.12);
}}
body {{
  margin: 0; background: var(--ivory); color: var(--carbon);
  font-family: Lato, "Helvetica Neue", Arial, sans-serif; line-height: 1.55;
}}
.wrap {{ max-width: 1180px; margin: 0 auto; padding: 0 16px 72px; }}
header {{ background: var(--carbon); color: var(--ivory); padding: 40px 0 34px; margin-bottom: 28px; }}
header .wrap {{ padding-bottom: 0; }}
h1 {{ font-size: clamp(1.5rem, 4vw, 2.1rem); margin: 0 0 10px; letter-spacing: -.01em; }}
.lede {{ color: #C9CDD2; max-width: 60ch; margin: 0 0 18px; }}
.notice {{
  display: inline-block; border: 1px solid var(--cobalt); color: var(--cobalt);
  border-radius: 999px; padding: 5px 14px; font-size: .78rem; letter-spacing: .06em;
  text-transform: uppercase; margin-bottom: 18px;
}}
.kpis {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(165px, 1fr)); gap: 1px; background: rgba(246,245,240,.16); border: 1px solid rgba(246,245,240,.16); }}
.kpi {{ background: var(--carbon); padding: 16px 18px; }}
.kpi b {{ display: block; font-size: 1.5rem; color: var(--ivory); letter-spacing: -.01em; }}
.kpi span {{ font-size: .76rem; color: #9BA2AA; }}
nav {{ display: flex; flex-wrap: wrap; gap: 6px; border-bottom: 1px solid var(--line); margin-bottom: 26px; }}
nav button {{
  appearance: none; border: 0; background: none; cursor: pointer; font: inherit;
  padding: 11px 16px; color: var(--steel); border-bottom: 2px solid transparent;
}}
nav button[aria-selected="true"] {{ color: var(--carbon); border-bottom-color: var(--cobalt); font-weight: 700; }}
.panel[hidden] {{ display: none; }}
figure {{ margin: 0 0 34px; }}
figcaption {{ color: var(--graphite); font-size: .9rem; margin-top: 6px; max-width: 78ch; }}
.chart {{ border: 1px solid var(--line); border-radius: 10px; overflow: hidden; }}
footer {{ border-top: 1px solid var(--line); padding-top: 18px; color: var(--graphite); font-size: .86rem; }}
a {{ color: var(--cobalt); }}
@media (max-width: 640px) {{ .kpi b {{ font-size: 1.25rem; }} }}
"""

SCRIPT = """
const buttons = [...document.querySelectorAll('nav button')];
const panels = [...document.querySelectorAll('.panel')];
function show(name) {
  buttons.forEach(b => b.setAttribute('aria-selected', String(b.dataset.tab === name)));
  panels.forEach(p => { p.hidden = p.dataset.tab !== name; });
  // Plotly sizes to a hidden container as zero, so each newly shown chart is
  // told to measure itself again.
  panels.filter(p => !p.hidden).forEach(p =>
    p.querySelectorAll('.js-plotly-plot').forEach(d => window.Plotly.Plots.resize(d)));
  history.replaceState(null, '', '#' + encodeURIComponent(name));
}
buttons.forEach(b => b.addEventListener('click', () => show(b.dataset.tab)));
window.addEventListener('resize', () =>
  document.querySelectorAll('.panel:not([hidden]) .js-plotly-plot')
    .forEach(d => window.Plotly.Plots.resize(d)));
show(decodeURIComponent(location.hash.slice(1)) || buttons[0].dataset.tab);
"""


def _format(value, pattern: str) -> str:
    try:
        return pattern.format(value)
    except (TypeError, ValueError):
        return "n/a"


def build() -> Path:
    register_template()
    con = connect()
    results = compute(con)
    all_figures = figures(results)
    head = headline(results)

    kpi_html = "".join(
        f'<div class="kpi"><b>{html.escape(_format(head.get(key), pattern))}</b>'
        f'<span>{html.escape(label)}</span></div>'
        for key, label, pattern in KPIS
    )

    tabs_html, panels_html, first = [], [], True
    for tab, entries in TABS.items():
        tabs_html.append(
            f'<button role="tab" data-tab="{html.escape(tab)}" '
            f'aria-selected="{str(first).lower()}">{html.escape(tab)}</button>'
        )
        blocks = []
        for name, caption in entries:
            figure = all_figures.get(name)
            if figure is None:
                continue  # an analysis that did not run leaves no hole in the page
            figure.update_layout(autosize=True, height=460, width=None,
                                 margin=dict(l=56, r=24, t=56, b=48))
            div = pio.to_html(
                figure, include_plotlyjs=False, full_html=False,
                config={"displayModeBar": False, "responsive": True},
                default_width="100%", default_height="460px",
            )
            blocks.append(
                f'<figure><div class="chart">{div}</div>'
                f'<figcaption>{html.escape(caption)}</figcaption></figure>'
            )
        panels_html.append(
            f'<section class="panel" data-tab="{html.escape(tab)}"'
            f'{"" if first else " hidden"}>{"".join(blocks)}</section>'
        )
        first = False

    built = dt.date.today().isoformat()
    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Growth Analytics Warehouse — dashboard</title>
<meta name="description" content="Synthetic end-to-end growth analytics platform: acquisition, unit economics, usage, retention and an upgrade-propensity model.">
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js" charset="utf-8"></script>
<style>{STYLE}</style>
</head>
<body>
<header>
  <div class="wrap">
    <div class="notice">Synthetic data</div>
    <h1>Growth Analytics Warehouse</h1>
    <p class="lede">A signup costs EUR {head.get('cost_per_signup', 0):,.2f}. A paying customer costs
    EUR {head.get('paid_cac', 0):,.0f}. Treating the two as one metric is how paid media looks
    profitable in countries where it is not — only {head.get('best_country', '')} clears 3x LTV/CAC.</p>
    <div class="kpis">{kpi_html}</div>
  </div>
</header>
<div class="wrap">
  <nav role="tablist">{"".join(tabs_html)}</nav>
  {"".join(panels_html)}
  <footer>
    <p>Every figure is generated by this repository's own analysis code, against a seeded
    synthetic warehouse. The company, its users, its spend and its results are invented.</p>
    <p><a href="{REPO_URL}">Source and method on GitHub</a> ·
    the live Limits simulator needs the Dash app (<code>make app</code>) ·
    built {built}</p>
  </footer>
</div>
<script>{SCRIPT}</script>
</body>
</html>
"""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    target = OUT_DIR / "index.html"
    target.write_text(page, encoding="utf-8")
    # Pages would otherwise hand the directory to Jekyll, which skips files and
    # folders beginning with an underscore.
    (ROOT / "docs" / ".nojekyll").write_text("", encoding="utf-8")
    (OUT_DIR / "headline.json").write_text(json.dumps(head, indent=2, default=float), encoding="utf-8")
    return target


if __name__ == "__main__":
    path = build()
    print(f"wrote {path} ({path.stat().st_size / 1024:,.0f} KB)")
