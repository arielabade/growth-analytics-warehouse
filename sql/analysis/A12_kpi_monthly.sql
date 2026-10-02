-- id: A12
-- name: Monthly KPI tracking (all countries)
-- business_question: How are spend, signups, cost per signup, paid CAC, churn, MRR and active users trending month over month?
-- tables: mart_unit_economics_country_month, fact_user_daily_usage, dim_date
-- grain: one row per month
-- output: spend, signups, cost_per_signup, paid_cac_90d, paying_end, mrr_end, logo_churn, monthly_active_users
-- kind: analysis
WITH ue AS (
    SELECT month_key, month_start, SUM(spend_eur) AS spend_eur, SUM(ad_signups) AS ad_signups,
           SUM(new_users) AS new_users, SUM(upgrades) AS upgrades,
           SUM(spend_eur) FILTER (WHERE is_mature_90d) AS spend_mature,
           SUM(paid_source_customers_90d) FILTER (WHERE is_mature_90d) AS customers_mature,
           SUM(paying_end) AS paying_end, SUM(mrr_end) AS mrr_end,
           SUM(cancels) AS cancels, SUM(paying_start) AS paying_start
    FROM mart_unit_economics_country_month GROUP BY month_key, month_start
),
mau AS (
    SELECT d.month_key, COUNT(DISTINCT f.user_key) AS monthly_active_users
    FROM fact_user_daily_usage f JOIN dim_date d ON d.date_key = f.date_key GROUP BY d.month_key
)
SELECT ue.month_key, ue.month_start, ue.spend_eur, ue.ad_signups, ue.new_users, ue.upgrades,
       ue.spend_eur / NULLIF(ue.ad_signups, 0) AS cost_per_signup,
       ue.spend_mature / NULLIF(ue.customers_mature, 0) AS paid_cac_90d,
       ue.paying_end, ue.mrr_end, ue.cancels * 1.0 / NULLIF(ue.paying_start, 0) AS logo_churn,
       mau.monthly_active_users
FROM ue LEFT JOIN mau ON mau.month_key = ue.month_key
ORDER BY ue.month_key;
