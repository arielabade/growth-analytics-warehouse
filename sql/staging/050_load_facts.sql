-- id: STG050
-- name: Load fact tables
-- business_question: Resolve natural keys to surrogate keys and persist facts at their natural grain.
-- tables: staging.stg_ad_performance, staging.stg_usage_daily, staging.stg_subscription_events, fact_ad_performance, fact_user_daily_usage, fact_subscription_event
-- grain: campaign x country x period / user x day / event
-- output: populated fact tables
-- kind: staging
INSERT INTO fact_ad_performance
SELECT camp.campaign_key, c.country_key,
       CAST(strftime(a.period_start, '%Y%m%d') AS INTEGER), CAST(strftime(a.period_end, '%Y%m%d') AS INTEGER),
       year(a.period_start) * 100 + month(a.period_start),
       a.spend_eur, a.impressions, a.reach, a.link_clicks, a.landing_page_views, a.signups
FROM staging.stg_ad_performance a
JOIN dim_campaign camp ON camp.campaign_name = a.campaign
JOIN dim_country c ON c.country_code = a.country;

INSERT INTO fact_user_daily_usage
SELECT u.user_key, CAST(strftime(s.usage_date, '%Y%m%d') AS INTEGER), s.assets_inserted
FROM staging.stg_usage_daily s JOIN dim_user u ON u.user_id = s.user_id;

INSERT INTO fact_subscription_event
SELECT row_number() OVER (ORDER BY e.event_ts, e.user_id, e.event_type) AS event_key,
       u.user_key, CAST(strftime(e.event_ts, '%Y%m%d') AS INTEGER), e.event_ts, e.event_type,
       pf.plan_key, pt.plan_key, e.mrr_before_eur, e.mrr_after_eur, e.mrr_after_eur - e.mrr_before_eur
FROM staging.stg_subscription_events e
JOIN dim_user u ON u.user_id = e.user_id
LEFT JOIN dim_plan pf ON pf.plan_name = e.plan_from
JOIN dim_plan pt ON pt.plan_name = e.plan_to;
