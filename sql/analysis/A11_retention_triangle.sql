-- id: A11
-- name: Cohort retention triangle (all countries)
-- business_question: What share of each signup-month cohort is still active k months later?
-- tables: mart_retention_cohorts
-- grain: one row per signup month x months since signup
-- output: cohort_size, active_users, paying_users and their shares (ratio of sums across countries)
-- replaces: Notebook 3 (monthly churn by country; extended)
-- kind: analysis
SELECT signup_month_key, months_since_signup, SUM(cohort_size) AS cohort_size,
       SUM(active_users) AS active_users, SUM(paying_users) AS paying_users,
       SUM(active_users) * 1.0 / SUM(cohort_size) AS active_retention,
       SUM(paying_users) * 1.0 / SUM(cohort_size) AS paying_share
FROM mart_retention_cohorts
GROUP BY signup_month_key, months_since_signup
ORDER BY signup_month_key, months_since_signup;
