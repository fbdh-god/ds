-- A/B 检验：Organic（对照）vs Ads（实验），双比例 Z 检验
-- H0: 两组转化率无差异；α = 0.05

USE ecommerce;

-- MySQL 默认除法小数位不足会截断 1/n，导致 SE=0、z_score 除零报错
SET div_precision_increment = 10;

DROP TABLE IF EXISTS ab_test_data;
CREATE TABLE ab_test_data AS
SELECT
    CASE
        WHEN traffic_source = 'Organic' THEN 'control'
        WHEN traffic_source = 'Ads'     THEN 'treatment'
    END AS experiment_group,
    COUNT(*) AS total_sessions,
    SUM(stage_purchase) AS conversions,
    ROUND(SUM(stage_purchase) * 100.0 / COUNT(*), 4) AS conversion_rate_pct
FROM funnel_session
WHERE traffic_source IN ('Organic', 'Ads')
GROUP BY CASE
    WHEN traffic_source = 'Organic' THEN 'control'
    WHEN traffic_source = 'Ads'     THEN 'treatment'
END;

-- MySQL 无正态 CDF 函数，用 Z 临界值近似判断显著性
DROP TABLE IF EXISTS ab_test_result_final;
CREATE TABLE ab_test_result_final AS
SELECT
    'control (Organic)' AS group_a,
    'treatment (Ads)'   AS group_b,
    n_a, n_b, conv_a, conv_b,
    ROUND(conv_a / n_a * 100, 4) AS conv_rate_a,
    ROUND(conv_b / n_b * 100, 4) AS conv_rate_b,
    ROUND(pooled_p, 6) AS pooled_p,
    ROUND(se, 6) AS standard_error,
    ROUND(z_score, 4) AS z_score,
    CASE
        WHEN ABS(z_score) > 2.576 THEN '< 0.01（极显著）'
        WHEN ABS(z_score) > 1.96  THEN '< 0.05（显著）'
        WHEN ABS(z_score) > 1.645 THEN '< 0.10（弱显著）'
        ELSE '>= 0.10（不显著）'
    END AS p_value_range,
    CASE
        WHEN ABS(z_score) > 1.96 THEN '拒绝 H0，两组转化率有显著差异'
        ELSE '接受 H0，两组转化率无显著差异'
    END AS conclusion,
    ROUND((conv_b / n_b - conv_a / n_a) * 100, 4) AS lift_pct
FROM (
    SELECT
        n_a, n_b, conv_a, conv_b,
        (conv_a + conv_b) / (n_a + n_b) AS pooled_p,
        SQRT(((conv_a + conv_b) / (n_a + n_b)) * (1 - (conv_a + conv_b) / (n_a + n_b)) * (1 / n_a + 1 / n_b)) AS se,
        (conv_b / n_b - conv_a / n_a) / SQRT(((conv_a + conv_b) / (n_a + n_b)) * (1 - (conv_a + conv_b) / (n_a + n_b)) * (1 / n_a + 1 / n_b)) AS z_score
    FROM (
        SELECT
            SUM(CASE WHEN experiment_group = 'control'   THEN total_sessions END) AS n_a,
            SUM(CASE WHEN experiment_group = 'treatment' THEN total_sessions END) AS n_b,
            SUM(CASE WHEN experiment_group = 'control'   THEN conversions END)   AS conv_a,
            SUM(CASE WHEN experiment_group = 'treatment' THEN conversions END)   AS conv_b
        FROM ab_test_data
    ) s
) c;

DROP TABLE IF EXISTS ab_test_email_social;
CREATE TABLE ab_test_email_social AS
SELECT
    'Email'  AS group_a,
    'Social' AS group_b,
    n_email, n_social, conv_email, conv_social,
    ROUND(conv_email / n_email * 100, 4) AS conv_rate_email,
    ROUND(conv_social / n_social * 100, 4) AS conv_rate_social,
    ROUND(pooled_p, 6) AS pooled_p,
    ROUND(se, 6) AS se,
    ROUND(z_score, 4) AS z_score,
    CASE
        WHEN ABS(z_score) > 2.576 THEN '< 0.01（极显著）'
        WHEN ABS(z_score) > 1.96  THEN '< 0.05（显著）'
        WHEN ABS(z_score) > 1.645 THEN '< 0.10（弱显著）'
        ELSE '>= 0.10（不显著）'
    END AS p_value_range,
    CASE
        WHEN ABS(z_score) > 1.96 THEN '拒绝 H0，两组转化率有显著差异'
        ELSE '接受 H0，两组转化率无显著差异'
    END AS conclusion
FROM (
    SELECT
        n_email, n_social, conv_email, conv_social,
        (conv_email + conv_social) / (n_email + n_social) AS pooled_p,
        SQRT(((conv_email + conv_social) / (n_email + n_social)) * (1 - (conv_email + conv_social) / (n_email + n_social)) * (1 / n_email + 1 / n_social)) AS se,
        (conv_social / n_social - conv_email / n_email) / SQRT(((conv_email + conv_social) / (n_email + n_social)) * (1 - (conv_email + conv_social) / (n_email + n_social)) * (1 / n_email + 1 / n_social)) AS z_score
    FROM (
        SELECT
            SUM(CASE WHEN traffic_source = 'Email'  THEN 1 ELSE 0 END) AS n_email,
            SUM(CASE WHEN traffic_source = 'Social' THEN 1 ELSE 0 END) AS n_social,
            SUM(CASE WHEN traffic_source = 'Email'  THEN stage_purchase ELSE 0 END) AS conv_email,
            SUM(CASE WHEN traffic_source = 'Social' THEN stage_purchase ELSE 0 END) AS conv_social
        FROM funnel_session
        WHERE traffic_source IN ('Email', 'Social')
    ) s
) c;
