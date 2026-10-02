import numpy as np
import pandas as pd

from src.analysis import a4_limits as a4


def test_blocked_share_and_monetization():
    day = pd.DataFrame({"user_key": [1, 1, 2, 3], "country_code": ["BR", "BR", "US", "US"], "assets": [10, 30, 5, 100]})
    tot = a4.user_totals(day)
    g = a4.blocked_share(day, tot, 20, "daily")
    assert set(g.user_key) == {1, 3} and g.set_index("user_key").e.round(3).to_dict() == {1: 0.25, 3: 0.8}
    prices = pd.Series({"BR": 10.0, "US": 20.0})
    scen = {"conv_max": 0.5, "loss_prob": 0.1, "free_user_value_eur": 4.0}
    r = a4.monetization(day, tot, prices, 20, "daily", scen)
    assert np.isclose(r["mrr_gain"], 0.5 * 0.25 * 10 + 0.5 * 0.8 * 20)
    assert np.isclose(r["mrr_loss"], 0.1 * 2 * 4.0) and r["users_affected"] == 2
    m = a4.blocked_share(day, tot, 50, "monthly")      # totals: 40, 5, 100
    assert set(m.user_key) == {3}
