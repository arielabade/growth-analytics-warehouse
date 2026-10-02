-- id: R01
-- name: Daily insertions per user (reconstructed extraction)
-- business_question: Reconstruction of the extract that produced the per-user, per-day insertion dataset used by the usage notebooks.
-- tables: fact_user_daily_usage, dim_user, dim_date, v_as_of
-- grain: one row per user x active day in the trailing 90 days
-- output: user_id, usage_date, assets_inserted
-- replaces: Input dataset of notebooks 2 and 3 (daily insertions per user) - reconstructed against the core tables
-- kind: reconstructed
SELECT u.user_id, d.date AS usage_date, f.assets_inserted
FROM fact_user_daily_usage f
JOIN dim_user u ON u.user_key = f.user_key
JOIN dim_date d ON d.date_key = f.date_key
CROSS JOIN v_as_of a
WHERE d.date BETWEEN a.as_of_date - 89 AND a.as_of_date
ORDER BY u.user_id, d.date;
