-- id: R05
-- name: Ad-performance export by country (reconstructed extraction)
-- business_question: Reconstruction of the ad-platform export by country and reporting period (before any cleaning).
-- tables: fact_ad_performance, dim_campaign, dim_channel, dim_country, dim_date
-- grain: one row per campaign x country x reporting period
-- output: campaign, channel, country, reporting_period ("start - end"), spend, impressions, reach, frequency, link clicks, landing page views, subscriptions
-- replaces: Input dataset of notebook 1 (ad-performance export by country) - reconstructed against the core tables
-- kind: reconstructed
SELECT camp.campaign_name AS campaign, ch.channel_name AS channel, c.country_code AS country,
       strftime(ds.date, '%Y-%m-%d') || ' - ' || strftime(de.date, '%Y-%m-%d') AS reporting_period,
       f.spend_eur, f.impressions, f.reach, f.impressions * 1.0 / NULLIF(f.reach, 0) AS frequency,
       f.link_clicks, f.landing_page_views, f.signups AS subscriptions
FROM fact_ad_performance f
JOIN dim_campaign camp ON camp.campaign_key = f.campaign_key
JOIN dim_channel ch ON ch.channel_key = camp.channel_key
JOIN dim_country c ON c.country_key = f.country_key
JOIN dim_date ds ON ds.date_key = f.period_start_key
JOIN dim_date de ON de.date_key = f.period_end_key
ORDER BY ds.date, ch.channel_name, camp.campaign_name, c.country_code;
