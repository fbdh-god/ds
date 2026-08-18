-- RFM 分群：R=最近购买距今、F=购买次数、M=累计消费

USE ecommerce;

DROP TABLE IF EXISTS rfm_raw;
CREATE TABLE rfm_raw AS
SELECT
    t.customer_id,
    DATEDIFF(
        (SELECT MAX(transaction_timestamp) FROM fct_transactions),
        MAX(t.transaction_timestamp)
    ) AS recency,
    COUNT(t.transaction_id) AS frequency,
    ROUND(SUM(t.order_value), 2) AS monetary
FROM fct_transactions t
GROUP BY t.customer_id;

DROP TABLE IF EXISTS rfm_scores;
CREATE TABLE rfm_scores AS
SELECT
    customer_id,
    recency,
    frequency,
    monetary,
    -- recency 越小越优，其余越大越优，用 6 - NTILE 统一成高分=好
    6 - NTILE(5) OVER (ORDER BY recency ASC)    AS r_score,
    6 - NTILE(5) OVER (ORDER BY frequency DESC) AS f_score,
    6 - NTILE(5) OVER (ORDER BY monetary DESC)  AS m_score
FROM rfm_raw;

DROP TABLE IF EXISTS rfm_segments;
CREATE TABLE rfm_segments AS
SELECT
    s.customer_id,
    recency,
    frequency,
    monetary,
    r_score,
    f_score,
    m_score,
    (r_score + f_score + m_score) AS rfm_total,
    CONCAT(r_score, f_score, m_score) AS rfm_segment_code,
    CASE
        WHEN r_score >= 4 AND f_score >= 4 AND m_score >= 4 THEN 'Champions'
        WHEN f_score >= 4 AND m_score >= 3                   THEN 'Loyal Customers'
        WHEN r_score >= 4 AND f_score = 1                    THEN 'New Customers'
        WHEN r_score >= 4 AND f_score = 2                    THEN 'Promising'
        WHEN r_score = 3 AND f_score BETWEEN 2 AND 3         THEN 'Need Attention'
        WHEN r_score >= 3 AND f_score >= 2                   THEN 'Potential Loyalist'
        WHEN r_score <= 2 AND f_score >= 3                   THEN 'At Risk'
        WHEN r_score <= 2 AND f_score <= 2                   THEN 'Lost'
        ELSE 'Others'
    END AS customer_segment,
    c.customer_tier,
    c.country_code,
    c.loyalty_score,
    c.signup_date
FROM rfm_scores s
LEFT JOIN dim_customers c ON s.customer_id = c.customer_id;

CREATE INDEX idx_rfm_segment ON rfm_segments(customer_segment);

DROP TABLE IF EXISTS rfm_segment_summary;
CREATE TABLE rfm_segment_summary AS
SELECT
    customer_segment,
    COUNT(*) AS customer_count,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM rfm_segments), 2) AS pct,
    ROUND(AVG(recency), 1)   AS avg_recency,
    ROUND(AVG(frequency), 1) AS avg_frequency,
    ROUND(AVG(monetary), 2)  AS avg_monetary,
    ROUND(SUM(monetary), 2)  AS total_revenue
FROM rfm_segments
GROUP BY customer_segment
ORDER BY total_revenue DESC;
