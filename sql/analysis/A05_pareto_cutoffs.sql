-- id: A05
-- name: Pareto cutoffs of usage volume
-- business_question: What share of active users produces 50/75/80/90/95% of inserted assets?
-- tables: mart_usage_pareto
-- grain: one row per window (30d, 90d) x volume cutoff
-- output: users_needed, pct_users_needed, active_users
-- replaces: Notebooks 2 and 3 (Pareto 80/20 of usage)
-- kind: analysis
WITH cuts AS (SELECT unnest([0.5, 0.75, 0.8, 0.9, 0.95]) AS cutoff)
SELECT p.window_days, c.cutoff,
       MIN(p.volume_rank) FILTER (WHERE p.cum_share_assets >= c.cutoff) AS users_needed,
       MAX(p.volume_rank) AS active_users,
       MIN(p.volume_rank) FILTER (WHERE p.cum_share_assets >= c.cutoff) * 1.0 / MAX(p.volume_rank) AS pct_users_needed
FROM mart_usage_pareto p CROSS JOIN cuts c
GROUP BY p.window_days, c.cutoff
ORDER BY p.window_days, c.cutoff;
