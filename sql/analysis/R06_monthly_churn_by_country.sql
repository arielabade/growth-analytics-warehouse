-- id: R06
-- name: Monthly churn by country (reconstructed extraction)
-- business_question: Reconstruction of the monthly paid-subscription churn by country (cancels / paying customers at start of month).
-- tables: fact_subscription_event, dim_user, dim_country, dim_date, dim_month
-- grain: one row per country x month
-- output: country_code, month_label, paying_at_start, cancels, churn_rate
-- replaces: Input dataset of notebook 3 (monthly churn by country) - reconstructed against the core tables
-- kind: reconstructed
WITH ev AS (
    SELECT u.country_key, d.month_key,
           SUM(CASE WHEN e.event_type = 'upgrade' THEN 1 WHEN e.event_type = 'cancel' THEN -1 ELSE 0 END) AS net_change,
           COUNT(*) FILTER (WHERE e.event_type = 'cancel') AS cancels
    FROM fact_subscription_event e
    JOIN dim_user u ON u.user_key = e.user_key
    JOIN dim_date d ON d.date_key = e.event_date_key
    GROUP BY u.country_key, d.month_key
),
j AS (
    SELECT c.country_code, m.month_key, m.month_label, COALESCE(ev.net_change, 0) AS net_change, COALESCE(ev.cancels, 0) AS cancels
    FROM dim_country c CROSS JOIN dim_month m
    LEFT JOIN ev ON ev.country_key = c.country_key AND ev.month_key = m.month_key
    WHERE m.month_start <= (SELECT as_of_date FROM v_as_of)
),
r AS (
    SELECT j.*, COALESCE(SUM(net_change) OVER (PARTITION BY country_code ORDER BY month_key
                          ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING), 0) AS paying_at_start
    FROM j
)
SELECT country_code, month_label, paying_at_start, cancels, cancels * 1.0 / NULLIF(paying_at_start, 0) AS churn_rate
FROM r ORDER BY country_code, month_key;
