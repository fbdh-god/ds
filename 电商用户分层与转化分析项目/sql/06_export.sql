-- 导出结果表为 CSV（供 Tableau 连接）
USE ecommerce;

SELECT * FROM rfm_segments
INTO OUTFILE 'F:/mysql/Uploads/rfm_segments.csv'
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\n';

SELECT * FROM rfm_segment_summary
INTO OUTFILE 'F:/mysql/Uploads/rfm_segment_summary.csv'
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\n';

SELECT * FROM funnel_overall
INTO OUTFILE 'F:/mysql/Uploads/funnel_overall.csv'
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\n';

SELECT * FROM funnel_by_channel
INTO OUTFILE 'F:/mysql/Uploads/funnel_by_channel.csv'
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\n';

SELECT * FROM funnel_by_device
INTO OUTFILE 'F:/mysql/Uploads/funnel_by_device.csv'
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\n';

SELECT * FROM channel_conversion
INTO OUTFILE 'F:/mysql/Uploads/channel_conversion.csv'
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\n';

SELECT * FROM revenue_by_first_touch
INTO OUTFILE 'F:/mysql/Uploads/revenue_by_first_touch.csv'
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\n';

SELECT * FROM revenue_by_last_touch
INTO OUTFILE 'F:/mysql/Uploads/revenue_by_last_touch.csv'
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\n';

SELECT * FROM campaign_roi
INTO OUTFILE 'F:/mysql/Uploads/campaign_roi.csv'
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\n';

SELECT * FROM ab_test_result_final
INTO OUTFILE 'F:/mysql/Uploads/ab_test_result.csv'
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\n';

SELECT * FROM ab_test_email_social
INTO OUTFILE 'F:/mysql/Uploads/ab_test_email_social.csv'
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\n';
