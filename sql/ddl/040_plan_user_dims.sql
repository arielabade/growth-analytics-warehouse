-- id: DDL040
-- name: Plan and user dimensions (snowflaked)
-- business_question: Describe who a user is, which plan they are on now, and whether that plan is free or paid.
-- tables: dim_plan_tier, dim_plan, dim_user
-- grain: one row per plan tier / plan / user (consolidated by normalized e-mail)
-- output: DDL only
-- kind: ddl
CREATE TABLE dim_plan_tier (
    plan_tier_key INTEGER PRIMARY KEY,
    tier_name     VARCHAR NOT NULL UNIQUE,   -- free | paid
    is_paid       BOOLEAN NOT NULL
);

CREATE TABLE dim_plan (
    plan_key       INTEGER PRIMARY KEY,
    plan_name      VARCHAR NOT NULL UNIQUE,
    plan_tier_key  INTEGER NOT NULL REFERENCES dim_plan_tier (plan_tier_key),
    list_price_eur DOUBLE NOT NULL
);

CREATE TABLE dim_user (
    user_key          INTEGER PRIMARY KEY,
    user_id           VARCHAR NOT NULL UNIQUE,
    email_hash        VARCHAR NOT NULL UNIQUE,   -- pseudonymous; addresses are never stored
    signup_date_key   INTEGER NOT NULL REFERENCES dim_date (date_key),
    country_key       INTEGER NOT NULL REFERENCES dim_country (country_key),
    source_key        INTEGER NOT NULL REFERENCES dim_acquisition_source (source_key),
    current_plan_key  INTEGER NOT NULL REFERENCES dim_plan (plan_key),  -- type-1 attribute; history lives in fact_subscription_event
    n_raw_accounts    INTEGER NOT NULL          -- >1 when "+alias" accounts were merged
);
