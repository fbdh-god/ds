-- 渠道归因：first-touch / last-touch 两种模型 + 营销活动 ROI

USE ecommerce;

DROP TABLE IF EXISTS attribution_first_touch;
CREATE TABLE attribution_first_touch AS
SELECT
    customer_id,
    traffic_source AS first_touch_channel,
    session_timestamp AS first_touch_date
FROM (
    SELECT
        customer_id,
        traffic_source,
        session_timestamp,
        ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY session_timestamp ASC) AS rn
    FROM fct_sessions
) ranked
WHERE rn = 1;

DROP TABLE IF EXISTS attribution_last_touch;
CREATE TABLE attribution_last_touch AS
SELECT
    t.customer_id,
    t.transaction_id,
    s.traffic_source AS last_touch_channel,
    s.session_timestamp AS last_touch_date,
    t.order_value,
    t.transaction_timestamp
FROM fct_transactions t
INNER JOIN (
    SELECT
        transaction_id,
        traffic_source,
        session_timestamp,
        ROW_NUMBER() OVER (
            PARTITION BY transaction_id
            ORDER BY session_timestamp DESC
        ) AS rn
    FROM (
        SELECT
            t2.transaction_id,
            s.traffic_source,
            s.session_timestamp
        FROM fct_sessions s
        INNER JOIN fct_transactions t2
            ON s.customer_id = t2.customer_id
            AND s.session_timestamp <= t2.transaction_timestamp
    ) joined
) s ON t.transaction_id = s.transaction_id AND s.rn = 1;

DROP TABLE IF EXISTS revenue_by_first_touch;
CREATE TABLE revenue_by_first_touch AS
SELECT
    ft.first_touch_channel AS channel,
    COUNT(DISTINCT ft.customer_id) AS customers,
    COUNT(t.transaction_id)        AS orders,
    ROUND(SUM(t.order_value), 2)   AS revenue,
    ROUND(AVG(t.order_value), 2)   AS avg_order_value
FROM attribution_first_touch ft
LEFT JOIN fct_transactions t ON ft.customer_id = t.customer_id
GROUP BY ft.first_touch_channel
ORDER BY revenue DESC;

DROP TABLE IF EXISTS revenue_by_last_touch;
CREATE TABLE revenue_by_last_touch AS
SELECT
    last_touch_channel AS channel,
    COUNT(DISTINCT customer_id) AS customers,
    COUNT(transaction_id)       AS orders,
    ROUND(SUM(order_value), 2)  AS revenue,
    ROUND(AVG(order_value), 2)  AS avg_order_value
FROM attribution_last_touch
GROUP BY last_touch_channel
ORDER BY revenue DESC;

DROP TABLE IF EXISTS campaign_roi;
CREATE TABLE campaign_roi AS
SELECT
    b.campaign_type,
    b.campaign_count,
    b.total_budget,
    s.attributed_sessions,
    COALESCE(r.attributed_revenue, 0) AS attributed_revenue,
    ROUND(
        (COALESCE(r.attributed_revenue, 0) - b.total_budget) / b.total_budget * 100, 2
    ) AS roi_pct
FROM (
    SELECT
        campaign_type,
        COUNT(DISTINCT campaign_id) AS campaign_count,
        ROUND(SUM(campaign_budget), 2) AS total_budget
    FROM dim_campaigns
    GROUP BY campaign_type
) b
LEFT JOIN (
    SELECT
        mc.campaign_type,
        COUNT(DISTINCT s.session_id) AS attributed_sessions
    FROM dim_campaigns mc
    JOIN fct_sessions s ON s.campaign_id = mc.campaign_id
    GROUP BY mc.campaign_type
) s ON s.campaign_type = b.campaign_type
LEFT JOIN (
    -- 每位客户按最近一次带 campaign 的会话归属，避免同一客户被多个类型重复计数
    SELECT
        mc.campaign_type,
        ROUND(SUM(t.order_value), 2) AS attributed_revenue
    FROM (
        SELECT customer_id, campaign_id
        FROM (
            SELECT customer_id, campaign_id,
                   ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY session_timestamp DESC) AS rn
            FROM fct_sessions
            WHERE campaign_id IS NOT NULL
        ) ranked
        WHERE rn = 1
    ) cust
    JOIN dim_campaigns mc ON mc.campaign_id = cust.campaign_id
    JOIN fct_transactions t ON t.customer_id = cust.customer_id
    GROUP BY mc.campaign_type
) r ON r.campaign_type = b.campaign_type
ORDER BY attributed_revenue DESC;

DROP TABLE IF EXISTS channel_comparison;
CREATE TABLE channel_comparison AS
SELECT
    f.channel,
    f.revenue AS first_touch_revenue,
    l.revenue AS last_touch_revenue,
    ROUND((l.revenue - f.revenue) / f.revenue * 100, 2) AS revenue_diff_pct
FROM revenue_by_first_touch f
LEFT JOIN revenue_by_last_touch l ON f.channel = l.channel;
