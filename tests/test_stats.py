import numpy as np
import pytest

from src.analysis import stats


def test_two_prop_ztest_known_value():
    r = stats.two_prop_ztest(50, 100, 40, 100)
    assert r["diff"] == pytest.approx(0.1)
    assert r["z"] == pytest.approx(1.4213, abs=1e-3) and r["p_value"] == pytest.approx(0.1552, abs=1e-3)


def test_holm_monotone_and_capped():
    adj = stats.holm([0.01, 0.04, 0.03])
    assert adj == pytest.approx([0.03, 0.06, 0.06]) and max(adj) <= 1


def test_bootstrap_ci_contains_estimate_and_is_seeded():
    num, den = np.array([10, 20, 30, 40.0]), np.array([100, 100, 100, 100.0])
    a = stats.bootstrap_ratio_ci(num, den, 500, seed=1)
    assert a == stats.bootstrap_ratio_ci(num, den, 500, seed=1)
    assert a[1] <= a[0] <= a[2] and a[0] == pytest.approx(0.25)


def test_poisson_ci():
    lo, hi = stats.poisson_ci(10)
    assert lo == pytest.approx(4.795, abs=0.01) and hi == pytest.approx(18.39, abs=0.02)


def test_freedman_diaconis():
    x = np.arange(1000.0)
    w, n = stats.freedman_diaconis_bins(x)
    assert w == pytest.approx(2 * 500 / 1000 ** (1 / 3), rel=0.01) and n >= 1


def test_kaplan_meier_hand_example():
    # durations 1,2,3 with the middle one censored: S(1)=2/3, S(3)=2/3*0 -> at t=3 one at risk, event => 0
    t, s = stats.kaplan_meier(np.array([1, 2, 3]), np.array([True, False, True]))
    assert t.tolist() == [0.0, 1.0, 3.0] and s == pytest.approx([1, 2 / 3, 0.0])
    assert stats.survival_at(t, s, 2) == pytest.approx(2 / 3)
