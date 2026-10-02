"""Monitoring page: pipeline health, row counts per layer, data-quality results, freshness."""
import dash
import plotly.graph_objects as go
from dash import dcc, html

from app import components as ui
from app import data
from app import theme as T
from src.analysis import charts as C

dash.register_page(__name__, path="/pipeline", name="Pipeline health", order=7, group="Monitoring")

INT = lambda v: "" if v != v or v is None else f"{int(v):,}"  # noqa: E731
SEC = lambda v: "" if v != v else f"{v:,.0f}"  # noqa: E731
STATUS_MAP = {"success": "ok", "success_with_warnings": "warn", "failed": "alert", "running": "na"}


def _layout():
    runs = data.df("SELECT * FROM pipeline_runs ORDER BY started_at DESC")
    if runs.empty:
        return html.Div(html.P("No pipeline runs recorded yet. Run `make pipeline`."))
    latest = runs.iloc[0]
    tables = data.df("SELECT layer, table_name, row_count FROM pipeline_run_tables WHERE run_id = ? ORDER BY layer, table_name", [latest.run_id])
    dq = data.df("SELECT check_name, layer, status, details FROM data_quality_results WHERE run_id = ? ORDER BY CASE status WHEN 'fail' THEN 0 WHEN 'warn' THEN 1 ELSE 2 END, layer, check_name", [latest.run_id])
    fresh = data.df("""SELECT (SELECT as_of_date FROM v_as_of) AS as_of,
                              (SELECT MAX(d.date) FROM fact_user_daily_usage f JOIN dim_date d ON d.date_key = f.date_key) AS last_usage,
                              (SELECT MAX(d.date) FROM fact_ad_performance f JOIN dim_date d ON d.date_key = f.period_end_key) AS last_ads""").iloc[0]
    dur = (latest.finished_at - latest.started_at).total_seconds() if latest.finished_at == latest.finished_at else float("nan")
    cnt = dq.status.value_counts()
    lag_u, lag_a = (fresh.as_of - fresh.last_usage).days, (fresh.as_of - fresh.last_ads).days
    f = C._fig("Rows per table, by layer (log scale)", 420)
    colors = {"raw": T.STEEL, "staging": T.AURUM, "core": T.COBALT, "marts": T.GRAPHITE}
    for layer in ["raw", "staging", "core", "marts"]:
        d = tables[tables.layer == layer]
        f.add_trace(go.Bar(name=layer, x=d.table_name, y=d.row_count, marker_color=colors[layer]))
    f.update_layout(yaxis_type="log", xaxis_tickangle=-40, legend=dict(orientation="h", y=1.1), margin=dict(b=140))
    layer_tot = tables.groupby("layer").row_count.sum().reindex(["raw", "staging", "core", "marts"])
    hist = runs.head(15).copy()
    hist["status"] = [ui.badge(STATUS_MAP.get(s, "na"), s) for s in hist.status]
    hist["duration_s"] = [(b - a).total_seconds() if b == b else float("nan") for a, b in zip(runs.head(15).started_at, runs.head(15).finished_at)]
    hist = hist[["run_id", "started_at", "status", "duration_s", "raw_rows", "staging_rows", "core_rows", "mart_rows", "message"]]
    dq2 = dq.copy()
    dq2["status"] = [ui.badge(s) for s in dq2.status]
    return html.Div([
        ui.head("Monitoring · Pipeline", "Is the pipeline healthy?", "Latest run, row counts per layer, data-quality checks and freshness against the as-of date."),
        ui.kpis(ui.kpi("Latest run", latest.status.replace("_", " "), latest.run_id, STATUS_MAP.get(latest.status)),
                ui.kpi("Duration", f"{dur:,.0f} s", f"as-of {latest.as_of_date}"),
                ui.kpi("Quality checks", f"{cnt.get('pass', 0)} pass", f"{cnt.get('warn', 0)} warn · {cnt.get('fail', 0)} fail", "alert" if cnt.get("fail", 0) else ("warn" if cnt.get("warn", 0) else "ok")),
                ui.kpi("Usage freshness", f"{lag_u} d behind", f"latest {fresh.last_usage:%Y-%m-%d}", "ok" if lag_u <= 1 else ("warn" if lag_u <= 3 else "alert")),
                ui.kpi("Ad data freshness", f"{lag_a} d behind", f"latest {fresh.last_ads:%Y-%m-%d}", "ok" if lag_a <= 1 else ("warn" if lag_a <= 3 else "alert"))),
        ui.kpis(*[ui.kpi(f"{k} rows", f"{int(v):,}") for k, v in layer_tot.items()]),
        dcc.Graph(figure=f, config={"displaylogo": False}),
        ui.section("Data-quality results (latest run)", ui.table(dq2, {"status": lambda v: v})),
        ui.section("Run history", ui.table(hist, {"status": lambda v: v, "duration_s": SEC, "raw_rows": INT, "staging_rows": INT,
                                                   "core_rows": INT, "mart_rows": INT, "message": lambda v: "" if v is None or v != v else str(v)})),
    ])


layout = _layout
