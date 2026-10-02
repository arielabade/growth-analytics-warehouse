-- id: M030
-- name: mart_funnel_country
-- business_question: How does paid traffic move through impressions -> clicks -> landing views -> signups, by country, channel and month?
-- tables: fact_ad_performance, dim_campaign, dim_channel, dim_country, dim_month
-- grain: one row per country x channel x month
-- output: summed measures plus ctr, cpc, cpm, lpv_rate, signup_rate, cost_per_signup, frequency (all ratios of SUMS)
-- replaces: Notebook 1 (paid acquisition funnel by country)
-- kind: mart
CREATE OR REPLACE VIEW mart_funnel_country AS
SELECT c.country_code, ch.channel_name, m.month_key, m.month_start,
       SUM(f.spend_eur) AS spend_eur, SUM(f.impressions) AS impressions, SUM(f.reach) AS reach,
       SUM(f.link_clicks) AS link_clicks, SUM(f.landing_page_views) AS landing_page_views, SUM(f.signups) AS signups,
       SUM(f.link_clicks) * 1.0 / NULLIF(SUM(f.impressions), 0) AS ctr,
       SUM(f.spend_eur) / NULLIF(SUM(f.link_clicks), 0) AS cpc,
       SUM(f.spend_eur) / NULLIF(SUM(f.impressions), 0) * 1000 AS cpm,
       SUM(f.landing_page_views) * 1.0 / NULLIF(SUM(f.link_clicks), 0) AS lpv_rate,
       SUM(f.signups) * 1.0 / NULLIF(SUM(f.landing_page_views), 0) AS signup_rate,
       SUM(f.spend_eur) / NULLIF(SUM(f.signups), 0) AS cost_per_signup,
       SUM(f.impressions) * 1.0 / NULLIF(SUM(f.reach), 0) AS frequency
FROM fact_ad_performance f
JOIN dim_campaign camp ON camp.campaign_key = f.campaign_key
JOIN dim_channel ch ON ch.channel_key = camp.channel_key
JOIN dim_country c ON c.country_key = f.country_key
JOIN dim_month m ON m.month_key = f.month_key
GROUP BY c.country_code, ch.channel_name, m.month_key, m.month_start;
