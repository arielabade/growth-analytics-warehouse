-- id: R02
-- name: Heavy users in 30d and 90d windows (reconstructed extraction)
-- business_question: Reconstruction of the extract listing users whose volume is at or above the 95th percentile in each window.
-- tables: fact_user_daily_usage, dim_user, dim_date, v_as_of
-- grain: one row per window x heavy user
-- output: window_days, user_id, total_assets, active_days, p95_threshold
-- replaces: Input dataset of notebook 2 (heavy users, 30d and 90d) - reconstructed against the core tables
-- kind: reconstructed
WITH win AS (SELECT w.window_days, a.as_of_date FROM (VALUES (30), (90)) AS w(window_days) CROSS JOIN v_as_of a),
tot AS (
    SELECT w.window_days, f.user_key, SUM(f.assets_inserted) AS total_assets, COUNT(*) AS active_days
    FROM fact_user_daily_usage f JOIN dim_date d ON d.date_key = f.date_key
    JOIN win w ON d.date BETWEEN w.as_of_date - CAST(w.window_days - 1 AS INTEGER) AND w.as_of_date
    GROUP BY w.window_days, f.user_key
),
thr AS (SELECT window_days, quantile_cont(total_assets, 0.95) AS p95_threshold FROM tot GROUP BY window_days)
SELECT t.window_days, u.user_id, t.total_assets, t.active_days, thr.p95_threshold
FROM tot t JOIN thr ON thr.window_days = t.window_days
JOIN dim_user u ON u.user_key = t.user_key
WHERE t.total_assets >= thr.p95_threshold
ORDER BY t.window_days, t.total_assets DESC;
