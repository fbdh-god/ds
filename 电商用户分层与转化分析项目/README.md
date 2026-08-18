# 电商用户分层与转化分析项目

基于 Global E-Commerce 数据集，用 MySQL 完成 RFM 分群、转化漏斗、渠道归因和 A/B 检验，再用 Tableau 出图。

## 数据

Kaggle 的 [Global E-Commerce Customer Purchase Prediction](https://www.kaggle.com/datasets/atharvavader/global-ecommerce-customer-purchase-prediction)，含客户、会话、交易、地理、营销活动五类数据。

| 表 | 行数 | 说明 |
|---|---|---|
| customers | 200,000 | 客户基础信息 |
| sessions | 2,000,000 | 会话行为日志 |
| transactions | 500,000 | 交易记录 |
| geo_data | 100 | 地区维度 |
| marketing_campaigns | 200 | 营销活动 |

## 分析

- **RFM 分群**：R / F / M 各按 `NTILE()` 打分，组合成 8 类客户
- **转化漏斗**：Visit → Browse → Add to Cart → Purchase，按渠道 / 设备拆分
- **渠道归因**：first-touch / last-touch 两种模型 + 营销活动 ROI
- **A/B 检验**：双比例 Z 检验（Organic vs Ads、Email vs Social）

## 结构

```
├── sql/            # SQL 脚本（建表 → 清洗 → 分析 → 导出）
├── output/         # 分析结果 CSV
└── dashboards/     # Tableau 仪表盘截图
```

## 数据清洗

原始数据有 7 类脏数据，集中在 `sql/01_clean.sql`：

| 问题 | 示例 | 处理 |
|---|---|---|
| 国家编码不统一 | usa / USA / U.S. | 归一化为 US / GB / DE 等 |
| 金额带符号千分位 | "$10,966" | 去符号转 DECIMAL |
| 布尔值多格式 | 0/1/TRUE/FALSE/Yes/No | 统一为 0/1 |
| 大小写不统一 | organic / Organic | 首字母大写统一 |
| 缺失值 | email_open_rate 11.37% 缺失 | 中位数填充 |
| 设备类型不统一 | TABLET | 首字母大写统一 |
| 噪声列 | noise_* | 导入时跳过 |

## 运行

1. 建库建表：执行 `sql/00_setup.sql`
2. 导入原始 CSV（Workbench 导入向导，跳过 noise 列）
3. 依次执行 `sql/01_clean.sql` → `02_rfm.sql` → `03_funnel.sql` → `04_attribution.sql` → `05_abtest.sql`
4. 导出结果：`sql/06_export.sql` 或 Workbench 导出向导
5. Tableau 连接 `output/` 下的 CSV 出图

## 主要结论

- Champions 占客户 17.8%，贡献最高收入（20.4M）；Lost 占比最大（22%）但收入最低
- 整体转化率约 1.93%，四个渠道差异不大
- 各渠道 first-touch 收入均高于 last-touch，首触渠道长期价值更高
- Organic vs Ads、Email vs Social 转化率差异均不显著（Z 检验 p > 0.10）
