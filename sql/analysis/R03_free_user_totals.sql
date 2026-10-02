-- id: R03
-- name: Free-user insertion totals (reconstructed extraction)
-- business_question: Reconstruction of the extract with total insertions per currently-free user, used for the free-user distribution and limit simulation.
-- tables: fact_user_daily_usage, dim_user, dim_plan, dim_plan_tier, dim_date, v_as_of
-- grain: one row per free user with usage in the trailing 90 days
-- output: user_id, signup_date_key, total_30d, total_90d, active_days_90d
-- replaces: Input dataset of notebook 3 (free-user totals) - reconstructed against the core tables
-- kind: reconstructed
SELECT u.user_id, u.signup_date_key,
       COALESCE(SUM(f.assets_inserted) FILTER (WHERE d.date > a.as_of_date - 30), 0) AS total_30d,
       SUM(f.assets_inserted) AS total_90d, COUNT(*) AS active_days_90d
FROM fact_user_daily_usage f
JOIN dim_user u ON u.user_key = f.user_key
JOIN dim_plan p ON p.plan_key = u.current_plan_key
JOIN dim_plan_tier t ON t.plan_tier_key = p.plan_tier_key
JOIN dim_date d ON d.date_key = f.date_key
CROSS JOIN v_as_of a
WHERE t.tier_name = 'free' AND d.date BETWEEN a.as_of_date - 89 AND a.as_of_date
GROUP BY u.user_id, u.signup_date_key
ORDER BY total_90d DESC;
