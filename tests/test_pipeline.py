import duckdb
import pandas as pd
import pytest

from src.generate.config import load_config
from src.generate.simulate import simulate
from src.pipeline.run import CORE_TABLES, MARTS, run_pipeline
from src.pipeline.sqlio import catalog, parse_header, run_query


def test_generator_is_deterministic():
    cfg = load_config(profile="small")
    a, b = simulate(cfg), simulate(cfg)
    pd.testing.assert_frame_equal(a.ads, b.ads)
    pd.testing.assert_frame_equal(a.usage, b.usage)


def test_pipeline_succeeds_and_checks_pass(built):
    assert built["res"]["status"] in ("success", "success_with_warnings"), built["res"]["failed"]
    assert not built["res"]["failed"]


def test_cleaning_preserves_ground_truth(built, con):
    t = simulate(built["cfg"])
    assert con.execute("SELECT COUNT(*) FROM dim_user").fetchone()[0] == len(t.users)
    assert con.execute("SELECT SUM(assets_inserted) FROM fact_user_daily_usage").fetchone()[0] == t.usage.assets_inserted.sum()
    assert abs(con.execute("SELECT SUM(spend_eur) FROM fact_ad_performance").fetchone()[0] - t.ads.spend_eur.sum()) < 0.5


def test_alias_accounts_merged(con):
    assert con.execute("SELECT COUNT(*) FROM dim_user WHERE n_raw_accounts > 1").fetchone()[0] > 0


def test_idempotent_core(built, tmp_path):
    db = tmp_path / "again.duckdb"
    run_pipeline(db_path=db, raw_dir=built["raw"], cfg=built["cfg"])
    first = run_pipeline(db_path=db, raw_dir=built["raw"], cfg=built["cfg"])   # second run on the same file
    a = duckdb.connect(str(built["db"]), read_only=True)
    b = duckdb.connect(str(db), read_only=True)
    for t in [x for x in CORE_TABLES if x != "fact_user_scores"]:
        q = f"SELECT * FROM {t} ORDER BY ALL"
        pd.testing.assert_frame_equal(a.execute(q).df(), b.execute(q).df(), check_dtype=False)
    assert b.execute("SELECT COUNT(*) FROM pipeline_runs").fetchone()[0] == 2     # history is kept
    assert first["status"] != "failed"


def test_dq_table_populated(con):
    n = con.execute("SELECT COUNT(*) FROM data_quality_results").fetchone()[0]
    assert n >= 50
    cols = {r[0] for r in con.execute("SELECT column_name FROM information_schema.columns WHERE table_name='pipeline_runs'").fetchall()}
    assert {"run_id", "started_at", "finished_at", "status", "raw_rows", "staging_rows", "core_rows", "mart_rows"} <= cols


def test_dq_detects_bad_data(built, tmp_path):
    from src.pipeline import quality

    db = tmp_path / "bad.duckdb"
    con = duckdb.connect(str(db))
    run_pipeline(db_path=db, raw_dir=built["raw"], cfg=built["cfg"])
    con.close()
    con = duckdb.connect(str(db))
    con.execute("ALTER TABLE fact_ad_performance DROP CONSTRAINT IF EXISTS x") if False else None
    # bypass CHECK constraints by building a mutated copy of the table without them
    con.execute("CREATE TABLE _ads AS SELECT * FROM fact_ad_performance")
    con.execute("UPDATE _ads SET spend_eur = -5, landing_page_views = link_clicks + 1 WHERE rowid = 0")
    con.execute("DROP VIEW IF EXISTS mart_funnel_country")
    con.execute("DROP VIEW IF EXISTS mart_unit_economics_country_month")
    con.execute("DROP TABLE fact_ad_performance")
    con.execute("ALTER TABLE _ads RENAME TO fact_ad_performance")
    res = {r[0]: r[2] for r in quality.domain_checks(con)}
    assert res["non_negative_spend"] == "fail" and res["funnel_monotonicity"] == "fail"
    con.close()


def test_no_current_date_in_sql():
    for q in catalog():
        low = "\n".join(ln for ln in q["sql"].lower().splitlines() if not ln.strip().startswith("--"))
        assert "current_date" not in low and "now()" not in low and "today()" not in low, q["path"]


def test_every_sql_file_has_header():
    for q in catalog():
        for k in ("id", "name", "business_question", "tables", "grain", "output"):
            assert q.get(k), f"{q['path']} missing header field {k}"
    assert parse_header("-- id: X\n-- name: n\n--   more\nSELECT 1")["name"] == "n more"


def test_all_queries_and_marts_run(con):
    for q in catalog():
        if q["folder"] == "analysis":
            df = run_query(con, q["id"])
            assert len(df) > 0, q["id"]
    for m in MARTS:
        assert con.execute(f"SELECT COUNT(*) FROM {m}").fetchone()[0] > 0, m


def test_funnel_mart_matches_sum_of_ratios_rule(con):
    r = con.execute("""SELECT SUM(link_clicks) * 1.0 / SUM(impressions), SUM(spend_eur) / SUM(signups) FROM mart_funnel_country""").fetchone()
    f = con.execute("SELECT SUM(link_clicks) * 1.0 / SUM(impressions), SUM(spend_eur) / SUM(signups) FROM fact_ad_performance").fetchone()
    assert r == pytest.approx(f)


def test_pareto_and_limit_sanity(con):
    mx = con.execute("SELECT MAX(cum_share_assets) FROM mart_usage_pareto WHERE window_days = 30").fetchone()[0]
    assert abs(mx - 1) < 1e-9
    d = con.execute("SELECT users_affected FROM mart_free_limit_simulation WHERE limit_type='daily' ORDER BY limit_value").df().users_affected
    assert d.is_monotonic_decreasing


def test_features_have_no_leakage(con):
    # features must be computed from days <= snapshot: users already paying at the snapshot are excluded
    n = con.execute("""SELECT COUNT(*) FROM mart_user_features f JOIN mart_user_lifecycle l USING (user_key)
                       WHERE l.first_upgrade_date <= f.snapshot_date""").fetchone()[0]
    assert n == 0
    # the label only looks forward
    bad = con.execute("""SELECT COUNT(*) FROM mart_user_features f JOIN mart_user_lifecycle l USING (user_key)
                         WHERE f.converted_next_30d AND NOT (l.first_upgrade_date > f.snapshot_date
                         AND l.first_upgrade_date <= f.snapshot_date + 30)""").fetchone()[0]
    assert bad == 0
