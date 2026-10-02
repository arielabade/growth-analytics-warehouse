-- id: A10
-- name: Usage concentration by country and signup cohort
-- business_question: Is usage more concentrated in some countries or older signup cohorts?
-- tables: mart_usage_pareto
-- grain: one row per window x country x signup year
-- output: active users, users in the top-80%-of-volume set, their share, volume per active user
-- replaces: Notebook 3 (users created in a given year or later; cohort filters)
-- kind: analysis
SELECT window_days, country_code, signup_year, COUNT(*) AS active_users,
       COUNT(*) FILTER (WHERE in_top80_volume) AS top80_users,
       COUNT(*) FILTER (WHERE in_top80_volume) * 1.0 / COUNT(*) AS top80_user_share,
       SUM(total_assets) * 1.0 / COUNT(*) AS assets_per_active_user
FROM mart_usage_pareto
GROUP BY window_days, country_code, signup_year
ORDER BY window_days, country_code, signup_year;
