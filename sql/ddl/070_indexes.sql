-- id: DDL070
-- name: Secondary indexes
-- business_question: Speed up the selective lookups the dashboard performs.
-- tables: fact_user_daily_usage, fact_subscription_event
-- grain: n/a
-- output: DDL only (DuckDB ART indexes; useful for selective point lookups, not for scans)
-- kind: ddl
CREATE INDEX idx_usage_date ON fact_user_daily_usage (date_key);
CREATE INDEX idx_event_user ON fact_subscription_event (user_key);
