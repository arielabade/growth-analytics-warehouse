-- id: A04
-- name: Unit-economics inputs by country (trailing 12 months)
-- business_question: What are each country's cost per signup, paid CAC, ARPU and monthly churn?
-- tables: mart_unit_economics_country_month, v_as_of
-- grain: one row per country
-- output: cost_per_signup (spend / signups), paid_cac (spend / paying customers, mature cohorts only), arpu, monthly_churn (pooled)
-- replaces: Notebooks 1 and 3 (cost per subscription; monthly churn by country), extended to LTV inputs
-- kind: analysis
-- Cost per signup and paid CAC are different numbers: the first prices a free account, the second prices a paying customer.
-- ARPU and churn are ratios of sums over the last 12 months (sum of MRR / sum of paying customers; sum of cancels / sum of customers at start of month).
WITH a AS (SELECT as_of_date FROM v_as_of)
SELECT m.country_code,
       SUM(m.spend_eur) AS spend_eur,
       SUM(m.spend_eur) / NULLIF(SUM(m.ad_signups), 0) AS cost_per_signup,
       SUM(m.spend_eur) FILTER (WHERE m.is_mature_90d) AS spend_mature_cohorts,
       SUM(m.paid_source_customers_90d) FILTER (WHERE m.is_mature_90d) AS paying_customers_mature_cohorts,
       SUM(m.spend_eur) FILTER (WHERE m.is_mature_90d)
         / NULLIF(SUM(m.paid_source_customers_90d) FILTER (WHERE m.is_mature_90d), 0) AS paid_cac,
       SUM(m.mrr_end) FILTER (WHERE m.month_start > a.as_of_date - 365)
         / NULLIF(SUM(m.paying_end) FILTER (WHERE m.month_start > a.as_of_date - 365), 0) AS arpu,
       SUM(m.cancels) FILTER (WHERE m.month_start > a.as_of_date - 365) * 1.0
         / NULLIF(SUM(m.paying_start) FILTER (WHERE m.month_start > a.as_of_date - 365), 0) AS monthly_churn,
       SUM(m.paying_end) FILTER (WHERE m.month_start = date_trunc('month', a.as_of_date)) AS paying_customers_now
FROM mart_unit_economics_country_month m CROSS JOIN a
GROUP BY m.country_code
ORDER BY m.country_code;
