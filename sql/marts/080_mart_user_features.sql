-- id: M080
-- name: mart_user_features
-- business_question: For each month-end snapshot, what did each still-free user do in the PRIOR 30 days, and did they convert to paid in the NEXT 30 days?
-- tables: fact_user_daily_usage, dim_date, dim_month, mart_user_lifecycle, v_as_of
-- grain: one row per user x snapshot_date (month ends) for free, never-paid users with usage in the prior 60 days
-- output: features computed only from days <= snapshot_date; converted_next_30d (label) with label_available flag
-- replaces: Notebook 3 (logistic regression on heavy users) - rebuilt without target/feature leakage
-- kind: mart
-- Leakage guard: every feature uses dates <= snapshot_date; the label uses dates in (snapshot_date, snapshot_date + 30].
CREATE OR REPLACE VIEW mart_user_features AS
WITH snaps AS (
    SELECT m.month_end AS snapshot_date
    FROM dim_month m CROSS JOIN v_as_of a
    WHERE m.month_end <= a.as_of_date
      AND m.month_end - 60 >= (SELECT MIN(date) FROM dim_date)
),
u60 AS (
    SELECT s.snapshot_date, f.user_key,
           SUM(f.assets_inserted) FILTER (WHERE d.date > s.snapshot_date - 30) AS assets_30d,
           COUNT(*) FILTER (WHERE d.date > s.snapshot_date - 30) AS active_days_30d,
           MAX(f.assets_inserted) FILTER (WHERE d.date > s.snapshot_date - 30) AS max_daily_assets_30d,
           COALESCE(SUM(f.assets_inserted) FILTER (WHERE d.date <= s.snapshot_date - 30), 0) AS assets_prev30d,
           COUNT(*) FILTER (WHERE d.date <= s.snapshot_date - 30) AS active_days_prev30d,
           date_diff('day', MAX(d.date), s.snapshot_date) AS days_since_last_use
    FROM fact_user_daily_usage f
    JOIN dim_date d ON d.date_key = f.date_key
    JOIN snaps s ON d.date BETWEEN s.snapshot_date - 59 AND s.snapshot_date
    GROUP BY s.snapshot_date, f.user_key
)
SELECT u.snapshot_date, u.user_key, l.country_code, l.source_name, l.is_paid_source,
       COALESCE(u.assets_30d, 0) AS assets_30d, COALESCE(u.active_days_30d, 0) AS active_days_30d,
       COALESCE(u.max_daily_assets_30d, 0) AS max_daily_assets_30d,
       u.assets_prev30d, u.active_days_prev30d, u.days_since_last_use,
       date_diff('day', l.signup_date, u.snapshot_date) AS tenure_days,
       COALESCE(u.assets_30d, 0) * 1.0 / NULLIF(u.active_days_30d, 0) AS avg_assets_per_active_day,
       (l.first_upgrade_date IS NOT NULL AND l.first_upgrade_date > u.snapshot_date
        AND l.first_upgrade_date <= u.snapshot_date + 30) AS converted_next_30d,
       u.snapshot_date + 30 <= (SELECT as_of_date FROM v_as_of) AS label_available
FROM u60 u
JOIN mart_user_lifecycle l ON l.user_key = u.user_key
WHERE l.signup_date <= u.snapshot_date
  AND (l.first_upgrade_date IS NULL OR l.first_upgrade_date > u.snapshot_date);
