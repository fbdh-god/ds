-- 转化漏斗（session 级）：Visit → Browse → Add to Cart → Purchase（7 日内成交）

USE ecommerce;

DROP TABLE IF EXISTS funnel_session;
CREATE TABLE funnel_session AS
SELECT
    s.session_id,
    s.customer_id,
    s.traffic_source,
    s.device_type,
    s.session_timestamp,
    1 AS stage_visit,
    CASE WHEN s.bounce_flag = 0 THEN 1 ELSE 0 END AS stage_browse,
    CASE WHEN s.bounce_flag = 0 AND s.cart_additions > 0 THEN 1 ELSE 0 END AS stage_cart,
    -- 购买归属到成交前最近一次会话、且仅限 7 日内，避免同一笔交易被多个会话重复计数
    CASE WHEN EXISTS (
        SELECT 1 FROM fct_transactions t
        WHERE t.customer_id = s.customer_id
          AND t.transaction_timestamp >= s.session_timestamp
          AND t.transaction_timestamp <= DATE_ADD(s.session_timestamp, INTERVAL 7 DAY)
          AND NOT EXISTS (
              SELECT 1 FROM fct_sessions s2
              WHERE s2.customer_id = s.customer_id
                AND s2.session_timestamp > s.session_timestamp
                AND s2.session_timestamp <= t.transaction_timestamp
          )
    ) THEN 1 ELSE 0 END AS stage_purchase
FROM fct_sessions s;

DROP TABLE IF EXISTS funnel_overall;
CREATE TABLE funnel_overall AS
SELECT 'Visit' AS stage_name, 1 AS stage_order, SUM(stage_visit) AS sessions, COUNT(*) AS total
FROM funnel_session
UNION ALL
SELECT 'Browse', 2, SUM(stage_browse), COUNT(*)
FROM funnel_session
UNION ALL
SELECT 'Add to Cart', 3, SUM(stage_cart), COUNT(*)
FROM funnel_session
UNION ALL
SELECT 'Purchase', 4, SUM(stage_purchase), COUNT(*)
FROM funnel_session;

DROP TABLE IF EXISTS funnel_by_channel;
CREATE TABLE funnel_by_channel AS
SELECT traffic_source AS channel, 'Visit' AS stage_name, 1 AS stage_order, SUM(stage_visit) AS sessions
FROM funnel_session GROUP BY traffic_source
UNION ALL
SELECT traffic_source, 'Browse', 2, SUM(stage_browse)
FROM funnel_session GROUP BY traffic_source
UNION ALL
SELECT traffic_source, 'Add to Cart', 3, SUM(stage_cart)
FROM funnel_session GROUP BY traffic_source
UNION ALL
SELECT traffic_source, 'Purchase', 4, SUM(stage_purchase)
FROM funnel_session GROUP BY traffic_source;

DROP TABLE IF EXISTS funnel_by_device;
CREATE TABLE funnel_by_device AS
SELECT device_type AS device, 'Visit' AS stage_name, 1 AS stage_order, SUM(stage_visit) AS sessions
FROM funnel_session GROUP BY device_type
UNION ALL
SELECT device_type, 'Browse', 2, SUM(stage_browse)
FROM funnel_session GROUP BY device_type
UNION ALL
SELECT device_type, 'Add to Cart', 3, SUM(stage_cart)
FROM funnel_session GROUP BY device_type
UNION ALL
SELECT device_type, 'Purchase', 4, SUM(stage_purchase)
FROM funnel_session GROUP BY device_type;

DROP TABLE IF EXISTS channel_conversion;
CREATE TABLE channel_conversion AS
SELECT
    f.traffic_source AS channel,
    SUM(f.stage_visit)    AS total_sessions,
    SUM(f.stage_browse)   AS browse_sessions,
    SUM(f.stage_cart)     AS cart_sessions,
    SUM(f.stage_purchase) AS purchase_sessions,
    ROUND(SUM(f.stage_browse)   * 100.0 / NULLIF(SUM(f.stage_visit), 0), 2) AS browse_rate,
    ROUND(SUM(f.stage_cart)     * 100.0 / NULLIF(SUM(f.stage_browse), 0), 2) AS cart_rate,
    ROUND(SUM(f.stage_purchase) * 100.0 / NULLIF(SUM(f.stage_cart), 0), 2)  AS purchase_rate,
    ROUND(SUM(f.stage_purchase) * 100.0 / NULLIF(SUM(f.stage_visit), 0), 2) AS overall_conv_rate
FROM funnel_session f
GROUP BY f.traffic_source
ORDER BY overall_conv_rate DESC;
