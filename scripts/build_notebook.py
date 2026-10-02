"""Build and execute notebooks/analysis.ipynb (SYNTHETIC data). Figures are embedded as PNG so GitHub renders them."""
from __future__ import annotations

from pathlib import Path

import nbformat as nbf
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parents[1]
md, code = nbf.v4.new_markdown_cell, nbf.v4.new_code_cell

cells = [
    md("# Growth analytics: full analysis (SYNTHETIC)\n\n> **Synthetic data.** Fictional freemium SaaS \"Vaultly\"; invented parameters; nothing here describes a real business. "
       "Every number below is computed by the code in this repository against the DuckDB warehouse (`make all` builds it).\n\n"
       "Contents: A1 paid acquisition · A2 unit economics · A3 usage concentration · A4 free-tier limit · A5 retention · A6 upgrade propensity."),
    code("""import pandas as pd
from IPython.display import Image, display
from src.analysis import a1_acquisition as a1, a2_unit_economics as a2, a3_concentration as a3, a4_limits as a4, a5_retention as a5
from src.analysis import charts as C
from src.analysis.common import connect, load_result, analysis_cfg
pd.set_option('display.width', 200); pd.set_option('display.max_columns', 30); pd.options.display.float_format = '{:,.3f}'.format
con = connect(); cfg = analysis_cfg()
def show(fig, h=430):
    fig.update_layout(width=1000, height=h)
    display(Image(fig.to_image(format='png', scale=1.2)))"""),
    md("## A1. Paid acquisition\nSpend, impressions, reach, frequency, CPM, CPC, CTR, landing-page-view rate, signup rate and cost per signup. "
       "**Ratios are ratios of sums** (total clicks / total impressions), never an average of row-level ratios."),
    code("by_country = a1.by_country(con)\nby_country[['country_code','spend_eur','impressions','reach','frequency','cpm','cpc','ctr','lpv_rate','signup_rate','cost_per_signup','signups']]"),
    code("show(C.spend_monthly(a1.by_country_month(con)))\nshow(C.funnel_rates(by_country))"),
    md("### BR vs MX\nTwo-proportion z-tests per funnel step and a bootstrap CI of the difference (resampling campaign × month rows). "
       "With millions of impressions the z-test flags almost any gap; the bootstrap respects clustering and is the more conservative read."),
    code("a1.compare_two(con, 'BR', 'MX')"),
    code("a1.pairwise_vs_reference(con, 'BR')"),
    code("show(C.cost_per_signup_ci(a1.cost_per_signup_ci(con)))"),
    md("## A2. Unit economics by country\n**Cost per signup** prices a free account. **Paid CAC** (spend / paying customers, mature cohorts only) prices a paying customer. "
       "They are different numbers and are never mixed. LTV = ARPU × gross margin / monthly churn; payback = CAC / (ARPU × margin)."),
    code("ue = a2.table(con, cfg)\nue[['country_code','cost_per_signup','paid_cac','paid_cac_low','paid_cac_high','arpu','monthly_churn','ltv','ltv_cac','payback_months','paying_customers']]"),
    code("print(a2.blended(ue, cfg['unit_economics']['gross_margin']))\nshow(C.ltv_cac(ue, cfg['unit_economics']['target_ltv_cac']))\nshow(C.cost_vs_cac(a2.cost_vs_cac(ue)))"),
    md("### Sensitivity\nLTV/CAC when churn and CAC move ±25% / ±20%."),
    code("sens = a2.sensitivity(ue, cfg)\nfor c in ['US', 'BR']:\n    display(a2.sensitivity_matrix(sens, c))"),
    md("## A3. Usage concentration\nPareto cutoffs, quartiles, IQR long tail, bands of active days, 30d vs 90d windows (relative to the as-of date), by country and signup cohort."),
    code("a3.pareto_cutoffs(con)"),
    code("a3.quartiles(con)"),
    code("a3.distribution(con).query(\"country_code == 'ALL'\")"),
    code("users = {w: a3.user_level(con, w) for w in (30, 90)}\nshow(C.lorenz({w: a3.lorenz_points(u) for w, u in users.items()}))\nshow(C.quartile_volume(a3.quartiles(con), 30))"),
    code("free30 = a3.user_level(con, 30, free_only=True)\nh = a3.monthly_histogram(free30)\nprint('Freedman-Diaconis bin width', round(h['bin_width'], 2), 'bins', h['bins'])\nshow(C.histogram(h))\nshow(C.active_day_bands(a3.active_day_bands(con), 90))"),
    code("a3.by_country_cohort(con).query('window_days == 90').head(16)"),
    md("## A4. Free-tier limit simulation\nThe usage side is measured. The monetisation layer is **assumption-driven** (low / base / high scenarios in `config/analysis.yaml`)."),
    code("a4.candidates(con)"),
    code("show(C.limit_curves(a4.simulation_grid(con), 'monthly'))\nshow(C.limit_curves(a4.simulation_grid(con), 'daily'))"),
    code("sg = a4.scenario_grid(con, cfg)\nrec = a4.recommend(sg, cfg)\nrec"),
    code("show(C.mrr_scenarios(sg, rec['limit_type'], recommended=rec['limit_value']))"),
    code("sg[(sg.limit_type == rec['limit_type']) & (sg.pct_users_affected <= 0.35)].pivot(index='limit_value', columns='scenario', values='incremental_mrr')[['low','base','high']]"),
    md("**Reading this.** The recommended limit maximises base-scenario incremental MRR *subject to a guardrail* on the share of active free users affected. "
       "Without the guardrail the modelled MRR keeps rising as the limit tightens, because conversion is linear in the share of usage blocked; the guardrail, not the data, bounds the answer. "
       "In the low scenario the same limit loses money: treat the recommendation as a hypothesis to A/B test, not a forecast."),
    md("## A5. Retention\nMonthly paid churn by country, cohort retention triangle, survival curves (Kaplan-Meier, censored at the as-of date)."),
    code("show(C.churn_by_country(a5.churn_by_country_month(con).query('paying_at_start > 0')))\nshow(C.triangle(a5.cohort_triangle(con)), 500)"),
    code("paid = a5.survival_curves(con, 'paid'); act = a5.survival_curves(con, 'activity')\ndisplay(a5.survival_table(paid))\nshow(C.survival(paid, 'Paid subscription survival'))\nshow(C.survival(act, 'Free-user activity survival'))"),
    md("## A6. Upgrade-propensity model\nTarget: converts to paid in the **next 30 days**. Features: only the **prior** 60 days. Time-based split with purged training windows. "
       "Models: logistic regression vs gradient boosting; selected on the validation fold; threshold chosen by expected profit. Training is done by `python -m src.model`; this section reads the stored results."),
    code("m = load_result(con, 'propensity')\npd.DataFrame([{'model': k, **{f'{s} {kk}': vv for s in ('validation','test') for kk, vv in v[s].items() if kk in ('pr_auc','roc_auc','brier')}} for k, v in m['comparison'].items()])"),
    code("print('chosen:', m['chosen'], '| threshold', round(m['threshold'], 4), '| break-even precision', round(m['break_even_precision'], 4))\nprint(m['profit_test'])\npd.DataFrame(m['lift_table'])"),
    code("show(C.lift(pd.DataFrame(m['lift_table'])), 380)\nshow(C.calibration(pd.DataFrame(m['calibration']['calibrated_gb_or_lr']), pd.DataFrame(m['calibration']['raw_gb'])))\nshow(C.profit(pd.DataFrame(m['profit_curve_test']), m['threshold']), 380)\nshow(C.importance(pd.DataFrame(m['importance'])), 380)"),
    md("### Why the target must not be built from a feature\nThe leaky variant below defines the label from `assets_30d` and also feeds `assets_30d` to the model. It looks superb and means nothing."),
    code("m['leakage_demo']"),
    md("---\n*All data in this notebook is synthetic.*"),
]

nb = nbf.v4.new_notebook(cells=cells, metadata={"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}})
out = ROOT / "notebooks" / "analysis.ipynb"
NotebookClient(nb, timeout=900, kernel_name="python3", resources={"metadata": {"path": str(ROOT)}}).execute()
nbf.write(nb, out)
print("wrote", out, f"{out.stat().st_size / 1e6:.1f} MB")
