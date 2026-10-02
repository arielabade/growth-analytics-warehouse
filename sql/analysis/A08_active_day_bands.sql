-- id: A08
-- name: Bands of active days
-- business_question: How many users use the product on 1, 2-3, 4-7, 8-14, 15-30, 31+ days of the window, and how much volume do they produce?
-- tables: mart_usage_pareto
-- grain: one row per window x active-days band
-- output: users, share_of_users, total_assets, share_of_volume
-- replaces: Notebook 3 (days with use)
-- kind: analysis
WITH b AS (
    SELECT window_days, total_assets,
           CASE WHEN active_days = 1 THEN '1' WHEN active_days <= 3 THEN '2-3' WHEN active_days <= 7 THEN '4-7'
                WHEN active_days <= 14 THEN '8-14' WHEN active_days <= 30 THEN '15-30' ELSE '31+' END AS band,
           CASE WHEN active_days = 1 THEN 1 WHEN active_days <= 3 THEN 2 WHEN active_days <= 7 THEN 3
                WHEN active_days <= 14 THEN 4 WHEN active_days <= 30 THEN 5 ELSE 6 END AS band_order
    FROM mart_usage_pareto
)
SELECT window_days, band, band_order, COUNT(*) AS users,
       COUNT(*) * 1.0 / SUM(COUNT(*)) OVER (PARTITION BY window_days) AS share_of_users,
       SUM(total_assets) AS total_assets,
       SUM(total_assets) * 1.0 / SUM(SUM(total_assets)) OVER (PARTITION BY window_days) AS share_of_volume
FROM b GROUP BY window_days, band, band_order
ORDER BY window_days, band_order;
