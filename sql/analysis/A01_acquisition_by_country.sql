-- id: A01
-- name: Paid acquisition by country (period total)
-- business_question: For each country, what did paid media cost and how did traffic convert at each funnel step?
-- tables: mart_funnel_country
-- grain: one row per country
-- output: summed spend/impressions/reach/clicks/landing views/signups and ratios computed from those sums (never averaged row ratios)
-- replaces: Notebook 1 (paid acquisition funnel by country)
-- kind: analysis
SELECT country_code,
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
GROUP BY country_code
ORDER BY spend_eur DESC;
