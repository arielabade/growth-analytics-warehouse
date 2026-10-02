-- id: A14
-- name: Activity durations for free-user survival curves
-- business_question: How long after signup do users stay active? (inactive for 14+ days = churned)
-- tables: mart_user_lifecycle, fact_user_daily_usage, dim_date, v_as_of
-- grain: one row per user with at least one usage day
-- output: country_code, duration_days (signup -> last usage day), churned flag (last usage more than 14 days before as_of)
-- replaces: Notebook 3 (monthly churn by country) - activity survival view
-- kind: analysis
WITH last_use AS (
    SELECT f.user_key, MAX(d.date) AS last_use_date
    FROM fact_user_daily_usage f JOIN dim_date d ON d.date_key = f.date_key GROUP BY f.user_key
)
SELECT l.user_key, l.country_code,
       date_diff('day', l.signup_date, u.last_use_date) AS duration_days,
       u.last_use_date < a.as_of_date - 14 AS churned
FROM mart_user_lifecycle l
JOIN last_use u ON u.user_key = l.user_key
CROSS JOIN v_as_of a;
