-- id: M040
-- name: mart_unit_economics_country_month
-- business_question: Per country and month: what did we spend, how many signups and paying customers did it buy, and what do customers pay and how fast do they churn?
-- tables: fact_ad_performance, mart_user_lifecycle, mart_subscription_history, fact_subscription_event, dim_country, dim_month, dim_date, dim_user, v_as_of
-- grain: one row per country x month
-- output: spend, ad_signups, cost_per_signup, new_users, paid-source customers, paid_cac_90d (mature cohorts only), paying_end, mrr_end, arpu, cancels, logo_churn
-- replaces: Notebooks 1 and 3 (cost per subscription; monthly churn by country)
-- kind: mart
-- Cost per signup (spend / signups) and paid CAC (spend / paying customers) are separate columns on purpose.
-- paid_cac_90d uses cohorts whose 90-day observation window is complete (is_mature_90d), to avoid right-censoring bias.
CREATE OR REPLACE VIEW mart_unit_economics_country_month AS
WITH spine AS (
    SELECT c.country_key, c.country_code, m.month_key, m.month_start, m.month_end,
           m.month_end + INTERVAL 90 DAY <= a.as_of_date AS is_mature_90d
    FROM dim_country c CROSS JOIN dim_month m CROSS JOIN v_as_of a
    WHERE m.month_start <= a.as_of_date
),
ads AS (
    SELECT country_key, month_key, SUM(spend_eur) AS spend_eur, SUM(signups) AS ad_signups
    FROM fact_ad_performance GROUP BY country_key, month_key
),
cohort AS (
    SELECT country_key, signup_month_key AS month_key,
           COUNT(*) AS new_users,
           COUNT(*) FILTER (WHERE is_paid_source) AS new_paid_source_users,
           COUNT(*) FILTER (WHERE is_paid_source AND days_to_upgrade <= 90) AS paid_source_customers_90d,
           COUNT(*) FILTER (WHERE is_paid_source AND ever_paid) AS paid_source_customers_to_date,
           COUNT(*) FILTER (WHERE NOT is_paid_source AND days_to_upgrade <= 90) AS organic_customers_90d
    FROM mart_user_lifecycle GROUP BY country_key, signup_month_key
),
mrr AS (
    SELECT u.country_key, m.month_key,
           COUNT(*) FILTER (WHERE h.is_paid) AS paying_end,
           SUM(h.mrr_eur) FILTER (WHERE h.is_paid) AS mrr_end
    FROM mart_subscription_history h
    JOIN dim_user u ON u.user_key = h.user_key
    JOIN dim_month m ON m.month_end >= h.valid_from AND m.month_end < h.valid_to_excl
    GROUP BY u.country_key, m.month_key
),
ev AS (
    SELECT u.country_key, d.month_key,
           COUNT(*) FILTER (WHERE e.event_type = 'upgrade') AS upgrades,
           COUNT(*) FILTER (WHERE e.event_type = 'cancel') AS cancels
    FROM fact_subscription_event e
    JOIN dim_user u ON u.user_key = e.user_key
    JOIN dim_date d ON d.date_key = e.event_date_key
    GROUP BY u.country_key, d.month_key
),
j AS (
    SELECT s.country_code, s.month_key, s.month_start, s.is_mature_90d,
           COALESCE(a.spend_eur, 0) AS spend_eur, COALESCE(a.ad_signups, 0) AS ad_signups,
           COALESCE(c.new_users, 0) AS new_users, COALESCE(c.new_paid_source_users, 0) AS new_paid_source_users,
           COALESCE(c.paid_source_customers_90d, 0) AS paid_source_customers_90d,
           COALESCE(c.paid_source_customers_to_date, 0) AS paid_source_customers_to_date,
           COALESCE(c.organic_customers_90d, 0) AS organic_customers_90d,
           COALESCE(r.paying_end, 0) AS paying_end, COALESCE(r.mrr_end, 0) AS mrr_end,
           COALESCE(e.upgrades, 0) AS upgrades, COALESCE(e.cancels, 0) AS cancels
    FROM spine s
    LEFT JOIN ads a ON a.country_key = s.country_key AND a.month_key = s.month_key
    LEFT JOIN cohort c ON c.country_key = s.country_key AND c.month_key = s.month_key
    LEFT JOIN mrr r ON r.country_key = s.country_key AND r.month_key = s.month_key
    LEFT JOIN ev e ON e.country_key = s.country_key AND e.month_key = s.month_key
),
w AS (
    SELECT j.*, LAG(paying_end) OVER (PARTITION BY country_code ORDER BY month_key) AS paying_start
    FROM j
)
SELECT country_code, month_key, month_start, is_mature_90d, spend_eur, ad_signups,
       spend_eur / NULLIF(ad_signups, 0) AS cost_per_signup,
       new_users, new_paid_source_users, paid_source_customers_90d, paid_source_customers_to_date, organic_customers_90d,
       CASE WHEN is_mature_90d THEN spend_eur / NULLIF(paid_source_customers_90d, 0) END AS paid_cac_90d,
       upgrades, paying_start, paying_end, mrr_end, mrr_end / NULLIF(paying_end, 0) AS arpu,
       cancels, cancels * 1.0 / NULLIF(paying_start, 0) AS logo_churn
FROM w;
