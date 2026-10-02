-- id: M000
-- name: v_as_of
-- business_question: Single source of truth for the reference date, so no query ever calls current_date.
-- tables: warehouse_meta
-- grain: one row
-- output: as_of_date
-- kind: mart
CREATE OR REPLACE VIEW v_as_of AS
SELECT CAST(value AS DATE) AS as_of_date FROM warehouse_meta WHERE key = 'as_of_date';
