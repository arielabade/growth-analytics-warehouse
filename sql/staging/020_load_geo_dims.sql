-- id: STG020
-- name: Load geography dimensions
-- business_question: Create deterministic surrogate keys for regions and countries.
-- tables: staging.stg_ref_country, dim_region, dim_country
-- grain: one row per region / country
-- output: populated dim_region, dim_country
-- kind: staging
INSERT INTO dim_region (region_key, region_name)
SELECT row_number() OVER (ORDER BY region_name), region_name
FROM (SELECT DISTINCT region_name FROM staging.stg_ref_country);

INSERT INTO dim_country (country_key, country_code, country_name, region_key, currency, price_index)
SELECT row_number() OVER (ORDER BY c.country_code), c.country_code, c.country_name, r.region_key, c.currency, c.price_index
FROM staging.stg_ref_country c JOIN dim_region r ON r.region_name = c.region_name;
