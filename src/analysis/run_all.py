"""Run every analysis against the warehouse, export charts, and write docs/RESULTS.md, docs/MODEL_CARD.md
and the README "Key results" block. Every number in those documents comes from this code (SYNTHETIC data).

Usage: python -m src.analysis.run_all [--no-images]
"""
from __future__ import annotations

import argparse
import json
import re

import pandas as pd

from src.analysis import a1_acquisition as a1
from src.analysis import a2_unit_economics as a2
from src.analysis import a3_concentration as a3
from src.analysis import a4_limits as a4
from src.analysis import a5_retention as a5
from src.analysis import charts as C
from src.analysis.common import ROOT, analysis_cfg, connect, load_result, save_result

IMG = ROOT / "docs" / "img"
CHART_WIDTH, CHART_HEIGHT = 1100, 460


def md_table(df: pd.DataFrame, fmt: dict | None = None) -> str:
    fmt = fmt or {}
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
    for _, r in df.iterrows():
        cells = []
        for c in cols:
            v = r[c]
            cells.append(fmt[c](v) if c in fmt else (f"{v:,.2f}" if isinstance(v, float) else str(v)))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def export(fig, name: str) -> None:
    fig.update_layout(width=CHART_WIDTH, height=CHART_HEIGHT)
    fig.write_image(str(IMG / f"{name}.png"), scale=1.5)


def compute(con) -> dict:
    cfg = analysis_cfg()
    R: dict = {"cfg": cfg}
    R["country"] = a1.by_country(con)
    R["monthly"] = a1.by_country_month(con)
    R["br_mx"] = a1.compare_two(con, "BR", "MX")
    R["pairwise"] = a1.pairwise_vs_reference(con, "BR")
    R["cps_ci"] = a1.cost_per_signup_ci(con)
    R["ue"] = a2.table(con, cfg)
    R["blended"] = a2.blended(R["ue"], cfg["unit_economics"]["gross_margin"])
    R["sens"] = a2.sensitivity(R["ue"], cfg)
    R["cvc"] = a2.cost_vs_cac(R["ue"])
    R["usage"] = a3.summary(con)
    R["pareto"] = a3.pareto_cutoffs(con)
    R["quartiles"] = a3.quartiles(con)
    R["dist"] = a3.distribution(con)
    R["bands"] = a3.active_day_bands(con)
    R["free30"] = a3.user_level(con, 30, free_only=True)
    R["hist"] = a3.monthly_histogram(R["free30"])
    R["lorenz"] = {w: a3.lorenz_points(a3.user_level(con, w)) for w in (30, 90)}
    R["grid"] = a4.simulation_grid(con)
    R["cand"] = a4.candidates(con)
    R["sgrid"] = a4.scenario_grid(con, cfg)
    R["rec"] = a4.recommend(R["sgrid"], cfg)
    R["triangle"] = a5.cohort_triangle(con)
    R["churn_ts"] = a5.churn_by_country_month(con)
    R["surv_paid"] = a5.survival_curves(con, "paid")
    R["surv_act"] = a5.survival_curves(con, "activity")
    R["model"] = load_result(con, "propensity")
    return R


def figures(R: dict) -> dict:
    F = {
        "cost_per_signup_ci": C.cost_per_signup_ci(R["cps_ci"]),
        "funnel_rates": C.funnel_rates(R["country"]),
        "spend_monthly": C.spend_monthly(R["monthly"]),
        "ltv_cac": C.ltv_cac(R["ue"], R["cfg"]["unit_economics"]["target_ltv_cac"]),
        "cost_vs_cac": C.cost_vs_cac(R["cvc"]),
        "lorenz": C.lorenz(R["lorenz"]),
        "quartile_volume": C.quartile_volume(R["quartiles"], 30),
        "histogram": C.histogram(R["hist"]),
        "active_day_bands": C.active_day_bands(R["bands"], 90),
        "limit_curves_monthly": C.limit_curves(R["grid"], "monthly"),
        "limit_curves_daily": C.limit_curves(R["grid"], "daily"),
        "mrr_scenarios_monthly": C.mrr_scenarios(R["sgrid"], "monthly", recommended=R["rec"]["limit_value"] if R["rec"]["limit_type"] == "monthly" else None),
        "mrr_scenarios_daily": C.mrr_scenarios(R["sgrid"], "daily", recommended=R["rec"]["limit_value"] if R["rec"]["limit_type"] == "daily" else None),
        "retention_triangle": C.triangle(R["triangle"]),
        "survival_paid": C.survival(R["surv_paid"], "Paid subscription survival (Kaplan-Meier; ALL highlighted)"),
        "survival_activity": C.survival(R["surv_act"], "Free-user activity survival (Kaplan-Meier; ALL highlighted)"),
        "churn_by_country": C.churn_by_country(R["churn_ts"]),
    }
    m = R["model"]
    if m:
        F["model_lift"] = C.lift(pd.DataFrame(m["lift_table"]))
        F["model_calibration"] = C.calibration(pd.DataFrame(m["calibration"]["calibrated_gb_or_lr"]),
                                               pd.DataFrame(m["calibration"]["raw_gb"]))
        F["model_profit"] = C.profit(pd.DataFrame(m["profit_curve_test"]), m["threshold"])
        F["model_importance"] = C.importance(pd.DataFrame(m["importance"]))
    return F


def headline(R: dict) -> dict:
    c, ue, b, u, rec, m = R["country"], R["ue"], R["blended"], R["usage"], R["rec"], R["model"]
    tot_spend, tot_signups = float(c.spend_eur.sum()), int(c.signups.sum())
    bm = R["br_mx"].set_index("step")
    h = {
        "spend_eur": tot_spend, "signups": tot_signups, "cost_per_signup": tot_spend / tot_signups,
        "paid_cac": b["paid_cac"], "ltv_cac_blended": b["ltv_cac"], "payback_months": b["payback_months"],
        "countries_ge_3x": ue[ue.ltv_cac >= 3].country_code.tolist(),
        "best_country": ue.iloc[0].country_code, "best_ltv_cac": float(ue.iloc[0].ltv_cac),
        "worst_country": ue.iloc[-1].country_code, "worst_ltv_cac": float(ue.iloc[-1].ltv_cac),
        "br_mx_signup_rate_p": float(bm.loc["Signup rate (signups / views)", "p_value"]),
        "br_mx_ctr_p": float(bm.loc["CTR (clicks / impressions)", "p_value"]),
        "br_mx_ctr_ci": [float(bm.loc["CTR (clicks / impressions)", "boot_ci_low"]), float(bm.loc["CTR (clicks / impressions)", "boot_ci_high"])],
        "br_mx_cps_diff": float(bm.loc["Cost per signup (EUR)", "diff"]),
        "br_mx_cps_ci": [float(bm.loc["Cost per signup (EUR)", "boot_ci_low"]), float(bm.loc["Cost per signup (EUR)", "boot_ci_high"])],
        "pct_users_80_30d": u[30]["pct_users_for_80pct"], "pct_users_80_90d": u[90]["pct_users_for_80pct"],
        "pct_users_50_30d": u[30]["pct_users_for_50pct"], "active_users_30d": u[30]["active_users"],
        "tail_volume_share_30d": u[30]["volume_share_beyond_fence"],
        "rec_type": rec["limit_type"], "rec_value": rec["limit_value"], "rec_pct_affected": rec["pct_users_affected"],
        "rec_mrr": rec["incremental_mrr_by_scenario"], "rec_robust": rec["robust_positive"],
        "paid_surv_180": float(R["surv_paid"]["ALL"].pipe(lambda d: d.survival[d.days <= 180].iloc[-1])),
    }
    if m:
        t = m["comparison"][m["chosen"]]["test"]
        lt = pd.DataFrame(m["lift_table"])
        h.update({"model": m["chosen"], "model_pr_auc": t["pr_auc"], "model_base_rate": t["base_rate"],
                  "model_roc_auc": t["roc_auc"], "model_top_decile_lift": float(lt.iloc[0].lift),
                  "model_top2_capture": float(lt.cum_capture.iloc[1]), "model_profit": m["profit_test"]["threshold_policy_eur"],
                  "model_profit_all": m["profit_test"]["contact_all_eur"], "model_contacted_share": m["profit_test"]["contacted"] / m["profit_test"]["of"]})
    return h


def results_md(R: dict, h: dict) -> str:
    pct = lambda v: f"{v:.1%}"  # noqa: E731
    eur = lambda v: f"{v:,.2f}"  # noqa: E731
    ue = R["ue"].copy()
    ue_t = ue[["country_code", "cost_per_signup", "paid_cac", "arpu", "monthly_churn", "ltv", "ltv_cac", "payback_months", "paying_customers"]]
    rec = R["rec"]
    s = ["# Results (SYNTHETIC)", "",
         "> Generated by `python -m src.analysis.run_all` from the **synthetic** warehouse. Fictional company, invented parameters: "
         "nothing here describes a real business. Re-running the pipeline with the same seed reproduces these numbers.", "",
         "## A1. Paid acquisition", "",
         f"Total spend EUR {h['spend_eur']:,.0f}, {h['signups']:,} signups, blended cost per signup EUR {h['cost_per_signup']:.2f}.", "",
         md_table(R["country"][["country_code", "spend_eur", "signups", "cpm", "cpc", "ctr", "lpv_rate", "signup_rate", "cost_per_signup"]],
                  {"spend_eur": lambda v: f"{v:,.0f}", "signups": lambda v: f"{int(v):,}", "cpm": eur, "cpc": eur,
                   "ctr": lambda v: f"{v:.2%}", "lpv_rate": pct, "signup_rate": pct, "cost_per_signup": eur}), "",
         "### BR vs MX", "",
         md_table(R["br_mx"], {"BR": lambda v: f"{v:.4f}", "MX": lambda v: f"{v:.4f}", "diff": lambda v: f"{v:+.4f}",
                               "z": lambda v: "" if v != v else f"{v:.2f}", "p_value": lambda v: "" if v != v else f"{v:.4f}",
                               "boot_ci_low": lambda v: f"{v:+.4f}", "boot_ci_high": lambda v: f"{v:+.4f}"}), "",
         "The z-test treats each impression/click as an independent trial, so with millions of impressions almost any gap is "
         "\"significant\". The bootstrap resamples campaign x period rows and is the more conservative read.", "",
         "### Cost per signup by country (95% bootstrap CI)", "", md_table(R["cps_ci"][["country", "cost_per_signup", "ci_low", "ci_high"]]), "",
         "## A2. Unit economics", "",
         md_table(ue_t, {"paying_customers": lambda v: f"{int(v)}", "monthly_churn": pct, "ltv": lambda v: f"{v:,.0f}",
                         "paid_cac": lambda v: f"{v:,.0f}", "arpu": eur, "cost_per_signup": eur, "ltv_cac": eur, "payback_months": lambda v: f"{v:.1f}"}), "",
         f"Blended (ratio of sums): paid CAC EUR {h['paid_cac']:.0f}, LTV/CAC {h['ltv_cac_blended']:.2f}x, payback {h['payback_months']:.1f} months. "
         f"Countries at or above 3x: {', '.join(h['countries_ge_3x']) or 'none'}.", "",
         "## A3. Usage concentration", "",
         f"In the trailing 30 days, {pct(h['pct_users_80_30d'])} of the {h['active_users_30d']:,} active users produce 80% of inserted assets "
         f"({pct(h['pct_users_50_30d'])} produce 50%). Users beyond the IQR upper fence carry {pct(h['tail_volume_share_30d'])} of volume.", "",
         md_table(R["pareto"], {"cutoff": lambda v: f"{v:.0%}", "pct_users_needed": pct, "users_needed": lambda v: f"{int(v):,}", "active_users": lambda v: f"{int(v):,}"}), "",
         md_table(R["dist"][R["dist"].country_code == "ALL"][["window_days", "users", "q1", "median", "q3", "p95", "p99", "max_assets", "iqr", "upper_fence"]],
                  {"users": lambda v: f"{int(v):,}"}), "",
         "## A4. Free-tier limit simulation", "",
         f"Recommended (base scenario, guardrail <= {rec['guardrail']:.0%} of active free users affected): **{rec['limit_type']} limit of {rec['limit_value']:g} assets**, "
         f"affecting {pct(rec['pct_users_affected'])} of active free users. Expected incremental MRR (EUR/month) by scenario: "
         + ", ".join(f"{k} {v:+,.0f}" for k, v in rec["incremental_mrr_by_scenario"].items()) + ". "
         + ("The sign is positive in every scenario." if rec["robust_positive"] else "**The sign flips across scenarios: the recommendation is assumption-driven.**"), "",
         "Scenario optima (guardrail applied): " + "; ".join(f"{k}: {v['limit_type']} {v['limit_value']:g} (EUR {v['incremental_mrr']:+,.0f})" for k, v in rec["scenario_optima"].items()) + ".", "",
         "Without the guardrail the modelled MRR keeps rising as the limit tightens, because the conversion model is linear in the share of usage blocked and "
         "cannot capture backlash from mass blocking. The guardrail, not the data, bounds the recommendation.", "",
         md_table(R["cand"], {"candidate": lambda v: f"{v:,.1f}"}), "",
         "## A5. Retention", "",
         f"Share of paid subscriptions still active 180 days after upgrade (Kaplan-Meier, all countries): {pct(h['paid_surv_180'])}.", "",
         md_table(a5.survival_table(R["surv_paid"]), {c: pct for c in ["S(30d)", "S(90d)", "S(180d)"]}), ""]
    m = R["model"]
    if m:
        t = m["comparison"][m["chosen"]]["test"]
        s += ["## A6. Upgrade-propensity model", "",
              f"Selected: `{m['chosen']}`. Hold-out PR-AUC {t['pr_auc']:.3f} vs base rate {t['base_rate']:.3f} ({t['pr_auc'] / t['base_rate']:.1f}x), ROC-AUC {t['roc_auc']:.3f}. "
              f"Top-decile lift {h['model_top_decile_lift']:.1f}x; top two deciles capture {pct(h['model_top2_capture'])} of converters. "
              f"Contacting users above the profit-optimal threshold ({pct(h['model_contacted_share'])} of users) yields EUR {h['model_profit']:,.0f} expected profit "
              f"vs EUR {h['model_profit_all']:,.0f} for contacting everyone (assumptions in config/analysis.yaml).", "",
              md_table(pd.DataFrame(m["lift_table"]), {"users": lambda v: f"{int(v):,}", "converters": lambda v: f"{int(v)}", "avg_score": lambda v: f"{v:.4f}",
                                                       "conversion_rate": lambda v: f"{v:.3%}", "lift": lambda v: f"{v:.2f}", "cum_capture": pct}), ""]
    return "\n".join(s) + "\n"


def model_card(m: dict, h: dict) -> str:
    t = m["comparison"][m["chosen"]]["test"]
    rows = [{"model": k, "valid PR-AUC": v["validation"]["pr_auc"], "test PR-AUC": v["test"]["pr_auc"],
             "test ROC-AUC": v["test"]["roc_auc"], "test Brier": v["test"]["brier"]} for k, v in m["comparison"].items()]
    a = m["assumptions"]
    imp = pd.DataFrame(m["importance"]).head(6)
    return f"""# Model card: upgrade propensity (SYNTHETIC)

> Trained on **synthetic** data from a fictional company. It demonstrates method, not real-world performance.

## Purpose
Rank currently-free active users by the probability that they convert to a paid plan in the **next 30 days**, so that a
limited-budget upgrade nudge can be aimed at the users most likely to respond.

## Data and target
* Grain: user x month-end snapshot (`mart_user_features`), free users who never paid before the snapshot and were active in the prior 60 days.
* Target: `converted_next_30d`, i.e. first upgrade event in (snapshot, snapshot + 30 days]. Base rate on the hold-out: {t['base_rate']:.3%}.
* Features: only days **at or before** the snapshot: assets and active days in the prior 30 days and the 30 days before that, largest single day, days since last use,
  tenure, trend (log ratio of recent to previous volume), country and acquisition source.
* **Leakage guard.** The target is never defined from a feature. A deliberately leaky variant (label = "heavy user", defined from `assets_30d`, with `assets_30d` as an
  input) scores PR-AUC {m['leakage_demo']['leaky_pr_auc']:.2f} / ROC-AUC {m['leakage_demo']['leaky_roc_auc']:.2f}: near perfect, and meaningless.

## Split (time-based)
* Fit snapshots: {m['snapshots']['fit'][0]} to {m['snapshots']['fit'][-1]} ({m['rows']['fit']:,} rows).
* Validation (calibration, model selection, threshold): {', '.join(m['snapshots']['valid'])} ({m['rows']['valid']:,} rows).
* Hold-out test: {', '.join(m['snapshots']['test'])} ({m['rows']['test']:,} rows). Training label windows end before the first test snapshot (purged).

## Models compared
{__import__('src.analysis.run_all', fromlist=['md_table']).md_table(pd.DataFrame(rows), {c: (lambda v: f'{v:.4f}') for c in ['valid PR-AUC', 'test PR-AUC', 'test ROC-AUC', 'test Brier']})}

Selected by validation PR-AUC of the uncalibrated candidates: **{m['chosen']}** (isotonic calibration fitted on the validation fold).
Hold-out: PR-AUC {t['pr_auc']:.3f} (base rate {t['base_rate']:.3f}), ROC-AUC {t['roc_auc']:.3f}, Brier {t['brier']:.4f}. Top-decile lift {h['model_top_decile_lift']:.1f}x.

## Decision threshold: expected profit, not accuracy
Contacting a user costs EUR {a['contact_cost_eur']}, a nudge lifts conversion probability by {a['nudge_relative_lift']:.0%} (relative), and a new paying customer is worth EUR {a['conversion_value_eur']}
(all assumptions in `config/analysis.yaml`). Break-even precision is {m['break_even_precision']:.2%}. The threshold ({m['threshold']:.4f}) maximises expected profit on the validation fold;
on the hold-out it contacts {m['profit_test']['contacted']:,} of {m['profit_test']['of']:,} users and earns EUR {m['profit_test']['threshold_policy_eur']:,.0f}
(contacting everyone: EUR {m['profit_test']['contact_all_eur']:,.0f}).

## Top features (permutation importance, drop in PR-AUC)
{__import__('src.analysis.run_all', fromlist=['md_table']).md_table(imp, {'pr_auc_drop': lambda v: f'{v:.4f}'})}

## Outputs
`fact_user_scores` holds the score and decile of every scored user at the as-of snapshot (`{m['model_name']}`, version `{m['version']}`); the serialized model is written to `models/` (git-ignored).

## Limitations
* Synthetic data with a built-in relationship between engagement and upgrade; real behaviour will be noisier and drift.
* Few positives per snapshot ({m['rows']['valid']:,} validation rows): threshold and calibration are noisy.
* Profit numbers rest on invented assumptions; the *ordering* of policies is more reliable than the euro amounts.
* Association, not causation: the score says who is likely to convert, not who is *persuaded* by a nudge (that needs an uplift model or a randomised test).
* The model is not refit on the hold-out before scoring; a production setup would retrain on a schedule and monitor calibration drift.
"""


def update_readme(h: dict) -> None:
    path = ROOT / "README.md"
    if not path.exists():
        return
    txt = path.read_text(encoding="utf-8")
    p = lambda v: f"{v:.1%}"  # noqa: E731
    mrr = h["rec_mrr"]
    block = f"""<!-- RESULTS:START -->
*All figures below come from the synthetic run (`make all`) and describe a fictional company.*

| Question | Result (synthetic) |
|---|---|
| Paid acquisition | EUR {h['spend_eur']:,.0f} spend, {h['signups']:,} signups, blended cost per signup EUR {h['cost_per_signup']:.2f} |
| BR vs MX | signup rate p = {h['br_mx_signup_rate_p']:.2f}; cost per signup gap EUR {h['br_mx_cps_diff']:+.2f} (bootstrap 95% CI {h['br_mx_cps_ci'][0]:+.2f} to {h['br_mx_cps_ci'][1]:+.2f}) |
| Paid CAC vs signup cost | blended paid CAC EUR {h['paid_cac']:.0f} is ~{h['paid_cac'] / h['cost_per_signup']:.0f}x the cost per signup; they are different metrics |
| Unit economics | blended LTV/CAC {h['ltv_cac_blended']:.2f}x, payback {h['payback_months']:.1f} months; only {', '.join(h['countries_ge_3x']) or 'no country'} at or above 3x (best {h['best_country']} {h['best_ltv_cac']:.1f}x, worst {h['worst_country']} {h['worst_ltv_cac']:.1f}x) |
| Usage concentration | {p(h['pct_users_80_30d'])} of active users produce 80% of volume (30d); {p(h['pct_users_50_30d'])} produce 50% |
| Free-limit recommendation | {h['rec_type']} limit of {h['rec_value']:g} assets, affecting {p(h['rec_pct_affected'])} of active free users; expected incremental MRR EUR {mrr['low']:+,.0f} / {mrr['base']:+,.0f} / {mrr['high']:+,.0f} (low / base / high) - **assumption-driven** |
| Upgrade propensity | hold-out PR-AUC {h.get('model_pr_auc', float('nan')):.3f} vs base rate {h.get('model_base_rate', float('nan')):.3f}; top-decile lift {h.get('model_top_decile_lift', float('nan')):.1f}x; profit-optimal threshold contacts {p(h.get('model_contacted_share', 0))} of users |

Details: [docs/RESULTS.md](docs/RESULTS.md) and [docs/MODEL_CARD.md](docs/MODEL_CARD.md).
<!-- RESULTS:END -->"""
    new = re.sub(r"<!-- RESULTS:START -->.*?<!-- RESULTS:END -->", lambda _m: block, txt, flags=re.S)
    path.write_text(new, encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-images", action="store_true")
    args = ap.parse_args()
    con = connect(read_only=False)
    R = compute(con)
    h = headline(R)
    save_result(con, "headline", h)
    (ROOT / "reports").mkdir(exist_ok=True)
    (ROOT / "reports" / "headline.json").write_text(json.dumps(h, indent=2, default=float), encoding="utf-8")
    (ROOT / "docs" / "RESULTS.md").write_text(results_md(R, h), encoding="utf-8")
    if R["model"]:
        (ROOT / "docs" / "MODEL_CARD.md").write_text(model_card(R["model"], h), encoding="utf-8")
    update_readme(h)
    if not args.no_images:
        IMG.mkdir(parents=True, exist_ok=True)
        for name, fig in figures(R).items():
            export(fig, name)
    con.close()
    print("analysis complete:", json.dumps({k: (round(v, 3) if isinstance(v, float) else v) for k, v in h.items() if not isinstance(v, (dict, list))}, indent=1))


if __name__ == "__main__":
    main()
