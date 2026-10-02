import numpy as np
import pandas as pd

from src.model import propensity as P


def test_time_split_purges_label_overlap(con):
    df = P.add_derived(P.load_features(con))
    sp = P.time_split(df, 3, 2)
    first_test = pd.Timestamp(sp["meta"]["test"][0])
    for s in sp["meta"]["fit"] + sp["meta"]["valid"]:
        assert pd.Timestamp(s) + pd.Timedelta(days=30) <= first_test
    assert set(sp["meta"]["fit"]).isdisjoint(sp["meta"]["valid"] + sp["meta"]["test"])


def test_lift_and_profit_helpers():
    rng = np.random.default_rng(0)
    p = rng.random(10_000)
    y = (rng.random(10_000) < p * 0.05).astype(int)
    lt = P.lift_table(y, p)
    assert lt.lift.iloc[0] > lt.lift.iloc[-1] and abs(lt.cum_capture.iloc[-1] - 1) < 1e-9
    pc = P.profit_curve(y, p, value=100, lift=0.5, cost=0.2)
    assert pc.profit_eur.max() > 0 > pc.profit_eur.iloc[0] or pc.profit_eur.max() >= pc.profit_eur.iloc[0]
    assert pc.contacted.is_monotonic_decreasing


def test_target_not_a_feature():
    assert "converted_next_30d" not in P.FEATURES
