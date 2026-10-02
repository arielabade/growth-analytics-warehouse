-- id: A09
-- name: Data-derived free-limit candidates (Q3 / P90 / P95)
-- business_question: Which daily and monthly caps do the quantiles of free-user behaviour suggest?
-- tables: mart_usage_pareto, fact_user_daily_usage, dim_date, mart_user_lifecycle, v_as_of
-- grain: one row per limit_type (daily | monthly) x statistic
-- output: candidate cap per statistic over currently-free active users in the trailing 30 days
-- replaces: Notebooks 2 and 3 (Q3 / P95 cap suggestions)
-- kind: analysis
WITH free AS (
    SELECT * FROM mart_usage_pareto WHERE window_days = 30 AND NOT is_paying_now
)
SELECT 'daily' AS limit_type, 'Q3 of max daily insertions' AS statistic, quantile_cont(max_daily_assets, 0.75) AS candidate FROM free
UNION ALL SELECT 'daily', 'P90 of max daily insertions', quantile_cont(max_daily_assets, 0.90) FROM free
UNION ALL SELECT 'daily', 'P95 of max daily insertions', quantile_cont(max_daily_assets, 0.95) FROM free
UNION ALL SELECT 'monthly', 'Q3 of 30d insertions', quantile_cont(total_assets, 0.75) FROM free
UNION ALL SELECT 'monthly', 'P90 of 30d insertions', quantile_cont(total_assets, 0.90) FROM free
UNION ALL SELECT 'monthly', 'P95 of 30d insertions', quantile_cont(total_assets, 0.95) FROM free;
