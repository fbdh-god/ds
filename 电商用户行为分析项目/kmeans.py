# -*- coding: utf-8 -*-
"""用户分群（K-Means）：切出非购买用户，对购买用户做 3~5 类聚类画像。"""
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
from common import *

ensure_dirs()
setup_style()

section("四、用户分群（K-Means）")

feat = pd.read_csv(os.path.join(RESULT_DIR, "user_features.csv"))
feat_cols = ["浏览次数", "加购次数", "购买次数", "客单价", "活跃天数", "平均会话时长(分钟)"]
n_users = len(feat)
print(f"用户特征表: {fmt(n_users)} 用户 × {len(feat_cols)} 特征")

buyers = feat[feat["购买次数"] > 0].copy()
nonbuyers = feat[feat["购买次数"] == 0]
n_buy = len(buyers)
n_nb = len(nonbuyers)
print("\n全量用户分层:")
print(f"  未购买用户(浏览/加购未购): {fmt(n_nb)}  ({pct(n_nb, n_users):.2f}%)")
print(f"  购买用户:                {fmt(n_buy)}  ({pct(n_buy, n_users):.2f}%)")
print("未购买用户占比过高(≈87%)，直接对全量聚类会被其主导，故只对购买用户做 3~5 类细分。")

Xb = buyers[feat_cols].astype("float64")
scaler = StandardScaler()
Xs = scaler.fit_transform(Xb)

SAMPLE = 200_000 if n_buy > 200_000 else n_buy
rng = np.random.default_rng(42)
idx = rng.choice(n_buy, size=SAMPLE, replace=False)
Xs_samp = Xs[idx]

K_RANGE = range(2, 9)
rows = []
for k in K_RANGE:
    km = KMeans(n_clusters=k, n_init=10, random_state=42)
    km.fit(Xs_samp)
    sil = silhouette_score(Xs_samp, km.labels_, sample_size=20000, random_state=42)
    rows.append({"K": k, "inertia(SSE)": round(km.inertia_, 1), "silhouette": round(sil, 4)})
    print(f"  K={k}: inertia={km.inertia_:,.1f}  silhouette={sil:.4f}")
kdf = pd.DataFrame(rows)
save(kdf, "kmeans_01_肘部法.csv")

k_sel = kdf[kdf["K"].between(3, 5)]
best = k_sel.loc[k_sel["silhouette"].idxmax()]
K = int(best["K"])
print(f"\n在 3~5 类内，选定 K = {K} (silhouette={best['silhouette']:.4f})")

km = KMeans(n_clusters=K, n_init=10, random_state=42)
km.fit(Xs_samp)
buyers["cluster"] = km.predict(Xs)

prof = buyers.groupby("cluster")[feat_cols].mean()
prof["人数"] = buyers.groupby("cluster").size()

# 频率档按购买次数均值排名，保证各类标签互不相同
FREQ_LABELS = {
    3: ["低频", "中频", "高频"],
    4: ["低频", "中低频", "中高频", "高频"],
    5: ["低频", "中低频", "中频", "中高频", "高频"],
}
freq_rank = prof["购买次数"].rank(method="first").astype(int) - 1
aov_thr = buyers["客单价"].mean()
print(f"\n购买用户平均客单价={aov_thr:.2f}")


def label_cluster(row):
    f = FREQ_LABELS[K][int(row["freq_rank"])]
    v = "高额" if row["客单价"] >= aov_thr else "低额"
    return f"{f}{v}买家"


prof["freq_rank"] = freq_rank
prof["标签"] = prof.apply(label_cluster, axis=1)
prof = prof.sort_values("人数", ascending=False).drop(columns=["freq_rank"])

nb_prof = nonbuyers[feat_cols].mean()
nb_row = nb_prof.to_dict()
nb_row["人数"] = n_nb
prof.loc["未购买用户"] = nb_row
prof["标签"] = prof["标签"].fillna("未购买用户(纯浏览/加购未购)")

prof["占比%"] = (100.0 * prof["人数"] / n_users).round(2)
prof_out = prof.reset_index().rename(columns={"cluster": "类编号"})
cols = ["类编号", "标签", "人数", "占比%"] + feat_cols
prof_out = prof_out[cols]
print("\n聚类画像（各类特征均值，含未购买用户大段）:")
print(prof_out.round(3).to_string(index=False))
save(prof_out, "kmeans_02_聚类画像.csv")

cnt = prof_out[["类编号", "标签", "人数", "占比%"]].copy()
print("\n各类用户人数与占比:")
print(cnt.round(2).to_string(index=False))
save(cnt, "kmeans_03_聚类人数.csv")

fig, ax = plt.subplots(figsize=(7, 4.5))
ax.plot(kdf["K"], kdf["inertia(SSE)"], marker="o", color=CAT[0], lw=2, label="inertia(SSE)")
ax.axvline(K, color=CAT[2], ls="--", lw=1, label=f"选定 K={K}")
ax.set_title("肘部法：购买用户 SSE 随 K 变化")
ax.set_xlabel("K")
ax.set_ylabel("SSE（簇内平方和）")
ax.legend()
ax.spines[["top", "right"]].set_visible(False)
savefig(fig, "kmeans_肘部法.png")

fig, ax = plt.subplots(figsize=(7, 4.5))
ax.plot(kdf["K"], kdf["silhouette"], marker="o", color=CAT[1], lw=2)
ax.axvline(K, color=CAT[2], ls="--", lw=1)
ax.set_title("轮廓系数随 K 变化（购买用户）")
ax.set_xlabel("K")
ax.set_ylabel("silhouette")
ax.spines[["top", "right"]].set_visible(False)
savefig(fig, "kmeans_轮廓系数.png")

buy_prof = buyers.groupby("cluster")[feat_cols].mean()
fig, ax = plt.subplots(figsize=(9, 5))
norm_prof = (buy_prof - buy_prof.mean()) / buy_prof.std()
norm_prof.T.plot.bar(ax=ax, color=CAT[:K], width=0.8)
ax.axhline(0, color=INK, lw=0.8)
ax.set_title("购买用户各聚类标准化特征对比（标签见 CSV 画像）")
ax.set_ylabel("标准化均值")
ax.set_xticklabels(ax.get_xticklabels(), rotation=20)
ax.legend(title="类", ncol=2, fontsize=8)
ax.spines[["top", "right"]].set_visible(False)
savefig(fig, "kmeans_画像对比.png")

pca = PCA(n_components=2, random_state=42)
Xp = pca.fit_transform(Xs[idx])
sc = pd.DataFrame({"PC1": Xp[:, 0], "PC2": Xp[:, 1],
                   "cluster": km.predict(Xs[idx]).astype(str)})
fig, ax = plt.subplots(figsize=(8, 6))
for k in sorted(sc["cluster"].unique(), key=int):
    ssub = sc[sc["cluster"] == k]
    ax.scatter(ssub["PC1"], ssub["PC2"], s=3, alpha=0.35, color=CAT[int(k) % 8], label=f"类{k}")
ax.set_title("购买用户 K-Means 聚类（PCA 2D 投影，抽样20万）")
ax.set_xlabel("PC1")
ax.set_ylabel("PC2")
ax.legend(markerscale=4, fontsize=8)
ax.spines[["top", "right"]].set_visible(False)
savefig(fig, "kmeans_PCA散点.png")

section("第四节完成")
print("结果已保存至 results/。")
