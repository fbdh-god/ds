-- 数据清洗

USE ecommerce;

DROP TABLE IF EXISTS dim_customers;

-- email_open_rate 缺失值用中位数填充
SET @med_email_open := (
    SELECT AVG(eor)
    FROM (
        SELECT email_open_rate AS eor,
               ROW_NUMBER() OVER (ORDER BY email_open_rate) AS rn,
               COUNT(*) OVER () AS cnt
        FROM stg_customers
        WHERE email_open_rate IS NOT NULL
    ) t
    WHERE rn IN (FLOOR((cnt + 1) / 2), CEIL((cnt + 1) / 2))
);

CREATE TABLE dim_customers AS
SELECT
    customer_id,
    age,
    CASE
        WHEN country_code IN ('usa', 'US', 'USA', 'U.S.') THEN 'US'
        WHEN country_code IN ('uk', 'UK')                  THEN 'GB'
        WHEN country_code IN ('de', 'DE')                  THEN 'DE'
        WHEN country_code = 'FR'                           THEN 'FR'
        WHEN country_code = 'IN'                           THEN 'IN'
        ELSE UPPER(country_code)
    END AS country_code,
    region,
    signup_date,
    loyalty_score,
    COALESCE(email_open_rate, @med_email_open) AS email_open_rate,
    discount_usage_rate,
    avg_review_score,
    referral_code,
    customer_tier,
    CAST(REPLACE(REPLACE(credit_limit, '$', ''), ',', '') AS DECIMAL(10, 2)) AS credit_limit
FROM stg_customers;

CREATE INDEX idx_cust_country ON dim_customers(country_code);
CREATE INDEX idx_cust_tier    ON dim_customers(customer_tier);

DROP TABLE IF EXISTS fct_sessions;
CREATE TABLE fct_sessions AS
SELECT
    session_id,
    customer_id,
    session_timestamp,
    session_duration,
    pages_viewed,
    cart_additions,
    CASE
        WHEN bounce_flag IN ('0', 'FALSE', 'No')  THEN 0
        WHEN bounce_flag IN ('1', 'TRUE', 'Yes')  THEN 1
        ELSE NULL
    END AS bounce_flag,
    CASE
        WHEN traffic_source IN ('organic', 'Organic') THEN 'Organic'
        WHEN traffic_source IN ('ads', 'Ads')         THEN 'Ads'
        WHEN traffic_source = 'SOCIAL'                 THEN 'Social'
        WHEN traffic_source = 'email'                  THEN 'Email'
        ELSE traffic_source
    END AS traffic_source,
    CASE
        WHEN device_type IN ('desktop', 'Desktop') THEN 'Desktop'
        WHEN device_type IN ('mobile', 'Mobile')   THEN 'Mobile'
        WHEN device_type = 'TABLET'                 THEN 'Tablet'
        ELSE device_type
    END AS device_type,
    campaign_id,
    geo_ip_region
FROM stg_sessions;

CREATE INDEX idx_sess_cust    ON fct_sessions(customer_id);
CREATE INDEX idx_sess_channel ON fct_sessions(traffic_source);
CREATE INDEX idx_sess_device  ON fct_sessions(device_type);
CREATE INDEX idx_sess_date    ON fct_sessions(session_timestamp);

DROP TABLE IF EXISTS fct_transactions;
CREATE TABLE fct_transactions AS
SELECT
    transaction_id,
    customer_id,
    transaction_timestamp,
    CAST(REPLACE(REPLACE(order_value, '$', ''), ',', '') AS DECIMAL(10, 2)) AS order_value,
    items_count,
    payment_method,
    CASE
        WHEN discount_applied IN ('0', 'FALSE', 'No')  THEN 0
        WHEN discount_applied IN ('1', 'TRUE', 'Yes')  THEN 1
        ELSE NULL
    END AS discount_applied,
    CASE
        WHEN shipping_speed = 'standard'  THEN 'Standard'
        WHEN shipping_speed = 'express'   THEN 'Express'
        WHEN shipping_speed = 'overnight' THEN 'Overnight'
        ELSE shipping_speed
    END AS shipping_speed,
    CASE
        WHEN high_value_flag = 'Yes' THEN 1
        WHEN high_value_flag = 'No'  THEN 0
        ELSE NULL
    END AS high_value_flag
FROM stg_transactions;

CREATE INDEX idx_trans_cust ON fct_transactions(customer_id);
CREATE INDEX idx_trans_date ON fct_transactions(transaction_timestamp);

DROP TABLE IF EXISTS dim_campaigns;
CREATE TABLE dim_campaigns AS
SELECT
    campaign_id,
    campaign_type,
    CAST(REPLACE(REPLACE(campaign_budget, '$', ''), ',', '') AS DECIMAL(12, 2)) AS campaign_budget,
    region_target,
    start_date,
    end_date
FROM stg_marketing_campaigns;

DROP TABLE IF EXISTS dim_geo;
CREATE TABLE dim_geo AS
SELECT
    geo_ip_region,
    average_income,
    urban_ratio,
    internet_penetration,
    region_tier
FROM stg_geo_data;
