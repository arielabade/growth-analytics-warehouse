"""A6. Upgrade-propensity model (SYNTHETIC data).

Target : the user converts free -> paid in the NEXT 30 days after a month-end snapshot.
Features: usage during the PRIOR 30/60 days only (built in sql/marts/080_mart_user_features.sql).
Split  : by time. Test = most recent labelled snapshots; the training set is purged so that no training
         label window overlaps a test snapshot; the last training snapshots form a validation fold used
         for calibration, model selection and the decision threshold.
Decision threshold: maximises expected profit (not accuracy).
"""
from __future__ import annotations

import json
from datetime import datetime

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, log_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder, StandardScaler

from src.analysis.common import ROOT, analysis_cfg, save_result

NUM = ["assets_30d", "active_days_30d", "max_daily_assets_30d", "assets_prev30d", "active_days_prev30d",
       "days_since_last_use", "tenure_days", "avg_assets_per_active_day"]
CAT = ["country_code", "source_name"]
MODEL_NAME, MODEL_VERSION = "upgrade_propensity_30d", "v1"
MODEL_PATH = ROOT / "models" / f"propensity_{MODEL_VERSION}.joblib"


def load_features(con) -> pd.DataFrame:
    df = con.execute("SELECT * FROM mart_user_features").df()
    df["snapshot_date"] = pd.to_datetime(df.snapshot_date)
    df["avg_assets_per_active_day"] = df.avg_assets_per_active_day.fillna(0.0)
    return df


def add_derived(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["trend_log_ratio"] = np.log1p(out.assets_30d) - np.log1p(out.assets_prev30d)
    return out


FEATURES = NUM + ["trend_log_ratio"] + CAT


def _preprocessor() -> ColumnTransformer:
    num = Pipeline([("log", FunctionTransformer(np.log1p, validate=False, feature_names_out="one-to-one")), ("scale", StandardScaler())])
    return ColumnTransformer([
        ("log_num", num, NUM),
        ("trend", "passthrough", ["trend_log_ratio"]),
        ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CAT)])


def make_models(seed: int) -> dict[str, Pipeline]:
    return {
        "logistic_regression": Pipeline([("prep", _preprocessor()), ("clf", LogisticRegression(max_iter=1000, C=1.0))]),
        "gradient_boosting": Pipeline([("prep", _preprocessor()), ("clf", HistGradientBoostingClassifier(
            max_depth=4, learning_rate=0.06, max_iter=250, l2_regularization=1.0, early_stopping=False, random_state=seed))]),
    }


def time_split(df: pd.DataFrame, n_test: int, n_calib: int) -> dict[str, pd.DataFrame]:
    """Labelled snapshots only; purge train so label windows (snapshot+30d) end before the first test snapshot."""
    lab = df[df.label_available]
    snaps = sorted(lab.snapshot_date.unique())
    test_snaps = snaps[-n_test:]
    first_test = test_snaps[0]
    train_snaps = [s for s in snaps[:-n_test] if s + pd.Timedelta(days=30) <= first_test]
    calib_snaps, fit_snaps = train_snaps[-n_calib:], train_snaps[:-n_calib]
    pick = lambda ss: lab[lab.snapshot_date.isin(ss)]  # noqa: E731
    return {"fit": pick(fit_snaps), "valid": pick(calib_snaps), "test": pick(test_snaps),
            "meta": {"fit": [str(pd.Timestamp(s).date()) for s in fit_snaps],
                     "valid": [str(pd.Timestamp(s).date()) for s in calib_snaps],
                     "test": [str(pd.Timestamp(s).date()) for s in test_snaps]}}


def metrics(y, p) -> dict:
    return {"pr_auc": float(average_precision_score(y, p)), "roc_auc": float(roc_auc_score(y, p)),
            "brier": float(brier_score_loss(y, p)), "log_loss": float(log_loss(y, np.clip(p, 1e-6, 1 - 1e-6))),
            "base_rate": float(np.mean(y)), "n": int(len(y)), "positives": int(np.sum(y))}


def lift_table(y: np.ndarray, p: np.ndarray) -> pd.DataFrame:
    """Deciles by score (10 = highest) with rate, lift over base rate and cumulative capture of converters."""
    d = pd.DataFrame({"y": y.astype(int), "p": p})
    d["decile"] = 10 - pd.qcut(d.p.rank(method="first"), 10, labels=False)
    t = d.groupby("decile").agg(users=("y", "size"), converters=("y", "sum"), avg_score=("p", "mean")).sort_index()
    base = d.y.mean()
    t["conversion_rate"] = t.converters / t.users
    t["lift"] = t.conversion_rate / base
    t["cum_capture"] = t.converters.cumsum() / t.converters.sum()
    return t.reset_index()


def calibration_table(y: np.ndarray, p: np.ndarray, bins: int = 10) -> pd.DataFrame:
    d = pd.DataFrame({"y": y.astype(int), "p": p})
    d["bin"] = pd.qcut(d.p.rank(method="first"), bins, labels=False)
    return d.groupby("bin").agg(mean_predicted=("p", "mean"), observed_rate=("y", "mean"), users=("y", "size")).reset_index()


def profit_curve(y: np.ndarray, p: np.ndarray, value: float, lift: float, cost: float,
                 thresholds: np.ndarray | None = None) -> pd.DataFrame:
    """Expected profit of contacting every user with score >= t.
    profit(t) = sum over contacted of (lift * value * y_i - cost). Break-even precision = cost / (lift * value)."""
    if thresholds is None:
        thresholds = np.unique(np.quantile(p, np.linspace(0, 0.999, 300)))
    rows = []
    for t in thresholds:
        m = p >= t
        contacted, conv = int(m.sum()), int(y[m].sum())
        rows.append({"threshold": float(t), "contacted": contacted, "converters_reached": conv,
                     "precision": conv / contacted if contacted else 0.0,
                     "profit_eur": float(lift * value * conv - cost * contacted)})
    return pd.DataFrame(rows)


def leakage_demo(df: pd.DataFrame, seed: int) -> dict:
    """What the old approach would show: the target is defined from a feature that is also a model input."""
    d = add_derived(df[df.label_available])
    cut = d.assets_30d.quantile(0.95)
    y = (d.assets_30d >= cut).astype(int)           # "heavy user" defined from assets_30d ...
    snaps = sorted(d.snapshot_date.unique())
    tr, te = d.snapshot_date.isin(snaps[:-3]), d.snapshot_date.isin(snaps[-3:])
    m = make_models(seed)["logistic_regression"].fit(d[tr][FEATURES], y[tr])  # ... and assets_30d is a feature
    p = m.predict_proba(d[te][FEATURES])[:, 1]
    honest = None
    return {"leaky_target": "assets_30d >= P95 (feature used to define the label)",
            "leaky_pr_auc": float(average_precision_score(y[te], p)), "leaky_roc_auc": float(roc_auc_score(y[te], p)),
            "honest_pr_auc_reference": honest}


def train_and_score(con, cfg: dict | None = None) -> dict:
    """Train both models, select on the validation fold, evaluate on the hold-out, write scores and results."""
    cfg = cfg or analysis_cfg()
    pc = cfg["propensity"]
    seed = pc["seed"]
    df = add_derived(load_features(con))
    sp = time_split(df, pc["test_snapshots"], pc["calibration_snapshots"])
    fit, valid, test = sp["fit"], sp["valid"], sp["test"]
    Xf, yf = fit[FEATURES], fit.converted_next_30d.astype(int).to_numpy()
    Xv, yv = valid[FEATURES], valid.converted_next_30d.astype(int).to_numpy()
    Xt, yt = test[FEATURES], test.converted_next_30d.astype(int).to_numpy()

    models = {k: m.fit(Xf, yf) for k, m in make_models(seed).items()}
    iso = {k: IsotonicRegression(out_of_bounds="clip", y_min=0, y_max=1).fit(m.predict_proba(Xv)[:, 1], yv)
           for k, m in models.items()}

    def predict(name: str, X, calibrated: bool) -> np.ndarray:
        p = models[name].predict_proba(X)[:, 1]
        return np.clip(iso[name].predict(p), 1e-5, 1) if calibrated else p

    variants = {"logistic_regression": ("logistic_regression", False), "gradient_boosting": ("gradient_boosting", False),
                "gradient_boosting_calibrated": ("gradient_boosting", True)}
    comp = {}
    for label, (name, cal) in variants.items():
        comp[label] = {"validation": metrics(yv, predict(name, Xv, cal)), "test": metrics(yt, predict(name, Xt, cal))}
    # NOTE: the isotonic map is fitted on the validation fold, so its "validation" row is optimistic by construction.
    # Selection therefore uses the two UNCALIBRATED candidates' validation PR-AUC (rank is unchanged by calibration).
    chosen_base = max(("logistic_regression", "gradient_boosting"), key=lambda k: comp[k]["validation"]["pr_auc"])
    chosen_label = chosen_base if chosen_base == "logistic_regression" else "gradient_boosting_calibrated"
    name, cal = variants[chosen_label]

    pv, pt = predict(name, Xv, cal), predict(name, Xt, cal)
    val_curve = profit_curve(yv, pv, pc["conversion_value_eur"], pc["nudge_relative_lift"], pc["contact_cost_eur"])
    best = val_curve.sort_values("profit_eur", ascending=False).iloc[0]
    threshold = float(best.threshold) if best.profit_eur > 0 else float("inf")
    test_curve = profit_curve(yt, pt, pc["conversion_value_eur"], pc["nudge_relative_lift"], pc["contact_cost_eur"])
    m = pt >= threshold
    contacted, reached = int(m.sum()), int(yt[m].sum())
    profit_test = pc["nudge_relative_lift"] * pc["conversion_value_eur"] * reached - pc["contact_cost_eur"] * contacted
    contact_all = pc["nudge_relative_lift"] * pc["conversion_value_eur"] * yt.sum() - pc["contact_cost_eur"] * len(yt)
    breakeven = pc["contact_cost_eur"] / (pc["nudge_relative_lift"] * pc["conversion_value_eur"])

    # permutation importance on a test subsample (PR-AUC drop)
    rng = np.random.default_rng(seed)
    sub = rng.choice(len(Xt), size=min(40000, len(Xt)), replace=False)
    pi = permutation_importance(models[name], Xt.iloc[sub], yt[sub], scoring="average_precision", n_repeats=3,
                                random_state=seed, n_jobs=1)
    imp = pd.DataFrame({"feature": FEATURES, "pr_auc_drop": pi.importances_mean}).sort_values("pr_auc_drop", ascending=False)

    # score the as_of snapshot (labels unavailable) and persist to fact_user_scores
    asof = df[~df.label_available & (df.snapshot_date == df.snapshot_date.max())]
    s = predict(name, asof[FEATURES], cal)
    scored = pd.DataFrame({"user_key": asof.user_key.to_numpy(), "score": s})
    scored["score_decile"] = (pd.qcut(scored.score.rank(method="first"), 10, labels=False) + 1).astype(int)
    scoring_key = int(asof.snapshot_date.iloc[0].strftime("%Y%m%d"))
    scored["scoring_date_key"] = scoring_key
    scored["model_name"], scored["model_version"] = MODEL_NAME, MODEL_VERSION
    con.execute("DELETE FROM fact_user_scores")
    con.register("_scores", scored)
    con.execute("INSERT INTO fact_user_scores SELECT user_key, scoring_date_key, model_name, model_version, score, "
                "score_decile FROM _scores")
    con.unregister("_scores")

    MODEL_PATH.parent.mkdir(exist_ok=True)
    joblib.dump({"model": models[name], "isotonic": iso[name] if cal else None, "features": FEATURES,
                 "threshold": threshold, "version": MODEL_VERSION}, MODEL_PATH)

    result = {
        "model_name": MODEL_NAME, "version": MODEL_VERSION, "trained_at": datetime.now().isoformat(timespec="seconds"),
        "chosen": chosen_label, "snapshots": sp["meta"],
        "rows": {"fit": len(fit), "valid": len(valid), "test": len(test), "scored_now": len(scored)},
        "comparison": comp, "threshold": threshold, "break_even_precision": breakeven,
        "assumptions": {k: pc[k] for k in ("conversion_value_eur", "nudge_relative_lift", "contact_cost_eur")},
        "profit_test": {"threshold_policy_eur": float(profit_test), "contact_all_eur": float(contact_all),
                        "contacted": contacted, "of": int(len(yt)), "converters_reached": reached,
                        "converters_total": int(yt.sum())},
        "lift_table": lift_table(yt, pt).to_dict("records"),
        "calibration": {"calibrated_gb_or_lr": calibration_table(yt, pt).to_dict("records"),
                        "raw_gb": calibration_table(yt, predict("gradient_boosting", Xt, False)).to_dict("records")},
        "profit_curve_test": test_curve.iloc[::6].to_dict("records"),
        "importance": imp.to_dict("records"),
        "leakage_demo": leakage_demo(df, seed),
    }
    if chosen_label == "logistic_regression":
        names = models[name].named_steps["prep"].get_feature_names_out()
        coef = models[name].named_steps["clf"].coef_[0]
        result["coefficients"] = pd.DataFrame({"feature": names, "coef": coef}).sort_values("coef", key=abs, ascending=False).head(15).to_dict("records")
    save_result(con, "propensity", result)
    return result


def main() -> None:
    from src.analysis.common import connect

    con = connect(read_only=False)
    r = train_and_score(con)
    t = r["comparison"][r["chosen"]]["test"]
    print(json.dumps({"chosen": r["chosen"], "test": t, "threshold": r["threshold"],
                      "profit_test": r["profit_test"], "scored_now": r["rows"]["scored_now"]}, indent=2))
    con.close()


if __name__ == "__main__":
    main()
