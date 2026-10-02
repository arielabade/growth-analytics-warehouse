-- id: M010
-- name: mart_subscription_history
-- business_question: What plan and MRR did each user have on any given date? (slowly-changing attributes derived from events)
-- tables: fact_subscription_event, dim_date, dim_plan, dim_plan_tier, v_as_of
-- grain: one row per user x plan interval [valid_from, valid_to_excl)
-- output: user_key, valid_from, valid_to_excl, plan_name, is_paid, mrr_eur
-- replaces: Helper for notebook 3 (monthly churn) - event-sourced replacement for a type-2 dimension
-- kind: mart
CREATE OR REPLACE VIEW mart_subscription_history AS
WITH e AS (
    SELECT ev.user_key, d.date AS valid_from, p.plan_name, t.is_paid, ev.mrr_after_eur AS mrr_eur,
           LEAD(d.date) OVER (PARTITION BY ev.user_key ORDER BY ev.event_ts, ev.event_key) AS next_date
    FROM fact_subscription_event ev
    JOIN dim_date d ON d.date_key = ev.event_date_key
    JOIN dim_plan p ON p.plan_key = ev.plan_to_key
    JOIN dim_plan_tier t ON t.plan_tier_key = p.plan_tier_key
)
SELECT user_key, valid_from,
       COALESCE(next_date, (SELECT as_of_date FROM v_as_of) + 1) AS valid_to_excl,
       plan_name, is_paid, mrr_eur
FROM e;
