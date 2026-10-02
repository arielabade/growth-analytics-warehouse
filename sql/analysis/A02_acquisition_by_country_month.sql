-- id: A02
-- name: Paid acquisition by country and month
-- business_question: How do spend, funnel conversion and cost per signup evolve month by month in each country?
-- tables: mart_funnel_country
-- grain: one row per country x month
-- output: summed measures and ratios of sums across channels
-- replaces: Notebook 1 (funnel by country, reporting periods)
-- kind: analysis
SELECT country_code, month_start,
       SUM(spend_eur) AS spend_eur, SUM(impressions) AS impressions, SUM(reach) AS reach,
       SUM(link_clicks) AS link_clicks, SUM(landing_page_views) AS landing_page_views, SUM(signups) AS signups,
       SUM(impressions) * 1.0 / NULLIF(SUM(reach), 0) AS frequency,
       SUM(spend_eur) / NULLIF(SUM(impressions), 0) * 1000 AS cpm,
       SUM(spend_eur) / NULLIF(SUM(link_clicks), 0) AS cpc,
       SUM(link_clicks) * 1.0 / NULLIF(SUM(impressions), 0) AS ctr,
       SUM(landing_page_views) * 1.0 / NULLIF(SUM(link_clicks), 0) AS lpv_rate,
       SUM(signups) * 1.0 / NULLIF(SUM(landing_page_views), 0) AS signup_rate,
       SUM(spend_eur) / NULLIF(SUM(signups), 0) AS cost_per_signup
FROM mart_funnel_country
GROUP BY country_code, month_start
ORDER BY country_code, month_start;
