-- id: DDL020
-- name: Geography dimensions (snowflaked)
-- business_question: Compare economics by country while still being able to roll up to region.
-- tables: dim_region, dim_country
-- grain: one row per region / country
-- output: DDL only
-- kind: ddl
CREATE TABLE dim_region (
    region_key  INTEGER PRIMARY KEY,
    region_name VARCHAR NOT NULL UNIQUE
);

CREATE TABLE dim_country (
    country_key  INTEGER PRIMARY KEY,
    country_code VARCHAR NOT NULL UNIQUE,   -- ISO 3166-1 alpha-2
    country_name VARCHAR NOT NULL,
    region_key   INTEGER NOT NULL REFERENCES dim_region (region_key),
    currency     VARCHAR NOT NULL,
    price_index  DOUBLE NOT NULL            -- local price level relative to list price
);
