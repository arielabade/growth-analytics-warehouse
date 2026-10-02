-- id: STG010
-- name: Load time dimensions
-- business_question: Build a gap-free calendar covering the data (from warehouse_meta calendar bounds).
-- tables: warehouse_meta, dim_year, dim_quarter, dim_month, dim_date
-- grain: one row per year / quarter / month / day
-- output: populated dim_year .. dim_date
-- kind: staging
CREATE OR REPLACE TEMP TABLE _cal AS
SELECT CAST(t.d AS DATE) AS d
FROM generate_series(
    CAST((SELECT value FROM warehouse_meta WHERE key = 'calendar_start') AS DATE),
    CAST((SELECT value FROM warehouse_meta WHERE key = 'calendar_end') AS DATE),
    INTERVAL 1 DAY) AS t(d);

INSERT INTO dim_year (year_key, year_num)
SELECT DISTINCT year(d), year(d) FROM _cal ORDER BY 1;

INSERT INTO dim_quarter (quarter_key, year_key, quarter_num, quarter_label)
SELECT DISTINCT year(d) * 10 + quarter(d), year(d), quarter(d),
       CAST(year(d) AS VARCHAR) || '-Q' || CAST(quarter(d) AS VARCHAR)
FROM _cal ORDER BY 1;

INSERT INTO dim_month (month_key, quarter_key, month_num, month_start, month_end, month_label)
SELECT year(d) * 100 + month(d), year(d) * 10 + quarter(d), month(d), MIN(d), MAX(d), strftime(MIN(d), '%Y-%m')
FROM _cal GROUP BY year(d), month(d), quarter(d) ORDER BY 1;

INSERT INTO dim_date (date_key, date, month_key, day_of_week, is_weekend)
SELECT year(d) * 10000 + month(d) * 100 + day(d), d, year(d) * 100 + month(d), isodow(d), isodow(d) >= 6
FROM _cal ORDER BY d;
