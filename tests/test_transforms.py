import numpy as np
import pandas as pd
import pytest

from src.pipeline import transforms as T


def test_split_period():
    s = pd.Series(["2025-01-01 - 2025-01-31", " 2025-02-01 - 2025-02-28 ", "bad", None])
    r = T.split_period(s)
    assert r.period_start.iloc[0] == pd.Timestamp("2025-01-01") and r.period_end.iloc[1] == pd.Timestamp("2025-02-28")
    assert r.period_start.iloc[2:].isna().all()


def test_normalize_email_case_and_alias():
    s = pd.Series(["  User000001+promo@Example.test", "user000001@example.test", "A.B+x+y@Example.test"])
    r = T.normalize_email(s).tolist()
    assert r[0] == r[1] == "user000001@example.test"
    assert r[2] == "a.b@example.test"


def test_coerce_numeric_decimal_comma():
    r = T.coerce_numeric(pd.Series(["1.234,56", "12,5", "7", "3.5", "x", None]))
    assert r.iloc[:4].tolist() == [1234.56, 12.5, 7.0, 3.5]
    assert r.iloc[4:].isna().all()


def test_drop_empty_rows_and_columns():
    df = pd.DataFrame({"a": ["1", "", "3"], "b": ["x", " ", "z"], "": ["", "", ""]})
    out = T.drop_empty(df)
    assert list(out.columns) == ["a", "b"] and len(out) == 2


def test_dedupe_and_consolidate():
    df = pd.DataFrame({"u": ["a", "a", "a", "b"], "d": ["d1", "d1", "d2", "d1"], "n": [2, 2, 3, 5]})
    d = T.dedupe_exact(df)
    assert len(d) == 3
    c = T.consolidate_user_day(pd.DataFrame({"u": ["a", "a"], "d": ["d1", "d1"], "n": [2, 3]}), "u", "d", "n")
    assert c.n.tolist() == [5]


def test_window_bounds_relative_to_as_of():
    s, e = T.window_bounds("2026-06-30", 30)
    assert e == pd.Timestamp("2026-06-30") and s == pd.Timestamp("2026-06-01")
    d = pd.Series(pd.to_datetime(["2026-05-31", "2026-06-01", "2026-06-30", "2026-07-01"]))
    assert T.in_window(d, "2026-06-30", 30).tolist() == [False, True, True, False]


def test_normalize_to_monthly_and_cohort():
    assert T.normalize_to_monthly(90, 90) == 30 and T.normalize_to_monthly(180, 90) == 60
    df = pd.DataFrame({"signup": ["2023-12-31", "2024-01-01", "2025-05-05"]})
    assert len(T.filter_cohort(df, "signup", 2024)) == 2


def test_ratio_of_sums_differs_from_mean_of_ratios():
    df = pd.DataFrame({"k": [1, 1], "spend_eur": [1.0, 100.0], "impressions": [100, 10_000_000], "reach": [90, 9_000_000],
                       "link_clicks": [50, 100_000], "landing_page_views": [40, 80_000], "signups": [4, 800]})
    r = T.sum_then_ratio(df, ["k"]).iloc[0]
    assert r.ctr == pytest.approx(100_050 / 10_000_100)
    naive = (df.link_clicks / df.impressions).mean()
    assert abs(r.ctr - naive) > 0.1          # the naive average is wildly off
    assert r.cost_per_signup == pytest.approx(101 / 804)
    assert r.cpm == pytest.approx(101 / 10_000_100 * 1000)


def test_safe_div_zero():
    assert np.isnan(T.safe_div(1, 0))
