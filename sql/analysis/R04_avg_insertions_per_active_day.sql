-- id: R04
-- name: Average insertions per active day, free users (reconstructed extraction)
-- business_question: Reconstruction of the extract giving each free user's average insertions on the days they were active.
-- tables: fact_user_daily_usage, dim_user, dim_plan, dim_plan_tier, dim_date, v_as_of
-- grain: one row per free user with usage in the trailing 30 days
-- output: user_id, active_days, total_assets, avg_assets_per_active_day
-- replaces: Input dataset of notebook 3 (average per active day) - reconstructed against the core tables
-- kind: reconstructed
SELECT u.user_id, COUNT(*) AS active_days, SUM(f.assets_inserted) AS total_assets,
       SUM(f.assets_inserted) * 1.0 / COUNT(*) AS avg_assets_per_active_day
FROM fact_user_daily_usage f
JOIN dim_user u ON u.user_key = f.user_key
JOIN dim_plan p ON p.plan_key = u.current_plan_key
JOIN dim_plan_tier t ON t.plan_tier_key = p.plan_tier_key
JOIN dim_date d ON d.date_key = f.date_key
CROSS JOIN v_as_of a
WHERE t.tier_name = 'free' AND d.date BETWEEN a.as_of_date - 29 AND a.as_of_date
GROUP BY u.user_id
ORDER BY avg_assets_per_active_day DESC;
