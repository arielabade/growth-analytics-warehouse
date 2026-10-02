-- id: A07
-- name: Usage distribution and IQR long-tail test
-- business_question: How long is the tail of per-user volume, overall and by country?
-- tables: mart_usage_pareto
-- grain: one row per window x country (plus ALL)
-- output: q1, median, q3, p95, p99, max, iqr, upper_fence (Q3 + 1.5 IQR), users and share of volume beyond the fence
-- replaces: Notebook 3 (IQR long-tail analysis of free-user insertions)
-- kind: analysis
WITH s AS (
    SELECT window_days, COALESCE(country_code, 'ALL') AS country_code,
           COUNT(*) AS users,
           quantile_cont(total_assets, 0.25) AS q1, quantile_cont(total_assets, 0.5) AS median,
           quantile_cont(total_assets, 0.75) AS q3, quantile_cont(total_assets, 0.95) AS p95,
           quantile_cont(total_assets, 0.99) AS p99, MAX(total_assets) AS max_assets, AVG(total_assets) AS mean_assets
    FROM mart_usage_pareto
    GROUP BY GROUPING SETS ((window_days), (window_days, country_code))
)
SELECT s.*, s.q3 - s.q1 AS iqr, s.q3 + 1.5 * (s.q3 - s.q1) AS upper_fence,
       (SELECT COUNT(*) FROM mart_usage_pareto p WHERE p.window_days = s.window_days
          AND (s.country_code = 'ALL' OR p.country_code = s.country_code)
          AND p.total_assets > s.q3 + 1.5 * (s.q3 - s.q1)) AS users_beyond_fence,
       (SELECT SUM(p.total_assets) FILTER (WHERE p.total_assets > s.q3 + 1.5 * (s.q3 - s.q1)) * 1.0 / SUM(p.total_assets)
          FROM mart_usage_pareto p WHERE p.window_days = s.window_days
          AND (s.country_code = 'ALL' OR p.country_code = s.country_code)) AS volume_share_beyond_fence
FROM s
ORDER BY s.window_days, s.country_code;
