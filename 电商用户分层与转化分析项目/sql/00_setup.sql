

CREATE DATABASE IF NOT EXISTS ecommerce
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_unicode_ci;

USE ecommerce;

DROP TABLE IF EXISTS stg_customers;
CREATE TABLE stg_customers (
    customer_id          INT PRIMARY KEY,
    age                  INT,
    country_code         VARCHAR(10),
    region               VARCHAR(20),
    signup_date          DATE,
    loyalty_score        DECIMAL(4,3),
    email_open_rate      DECIMAL(6,3),
    discount_usage_rate  DECIMAL(6,3),
    avg_review_score     DECIMAL(4,2),
    referral_code        VARCHAR(20),
    customer_tier        VARCHAR(10),
    credit_limit         VARCHAR(20)   -- 原始为 "$10,966" 格式，暂存字符串
);

DROP TABLE IF EXISTS stg_sessions;
CREATE TABLE stg_sessions (
    session_id        BIGINT PRIMARY KEY,
    customer_id       INT,
    session_timestamp DATE,
    session_duration  DECIMAL(10,2),
    pages_viewed      INT,
    cart_additions    INT,
    bounce_flag       VARCHAR(10),
    traffic_source    VARCHAR(20),
    device_type       VARCHAR(20),
    campaign_id       INT,
    geo_ip_region     VARCHAR(20)
);

DROP TABLE IF EXISTS stg_transactions;
CREATE TABLE stg_transactions (
    transaction_id        BIGINT PRIMARY KEY,
    customer_id           INT,
    transaction_timestamp DATE,
    order_value           VARCHAR(20),   -- 原始为 "$20.39" 格式
    items_count           INT,
    payment_method        VARCHAR(20),
    discount_applied      VARCHAR(10),
    shipping_speed        VARCHAR(20),
    high_value_flag       VARCHAR(5)
);

DROP TABLE IF EXISTS stg_geo_data;
CREATE TABLE stg_geo_data (
    geo_ip_region        VARCHAR(20) PRIMARY KEY,
    average_income       DECIMAL(12,2),
    urban_ratio          DECIMAL(6,4),
    internet_penetration DECIMAL(6,4),
    region_tier          VARCHAR(10)
);

DROP TABLE IF EXISTS stg_marketing_campaigns;
CREATE TABLE stg_marketing_campaigns (
    campaign_id     INT PRIMARY KEY,
    campaign_type   VARCHAR(20),
    campaign_budget VARCHAR(20),   -- 原始为 "$46,187" 格式
    region_target   VARCHAR(20),
    start_date      DATE,
    end_date        DATE
);

DROP TABLE IF EXISTS stg_train;
CREATE TABLE stg_train (
    customer_id INT PRIMARY KEY,
    target      INT
);
