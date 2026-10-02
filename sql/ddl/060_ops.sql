-- id: DDL060
-- name: Operational tables (pipeline runs and data quality)
-- business_question: Is the pipeline healthy, and which checks passed in each run?
-- tables: pipeline_runs, pipeline_run_tables, data_quality_results
-- grain: one row per run / run x table / run x check
-- output: DDL only
-- kind: ddl
CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id       VARCHAR PRIMARY KEY,
    started_at   TIMESTAMP NOT NULL,
    finished_at  TIMESTAMP,
    status       VARCHAR NOT NULL,          -- running | success | success_with_warnings | failed
    as_of_date   DATE NOT NULL,
    raw_rows     BIGINT,
    staging_rows BIGINT,
    core_rows    BIGINT,
    mart_rows    BIGINT,
    message      VARCHAR
);

CREATE TABLE IF NOT EXISTS pipeline_run_tables (
    run_id     VARCHAR NOT NULL,
    layer      VARCHAR NOT NULL,            -- raw | staging | core | marts
    table_name VARCHAR NOT NULL,
    row_count  BIGINT NOT NULL,
    PRIMARY KEY (run_id, layer, table_name)
);

CREATE TABLE IF NOT EXISTS data_quality_results (
    run_id     VARCHAR NOT NULL,
    check_name VARCHAR NOT NULL,
    layer      VARCHAR NOT NULL,
    status     VARCHAR NOT NULL,            -- pass | warn | fail
    details    VARCHAR,
    checked_at TIMESTAMP NOT NULL,
    PRIMARY KEY (run_id, check_name)
);
