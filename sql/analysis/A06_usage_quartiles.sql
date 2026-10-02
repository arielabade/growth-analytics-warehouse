-- id: A06
-- name: Usage quartiles
-- business_question: How much of total volume sits in each usage quartile (Q4 = heaviest 25% of users)?
-- tables: mart_usage_pareto
-- grain: one row per window x usage quartile
-- output: users, total_assets, share_of_volume, min/max assets per user
-- replaces: Notebooks 2 and 3 (quartiles of usage)
-- kind: analysis
SELECT window_days, usage_quartile, COUNT(*) AS users, SUM(total_assets) AS total_assets,
       SUM(total_assets) * 1.0 / SUM(SUM(total_assets)) OVER (PARTITION BY window_days) AS share_of_volume,
       MIN(total_assets) AS min_assets, MAX(total_assets) AS max_assets
FROM mart_usage_pareto
GROUP BY window_days, usage_quartile
ORDER BY window_days, usage_quartile;
