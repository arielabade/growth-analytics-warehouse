-- id: M020
-- name: mart_user_lifecycle
-- business_question: When did each user sign up, first pay and cancel, and are they paying now?
-- tables: dim_user, dim_country, dim_acquisition_source, dim_plan, dim_plan_tier, dim_date, fact_subscription_event
-- grain: one row per user
-- output: user_key, country_key, country_code, source_name, is_paid_source, signup_date, signup_month_key, first_upgrade_date, cancel_date, current_tier, ever_paid, is_paying_now, days_to_upgrade
-- kind: mart
CREATE OR REPLACE VIEW mart_user_lifecycle AS
WITH ev AS (
    SELECT e.user_key,
           MIN(CASE WHEN e.event_type = 'upgrade' THEN d.date END) AS first_upgrade_date,
           MAX(CASE WHEN e.event_type = 'cancel' THEN d.date END) AS cancel_date
    FROM fact_subscription_event e JOIN dim_date d ON d.date_key = e.event_date_key
    GROUP BY e.user_key
)
SELECT u.user_key, u.country_key, c.country_code, s.source_name, s.is_paid AS is_paid_source,
       ds.date AS signup_date, ds.month_key AS signup_month_key,
       ev.first_upgrade_date, ev.cancel_date, t.tier_name AS current_tier,
       ev.first_upgrade_date IS NOT NULL AS ever_paid,
       (ev.first_upgrade_date IS NOT NULL AND ev.cancel_date IS NULL) AS is_paying_now,
       date_diff('day', ds.date, ev.first_upgrade_date) AS days_to_upgrade
FROM dim_user u
JOIN dim_country c ON c.country_key = u.country_key
JOIN dim_acquisition_source s ON s.source_key = u.source_key
JOIN dim_date ds ON ds.date_key = u.signup_date_key
JOIN dim_plan p ON p.plan_key = u.current_plan_key
JOIN dim_plan_tier t ON t.plan_tier_key = p.plan_tier_key
LEFT JOIN ev ON ev.user_key = u.user_key;
