-- id: M060
-- name: mart_free_limit_simulation
-- business_question: If the free plan capped daily or monthly insertions at X, how many active free users and how much volume would be affected?
-- tables: fact_user_daily_usage, dim_date, mart_user_lifecycle, v_as_of
-- grain: one row per limit_type (daily | monthly) x limit_value over the trailing 30 days of currently-free active users
-- output: free_active_users, users_affected, pct_users_affected, volume_of_affected_users, excess_volume, pct_volume_excess, blocked_user_days
-- replaces: Notebooks 2 and 3 (daily and monthly free-tier limit simulations)
-- kind: mart
-- A user is affected by a daily limit if any day exceeds it, and by a monthly limit if the 30d total exceeds it.
CREATE OR REPLACE VIEW mart_free_limit_simulation AS
WITH a AS (SELECT as_of_date FROM v_as_of),
free_users AS (SELECT user_key FROM mart_user_lifecycle WHERE NOT is_paying_now),
dayrows AS (
    SELECT f.user_key, f.assets_inserted
    FROM fact_user_daily_usage f
    JOIN dim_date d ON d.date_key = f.date_key
    JOIN free_users fu ON fu.user_key = f.user_key
    CROSS JOIN a
    WHERE d.date BETWEEN a.as_of_date - 29 AND a.as_of_date
),
tot AS (
    SELECT user_key, SUM(assets_inserted) AS total_30d, MAX(assets_inserted) AS max_day
    FROM dayrows GROUP BY user_key
),
pop AS (SELECT COUNT(*) AS free_active_users, SUM(total_30d) AS total_volume FROM tot),
dgrid AS (SELECT unnest([1, 2, 3, 4, 5, 6, 8, 10, 12, 15, 20, 25, 30, 40, 50, 75, 100]) AS limit_value),
mgrid AS (SELECT unnest([10, 20, 30, 50, 75, 100, 150, 200, 300, 400, 500, 750, 1000, 1500, 2000]) AS limit_value),
daily AS (
    SELECT 'daily' AS limit_type, g.limit_value,
           COUNT(*) FILTER (WHERE t.max_day > g.limit_value) AS users_affected,
           SUM(t.total_30d) FILTER (WHERE t.max_day > g.limit_value) AS volume_of_affected_users
    FROM dgrid g CROSS JOIN tot t GROUP BY g.limit_value
),
daily_x AS (
    SELECT g.limit_value,
           SUM(GREATEST(d.assets_inserted - g.limit_value, 0)) AS excess_volume,
           COUNT(*) FILTER (WHERE d.assets_inserted > g.limit_value) AS blocked_user_days
    FROM dgrid g CROSS JOIN dayrows d GROUP BY g.limit_value
),
monthly AS (
    SELECT 'monthly' AS limit_type, g.limit_value,
           COUNT(*) FILTER (WHERE t.total_30d > g.limit_value) AS users_affected,
           SUM(t.total_30d) FILTER (WHERE t.total_30d > g.limit_value) AS volume_of_affected_users,
           SUM(GREATEST(t.total_30d - g.limit_value, 0)) AS excess_volume,
           COUNT(*) FILTER (WHERE t.total_30d > g.limit_value) AS blocked_user_days
    FROM mgrid g CROSS JOIN tot t GROUP BY g.limit_value
),
u AS (
    SELECT d.limit_type, d.limit_value, d.users_affected, d.volume_of_affected_users, x.excess_volume, x.blocked_user_days
    FROM daily d JOIN daily_x x ON x.limit_value = d.limit_value
    UNION ALL
    SELECT limit_type, limit_value, users_affected, volume_of_affected_users, excess_volume, blocked_user_days FROM monthly
)
SELECT u.limit_type, u.limit_value, p.free_active_users,
       COALESCE(u.users_affected, 0) AS users_affected,
       COALESCE(u.users_affected, 0) * 1.0 / p.free_active_users AS pct_users_affected,
       p.total_volume AS total_volume_30d,
       COALESCE(u.volume_of_affected_users, 0) AS volume_of_affected_users,
       COALESCE(u.excess_volume, 0) AS excess_volume,
       COALESCE(u.excess_volume, 0) * 1.0 / p.total_volume AS pct_volume_excess,
       u.blocked_user_days
FROM u CROSS JOIN pop p;
