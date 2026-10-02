-- id: A13
-- name: Paid-subscription durations for survival curves
-- business_question: How long do paying customers stay, accounting for customers who have not cancelled yet (censoring)?
-- tables: mart_user_lifecycle, v_as_of
-- grain: one row per user who ever paid
-- output: country_code, duration_days (first upgrade -> cancel, or -> as_of if still paying), cancelled flag
-- replaces: Notebook 3 (monthly churn by country) - survival view
-- kind: analysis
SELECT l.user_key, l.country_code, l.source_name,
       date_diff('day', l.first_upgrade_date, COALESCE(l.cancel_date, a.as_of_date)) AS duration_days,
       l.cancel_date IS NOT NULL AS cancelled
FROM mart_user_lifecycle l CROSS JOIN v_as_of a
WHERE l.first_upgrade_date IS NOT NULL;
