"""Small, dependency-light statistics helpers (all unit-tested). Data is SYNTHETIC."""
from __future__ import annotations

import math

import numpy as np
from scipy import stats as sps


def two_prop_ztest(x1: int, n1: int, x2: int, n2: int) -> dict:
    """Two-sided pooled two-proportion z-test; also returns the difference and its unpooled 95% CI."""
    p1, p2 = x1 / n1, x2 / n2
    pooled = (x1 + x2) / (n1 + n2)
    se0 = math.sqrt(pooled * (1 - pooled) * (1 / n1 + 1 / n2))
    z = (p1 - p2) / se0 if se0 > 0 else 0.0
    p = 2 * (1 - sps.norm.cdf(abs(z)))
    se = math.sqrt(p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2)
    return {"p1": p1, "p2": p2, "diff": p1 - p2, "z": z, "p_value": p,
            "ci_low": p1 - p2 - 1.96 * se, "ci_high": p1 - p2 + 1.96 * se}


def holm(pvalues: list[float]) -> list[float]:
    """Holm-Bonferroni adjusted p-values (same order as input)."""
    m = len(pvalues)
    order = np.argsort(pvalues)
    adj = np.empty(m)
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, (m - rank) * pvalues[i])
        adj[i] = min(1.0, running)
    return adj.tolist()


def bootstrap_ratio_ci(num: np.ndarray, den: np.ndarray, n_boot: int = 2000, seed: int = 7,
                       alpha: float = 0.05) -> tuple[float, float, float]:
    """Percentile CI of sum(num)/sum(den), resampling rows (a ratio of sums, not a mean of ratios)."""
    rng = np.random.default_rng(seed)
    num, den = np.asarray(num, float), np.asarray(den, float)
    idx = rng.integers(0, len(num), size=(n_boot, len(num)))
    ratios = num[idx].sum(1) / den[idx].sum(1)
    lo, hi = np.quantile(ratios, [alpha / 2, 1 - alpha / 2])
    return float(num.sum() / den.sum()), float(lo), float(hi)


def bootstrap_ratio_diff_ci(num1, den1, num2, den2, n_boot: int = 2000, seed: int = 7,
                            alpha: float = 0.05) -> tuple[float, float, float]:
    """Percentile CI of ratio1 - ratio2 with independent row resampling in each group."""
    rng = np.random.default_rng(seed)
    n1, d1, n2, d2 = (np.asarray(a, float) for a in (num1, den1, num2, den2))
    i1 = rng.integers(0, len(n1), size=(n_boot, len(n1)))
    i2 = rng.integers(0, len(n2), size=(n_boot, len(n2)))
    diff = n1[i1].sum(1) / d1[i1].sum(1) - n2[i2].sum(1) / d2[i2].sum(1)
    lo, hi = np.quantile(diff, [alpha / 2, 1 - alpha / 2])
    return float(n1.sum() / d1.sum() - n2.sum() / d2.sum()), float(lo), float(hi)


def poisson_ci(k: int, alpha: float = 0.05) -> tuple[float, float]:
    """Exact (Garwood) confidence interval for a Poisson count."""
    lo = 0.0 if k == 0 else sps.chi2.ppf(alpha / 2, 2 * k) / 2
    hi = sps.chi2.ppf(1 - alpha / 2, 2 * (k + 1)) / 2
    return float(lo), float(hi)


def freedman_diaconis_bins(x: np.ndarray) -> tuple[float, int]:
    """Freedman-Diaconis bin width 2*IQR/n^(1/3) and the implied number of bins."""
    x = np.asarray(x, float)
    q1, q3 = np.quantile(x, [0.25, 0.75])
    width = 2 * (q3 - q1) / len(x) ** (1 / 3)
    if width <= 0:
        return 0.0, 1
    return float(width), int(math.ceil((x.max() - x.min()) / width))


def kaplan_meier(durations: np.ndarray, events: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Kaplan-Meier survival estimate. Returns (times, survival) including t=0."""
    durations = np.asarray(durations, float)
    events = np.asarray(events, bool)
    times = np.unique(durations[events])
    surv, s = [1.0], 1.0
    for t in times:
        at_risk = (durations >= t).sum()
        d = ((durations == t) & events).sum()
        s *= 1 - d / at_risk
        surv.append(s)
    return np.concatenate([[0.0], times]), np.array(surv)


def survival_at(times: np.ndarray, surv: np.ndarray, t: float) -> float:
    """Step-function value of a KM curve at time t."""
    i = np.searchsorted(times, t, side="right") - 1
    return float(surv[max(i, 0)])
