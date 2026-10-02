"""Data-quality checks (SYNTHETIC data). Each check returns (name, layer, status, details)."""
from __future__ import annotations

from typing import Callable

import duckdb

Result = tuple[str, str, str, str]
OPS_TABLES = ("pipeline_runs", "pipeline_run_tables", "data_quality_results", "warehouse_meta")


def _one(con, sql: str):
    return con.execute(sql).fetchone()[0]


def _status(violations: int) -> str:
    return "pass" if violations == 0 else "fail"


def constraint_checks(con) -> list[Result]:
    """PK uniqueness and FK integrity, generated from the catalog so new tables are covered automatically."""
    out: list[Result] = []
    rows = con.execute(
        "SELECT table_name, constraint_type, constraint_column_names, referenced_table, referenced_column_names "
        "FROM duckdb_constraints() WHERE constraint_type IN ('PRIMARY KEY','FOREIGN KEY') ORDER BY 1, 2").fetchall()
    for table, ctype, cols, ref_table, ref_cols in rows:
        if table in OPS_TABLES:
            continue
        if ctype == "PRIMARY KEY":
            tup = ", ".join(cols)
            n = _one(con, f"SELECT COUNT(*) - COUNT(DISTINCT ({tup})) FROM {table}")
            out.append((f"pk_unique:{table}", "core", _status(n), f"{n} duplicate key(s) on ({tup})"))
        else:
            cond = " AND ".join(f"c.{a} = p.{b}" for a, b in zip(cols, ref_cols))
            nn = " AND ".join(f"c.{a} IS NOT NULL" for a in cols)
            n = _one(con, f"SELECT COUNT(*) FROM {table} c LEFT JOIN {ref_table} p ON {cond} "
                          f"WHERE {nn} AND p.{ref_cols[0]} IS NULL")
            out.append((f"fk_integrity:{table}({','.join(cols)})->{ref_table}", "core", _status(n),
                        f"{n} orphan row(s)"))
    return out


def domain_checks(con) -> list[Result]:
    out: list[Result] = []
    n = _one(con, "SELECT COUNT(*) FROM fact_ad_performance WHERE spend_eur < 0")
    out.append(("non_negative_spend", "core", _status(n), f"{n} row(s) with negative spend"))

    n = _one(con, """SELECT COUNT(*) FROM fact_ad_performance
                     WHERE NOT (impressions >= link_clicks AND link_clicks >= landing_page_views
                                AND landing_page_views >= signups)""")
    out.append(("funnel_monotonicity", "core", _status(n),
                f"{n} row(s) violating impressions >= clicks >= landing views >= signups"))

    n = _one(con, "SELECT COUNT(*) FROM fact_ad_performance WHERE reach > impressions")
    out.append(("reach_not_above_impressions", "core", _status(n), f"{n} row(s) with reach > impressions"))

    asof = "(SELECT as_of_date FROM v_as_of)"
    for name, sql in {
        "ad_period_end": f"SELECT COUNT(*) FROM fact_ad_performance f JOIN dim_date d ON d.date_key = f.period_end_key WHERE d.date > {asof}",
        "usage_date": f"SELECT COUNT(*) FROM fact_user_daily_usage f JOIN dim_date d ON d.date_key = f.date_key WHERE d.date > {asof}",
        "event_date": f"SELECT COUNT(*) FROM fact_subscription_event f JOIN dim_date d ON d.date_key = f.event_date_key WHERE d.date > {asof}",
        "signup_date": f"SELECT COUNT(*) FROM dim_user u JOIN dim_date d ON d.date_key = u.signup_date_key WHERE d.date > {asof}",
    }.items():
        n = _one(con, sql)
        out.append((f"no_future_dates:{name}", "core", _status(n), f"{n} row(s) dated after as_of_date"))

    lag_usage = _one(con, f"SELECT date_diff('day', MAX(d.date), {asof}) FROM fact_user_daily_usage f JOIN dim_date d ON d.date_key = f.date_key")
    lag_ads = _one(con, f"SELECT date_diff('day', MAX(d.date), {asof}) FROM fact_ad_performance f JOIN dim_date d ON d.date_key = f.period_end_key")
    for name, lag in (("usage", lag_usage), ("ad_performance", lag_ads)):
        st = "pass" if lag <= 1 else ("warn" if lag <= 3 else "fail")
        out.append((f"freshness:{name}", "core", st, f"latest {name} data is {lag} day(s) before as_of_date"))

    n = _one(con, """SELECT COUNT(*) FROM (
        SELECT user_key, arg_min(event_type, event_ts) AS first_type FROM fact_subscription_event GROUP BY user_key)
        WHERE first_type <> 'signup'""")
    out.append(("events_start_with_signup", "core", _status(n), f"{n} user(s) whose first event is not a signup"))

    n = _one(con, """SELECT COUNT(*) FROM mart_user_lifecycle WHERE cancel_date IS NOT NULL AND
                     (first_upgrade_date IS NULL OR cancel_date < first_upgrade_date)""")
    out.append(("cancel_after_upgrade", "core", _status(n), f"{n} user(s) cancelling before/without upgrading"))
    return out


def reconciliation_checks(con, staging_info: dict) -> list[Result]:
    out: list[Result] = []
    pairs = [("stg_users", "dim_user"), ("stg_ad_performance", "fact_ad_performance"),
             ("stg_usage_daily", "fact_user_daily_usage"), ("stg_subscription_events", "fact_subscription_event")]
    for s, c in pairs:
        ns, nc = _one(con, f"SELECT COUNT(*) FROM staging.{s}"), _one(con, f"SELECT COUNT(*) FROM {c}")
        out.append((f"staging_to_core_rowcount:{c}", "core", "pass" if ns == nc else "fail",
                    f"staging={ns:,} core={nc:,} (a mismatch means a join silently dropped rows)"))
    o = staging_info.get("orphan_usage_rows", 0)
    out.append(("usage_rows_without_user", "staging", _status(o), f"{o} usage row(s) with no matching user"))

    paid_users = _one(con, "SELECT COUNT(*) FROM mart_user_lifecycle WHERE is_paid_source")
    signups = _one(con, "SELECT SUM(signups) FROM fact_ad_performance")
    gap = abs(signups - paid_users) / max(signups, 1)
    out.append(("ad_signups_vs_paid_source_users", "core", "pass" if gap <= 0.005 else "warn",
                f"ad signups={signups:,} vs paid-source users={paid_users:,} (gap {gap:.2%})"))

    n = _one(con, """SELECT COUNT(*) FROM staging.stg_users s JOIN dim_user u ON u.user_id = s.user_id
                     JOIN dim_plan p ON p.plan_key = u.current_plan_key WHERE p.plan_name <> s.raw_current_plan""")
    out.append(("raw_plan_matches_event_history", "core", "pass" if n == 0 else "warn",
                f"{n} user(s) whose exported plan differs from the plan derived from events"))
    return out


def mart_checks(con) -> list[Result]:
    out: list[Result] = []
    n = _one(con, """SELECT COUNT(*) FROM mart_funnel_country WHERE ctr NOT BETWEEN 0 AND 1
                     OR lpv_rate NOT BETWEEN 0 AND 1 OR signup_rate NOT BETWEEN 0 AND 1""")
    out.append(("mart_funnel_rates_in_unit_interval", "marts", _status(n), f"{n} row(s) with a rate outside [0,1]"))

    n = _one(con, """SELECT COUNT(*) FROM (SELECT window_days, MAX(cum_share_assets) AS m FROM mart_usage_pareto
                     GROUP BY window_days) WHERE abs(m - 1) > 1e-9""")
    out.append(("mart_pareto_cum_share_reaches_1", "marts", _status(n), f"{n} window(s) whose cumulative share != 100%"))

    n = _one(con, """SELECT COUNT(*) FROM (SELECT users_affected,
                     LAG(users_affected) OVER (PARTITION BY limit_type ORDER BY limit_value) AS prev
                     FROM mart_free_limit_simulation) WHERE prev IS NOT NULL AND users_affected > prev""")
    out.append(("mart_limit_affected_users_monotone", "marts", _status(n),
                f"{n} step(s) where a higher limit affects more users"))

    n = _one(con, """SELECT COUNT(*) FROM mart_user_features f JOIN mart_user_lifecycle l USING (user_key)
                     WHERE l.first_upgrade_date <= f.snapshot_date""")
    out.append(("mart_features_only_pre_upgrade_users", "marts", _status(n),
                f"{n} feature row(s) for users already paying at the snapshot"))

    for mart in ("mart_funnel_country", "mart_unit_economics_country_month", "mart_usage_pareto",
                 "mart_free_limit_simulation", "mart_retention_cohorts", "mart_user_features"):
        c = _one(con, f"SELECT COUNT(*) FROM {mart}")
        out.append((f"mart_not_empty:{mart}", "marts", "pass" if c > 0 else "fail", f"{c:,} row(s)"))
    return out


def run_checks(con: duckdb.DuckDBPyConnection, staging_info: dict) -> list[Result]:
    checks: list[Callable[[], list[Result]]] = [
        lambda: constraint_checks(con), lambda: domain_checks(con),
        lambda: reconciliation_checks(con, staging_info), lambda: mart_checks(con)]
    results: list[Result] = []
    for fn in checks:
        results.extend(fn())
    return results
