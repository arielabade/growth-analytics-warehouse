-- id: A03
-- name: Paid acquisition by channel and country
-- business_question: Which channel delivers cheaper signups in each country?
-- tables: mart_funnel_country
-- grain: one row per channel x country
-- output: summed measures and cost per signup, CTR, signup rate
-- kind: analysis
SELECT channel_name, country_code, SUM(spend_eur) AS spend_eur, SUM(signups) AS signups,
       SUM(link_clicks) * 1.0 / NULLIF(SUM(impressions), 0) AS ctr,
       SUM(signups) * 1.0 / NULLIF(SUM(landing_page_views), 0) AS signup_rate,
       SUM(spend_eur) / NULLIF(SUM(signups), 0) AS cost_per_signup
FROM mart_funnel_country
GROUP BY channel_name, country_code
ORDER BY country_code, channel_name;
