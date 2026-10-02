-- id: DDL050
-- name: Fact tables
-- business_question: Store measurable events at their natural grain.
-- tables: fact_ad_performance, fact_user_daily_usage, fact_subscription_event, fact_user_scores
-- grain: see column comments (ad: campaign x country x reporting period; usage: user x day; event: one subscription event; scores: user x scoring date x model version)
-- output: DDL only
-- kind: ddl
CREATE TABLE fact_ad_performance (
    campaign_key         INTEGER NOT NULL REFERENCES dim_campaign (campaign_key),
    country_key          INTEGER NOT NULL REFERENCES dim_country (country_key),
    period_start_key     INTEGER NOT NULL REFERENCES dim_date (date_key),
    period_end_key       INTEGER NOT NULL REFERENCES dim_date (date_key),
    month_key            INTEGER NOT NULL REFERENCES dim_month (month_key),
    spend_eur            DOUBLE NOT NULL CHECK (spend_eur >= 0),
    impressions          BIGINT NOT NULL CHECK (impressions >= 0),
    reach                BIGINT NOT NULL CHECK (reach >= 0),
    link_clicks          BIGINT NOT NULL CHECK (link_clicks >= 0),
    landing_page_views   BIGINT NOT NULL CHECK (landing_page_views >= 0),
    signups              BIGINT NOT NULL CHECK (signups >= 0),
    PRIMARY KEY (campaign_key, country_key, period_start_key)
);

CREATE TABLE fact_user_daily_usage (
    user_key        INTEGER NOT NULL REFERENCES dim_user (user_key),
    date_key        INTEGER NOT NULL REFERENCES dim_date (date_key),
    assets_inserted INTEGER NOT NULL CHECK (assets_inserted >= 0),
    PRIMARY KEY (user_key, date_key)
);

CREATE TABLE fact_subscription_event (
    event_key       BIGINT PRIMARY KEY,
    user_key        INTEGER NOT NULL REFERENCES dim_user (user_key),
    event_date_key  INTEGER NOT NULL REFERENCES dim_date (date_key),
    event_ts        TIMESTAMP NOT NULL,
    event_type      VARCHAR NOT NULL CHECK (event_type IN ('signup', 'upgrade', 'downgrade', 'cancel')),
    plan_from_key   INTEGER REFERENCES dim_plan (plan_key),
    plan_to_key     INTEGER NOT NULL REFERENCES dim_plan (plan_key),
    mrr_before_eur  DOUBLE NOT NULL,
    mrr_after_eur   DOUBLE NOT NULL,
    mrr_delta_eur   DOUBLE NOT NULL
);

CREATE TABLE fact_user_scores (
    user_key         INTEGER NOT NULL REFERENCES dim_user (user_key),
    scoring_date_key INTEGER NOT NULL REFERENCES dim_date (date_key),
    model_name       VARCHAR NOT NULL,
    model_version    VARCHAR NOT NULL,
    score            DOUBLE NOT NULL CHECK (score BETWEEN 0 AND 1),
    score_decile     INTEGER NOT NULL CHECK (score_decile BETWEEN 1 AND 10),   -- 10 = highest propensity
    PRIMARY KEY (user_key, scoring_date_key, model_version)
);
