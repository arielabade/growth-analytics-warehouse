-- id: DDL010
-- name: Time dimensions (snowflaked)
-- business_question: Give every fact a calendar that can be rolled up date -> month -> quarter -> year.
-- tables: dim_year, dim_quarter, dim_month, dim_date, warehouse_meta
-- grain: one row per year / quarter / month / calendar day
-- output: DDL only
-- kind: ddl
CREATE TABLE warehouse_meta (
    key   VARCHAR PRIMARY KEY,
    value VARCHAR NOT NULL
);

CREATE TABLE dim_year (
    year_key INTEGER PRIMARY KEY,           -- e.g. 2026
    year_num INTEGER NOT NULL
);

CREATE TABLE dim_quarter (
    quarter_key   INTEGER PRIMARY KEY,      -- YYYYQ, e.g. 20262
    year_key      INTEGER NOT NULL REFERENCES dim_year (year_key),
    quarter_num   INTEGER NOT NULL CHECK (quarter_num BETWEEN 1 AND 4),
    quarter_label VARCHAR NOT NULL          -- e.g. 2026-Q2
);

CREATE TABLE dim_month (
    month_key     INTEGER PRIMARY KEY,      -- YYYYMM, e.g. 202606
    quarter_key   INTEGER NOT NULL REFERENCES dim_quarter (quarter_key),
    month_num     INTEGER NOT NULL CHECK (month_num BETWEEN 1 AND 12),
    month_start   DATE NOT NULL,
    month_end     DATE NOT NULL,
    month_label   VARCHAR NOT NULL          -- e.g. 2026-06
);

CREATE TABLE dim_date (
    date_key     INTEGER PRIMARY KEY,       -- YYYYMMDD
    date         DATE NOT NULL UNIQUE,
    month_key    INTEGER NOT NULL REFERENCES dim_month (month_key),
    day_of_week  INTEGER NOT NULL,          -- 1 = Monday
    is_weekend   BOOLEAN NOT NULL
);
