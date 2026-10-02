-- id: M070
-- name: mart_retention_cohorts
-- business_question: Of the users who signed up in a month, how many are still active (and how many are paying) k months later?
-- tables: mart_user_lifecycle, fact_user_daily_usage, dim_date, dim_month, mart_subscription_history, v_as_of
-- grain: one row per signup cohort month x country x months_since_signup
-- output: cohort_size, active_users, paying_users, active_retention, paying_share
-- replaces: Notebook 3 (monthly churn by country; extended to a cohort triangle)
-- kind: mart
CREATE OR REPLACE VIEW mart_retention_cohorts AS
WITH ms AS (SELECT month_key, (month_key // 100) * 12 + month_key % 100 AS m_idx, month_end FROM dim_month),
as_of_m AS (SELECT (year(as_of_date) * 100 + month(as_of_date)) AS as_of_month FROM v_as_of),
coh AS (
    SELECT country_code, signup_month_key, COUNT(*) AS cohort_size
    FROM mart_user_lifecycle GROUP BY country_code, signup_month_key
),
spine AS (
    SELECT c.country_code, c.signup_month_key, c.cohort_size, am.month_key AS cal_month_key,
           am.m_idx - sm.m_idx AS months_since_signup
    FROM coh c
    JOIN ms sm ON sm.month_key = c.signup_month_key
    JOIN ms am ON am.m_idx >= sm.m_idx
    CROSS JOIN as_of_m
    WHERE am.month_key <= as_of_m.as_of_month
),
act AS (
    SELECT DISTINCT f.user_key, d.month_key FROM fact_user_daily_usage f JOIN dim_date d ON d.date_key = f.date_key
),
act_by AS (
    SELECT l.country_code, l.signup_month_key, act.month_key AS cal_month_key, COUNT(*) AS active_users
    FROM act JOIN mart_user_lifecycle l ON l.user_key = act.user_key GROUP BY 1, 2, 3
),
pay_by AS (
    SELECT l.country_code, l.signup_month_key, m.month_key AS cal_month_key, COUNT(*) AS paying_users
    FROM mart_subscription_history h
    JOIN mart_user_lifecycle l ON l.user_key = h.user_key
    JOIN dim_month m ON m.month_end >= h.valid_from AND m.month_end < h.valid_to_excl
    WHERE h.is_paid GROUP BY 1, 2, 3
)
SELECT s.country_code, s.signup_month_key, s.months_since_signup, s.cohort_size,
       COALESCE(a.active_users, 0) AS active_users, COALESCE(p.paying_users, 0) AS paying_users,
       COALESCE(a.active_users, 0) * 1.0 / s.cohort_size AS active_retention,
       COALESCE(p.paying_users, 0) * 1.0 / s.cohort_size AS paying_share
FROM spine s
LEFT JOIN act_by a ON a.country_code = s.country_code AND a.signup_month_key = s.signup_month_key AND a.cal_month_key = s.cal_month_key
LEFT JOIN pay_by p ON p.country_code = s.country_code AND p.signup_month_key = s.signup_month_key AND p.cal_month_key = s.cal_month_key;
