-- id: M050
-- name: mart_usage_pareto
-- business_question: How concentrated is usage? Which users make up 80% of inserted assets in the trailing 30 and 90 days?
-- tables: fact_user_daily_usage, dim_date, mart_user_lifecycle, v_as_of
-- grain: one row per user x window (30d, 90d) for users with at least one insertion in the window
-- output: total_assets, active_days, avg_assets_per_active_day, monthly_assets (window total normalised to 30 days), usage_quartile (4 = heaviest), cum_share_users, cum_share_assets, in_top80_volume
-- replaces: Notebooks 2 and 3 (Pareto of usage, quartiles, 30d/90d windows, monthly normalisation)
-- kind: mart
CREATE OR REPLACE VIEW mart_usage_pareto AS
WITH win AS (
    SELECT w.window_days, a.as_of_date, a.as_of_date - CAST(w.window_days - 1 AS INTEGER) AS win_start
    FROM (VALUES (30), (90)) AS w(window_days) CROSS JOIN v_as_of a
),
agg AS (
    SELECT w.window_days, f.user_key,
           SUM(f.assets_inserted) AS total_assets, COUNT(*) AS active_days, MAX(f.assets_inserted) AS max_daily_assets
    FROM fact_user_daily_usage f
    JOIN dim_date d ON d.date_key = f.date_key
    JOIN win w ON d.date BETWEEN w.win_start AND w.as_of_date
    GROUP BY w.window_days, f.user_key
),
ranked AS (
    SELECT agg.*,
           SUM(total_assets) OVER (PARTITION BY window_days ORDER BY total_assets DESC, user_key) AS cum_assets,
           SUM(total_assets) OVER (PARTITION BY window_days) AS all_assets,
           ROW_NUMBER() OVER (PARTITION BY window_days ORDER BY total_assets DESC, user_key) AS rnk,
           COUNT(*) OVER (PARTITION BY window_days) AS n_users,
           NTILE(4) OVER (PARTITION BY window_days ORDER BY total_assets, user_key) AS usage_quartile
    FROM agg
)
SELECT r.window_days, r.user_key, l.country_code, l.current_tier, l.is_paying_now, l.signup_month_key,
       year(l.signup_date) AS signup_year,
       r.total_assets, r.active_days, r.max_daily_assets,
       r.total_assets * 1.0 / r.active_days AS avg_assets_per_active_day,
       r.total_assets * 30.0 / r.window_days AS monthly_assets,
       r.usage_quartile, r.rnk AS volume_rank,
       r.rnk * 1.0 / r.n_users AS cum_share_users,
       r.cum_assets * 1.0 / r.all_assets AS cum_share_assets,
       (r.cum_assets - r.total_assets) * 1.0 / r.all_assets < 0.8 AS in_top80_volume
FROM ranked r JOIN mart_user_lifecycle l ON l.user_key = r.user_key;
