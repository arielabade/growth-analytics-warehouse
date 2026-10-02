-- id: STG040
-- name: Load plan, plan-tier and user dimensions
-- business_question: Resolve each user's current plan from their latest subscription event.
-- tables: staging.stg_ref_plan, staging.stg_users, staging.stg_subscription_events, dim_plan_tier, dim_plan, dim_user
-- grain: one row per tier / plan / user
-- output: populated dim_plan_tier, dim_plan, dim_user
-- kind: staging
INSERT INTO dim_plan_tier (plan_tier_key, tier_name, is_paid)
SELECT row_number() OVER (ORDER BY tier_name), tier_name, tier_name <> 'free'
FROM (SELECT DISTINCT tier_name FROM staging.stg_ref_plan);

INSERT INTO dim_plan (plan_key, plan_name, plan_tier_key, list_price_eur)
SELECT row_number() OVER (ORDER BY p.list_price_eur, p.plan_name), p.plan_name, t.plan_tier_key, p.list_price_eur
FROM staging.stg_ref_plan p JOIN dim_plan_tier t ON t.tier_name = p.tier_name;

INSERT INTO dim_user (user_key, user_id, email_hash, signup_date_key, country_key, source_key, current_plan_key, n_raw_accounts)
SELECT row_number() OVER (ORDER BY u.user_id), u.user_id, u.email_hash,
       CAST(strftime(u.signup_date, '%Y%m%d') AS INTEGER), c.country_key, s.source_key,
       p.plan_key, u.n_raw_accounts
FROM staging.stg_users u
JOIN dim_country c ON c.country_code = u.country
JOIN dim_acquisition_source s ON s.source_name = u.source
LEFT JOIN (SELECT user_id, arg_max(plan_to, event_ts) AS plan_name
           FROM staging.stg_subscription_events GROUP BY user_id) le ON le.user_id = u.user_id
JOIN dim_plan p ON p.plan_name = COALESCE(le.plan_name, u.raw_current_plan);
