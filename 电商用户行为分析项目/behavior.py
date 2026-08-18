# -*- coding: utf-8 -*-
"""用户行为分析：转化漏斗 / 购买路径 / 复购 / RFM，并导出用户特征表供 KMeans。"""
import sys
import numpy as np
import pandas as pd
from collections import Counter
from common import *

ensure_dirs()
setup_style()
SMOKE = "--smoke" in sys.argv
MAX_CHUNKS = 3 if SMOKE else None

section("三、用户行为分析")
print("清洗+聚合 单趟分块读取" + ("  [SMOKE]" if SMOKE else ""))

agg = UserAgg()
etype_clean = Counter()
l1 = {"view": Counter(), "cart": Counter(), "purchase": Counter()}
max_pur_day = -1


def process(name, path, max_chunks):
    global max_pur_day
    it = iter_chunks(path)
    nc = 0
    for raw in it:
        nc += 1
        if max_chunks and nc > max_chunks:
            break
        chunk = clean_chunk(raw)
        if len(chunk) == 0:
            continue
        vc = chunk["event_type"].value_counts()
        for et, c in vc.items():
            etype_clean[et] += c
        for et in ["view", "cart", "purchase"]:
            l1[et].update(chunk.loc[chunk["event_type"] == et, "cat_level1"].value_counts().to_dict())
        is_pur = chunk["event_type"] == "purchase"
        day = day_index(chunk["event_time"])
        dayn = day.to_numpy()
        is_pur_n = is_pur.to_numpy()
        if is_pur_n.any():
            max_pur_day = max(max_pur_day, int(dayn[is_pur_n].max()))
        values = {
            "n_view": (chunk["event_type"] == "view").astype("int64").to_numpy(),
            "n_cart": (chunk["event_type"] == "cart").astype("int64").to_numpy(),
            "n_pur": is_pur_n.astype("int64"),
            "spend": chunk["price"].where(is_pur, 0.0).to_numpy(),
            "first_pur_day": np.where(is_pur_n, dayn, 999),
            "last_pur_day": np.where(is_pur_n, dayn, -1),
            "days_mask": np.left_shift(np.int64(1), dayn),
        }
        agg.add(chunk["user_id"].to_numpy(), values)
        sess = chunk.groupby("user_session", sort=False).agg(
            user_id=("user_id", "first"),
            t_min=("event_time", "min"), t_max=("event_time", "max"))
        sess["dur"] = (sess["t_max"] - sess["t_min"]).dt.total_seconds() / 60.0
        sess_u = sess.groupby("user_id", sort=False)["dur"].agg(["sum", "size"])
        agg.add(sess_u.index.to_numpy(),
                {"sum_dur": sess_u["sum"].to_numpy(), "n_sess": sess_u["size"].to_numpy()})
        if nc % 5 == 0:
            print(f"  [{name}] chunk {nc}")


process("Oct", FILES["Oct"], MAX_CHUNKS)
process("Nov", FILES["Nov"], MAX_CHUNKS)

section("用户特征表")
uf = agg.to_frame()
n_users = len(uf)
print(f"独立用户数: {fmt(n_users)}")
uf["客单价"] = uf["spend"] / uf["n_pur"].replace(0, np.nan)
uf["活跃天数"] = np.bitwise_count(uf["days_mask"].to_numpy(dtype=np.int64))
uf["平均会话时长(分钟)"] = uf["sum_dur"] / uf["n_sess"].replace(0, np.nan)
feat = uf[["user_id", "n_view", "n_cart", "n_pur", "客单价", "活跃天数", "平均会话时长(分钟)"]].copy()
feat.columns = ["user_id", "浏览次数", "加购次数", "购买次数", "客单价", "活跃天数", "平均会话时长(分钟)"]
feat["客单价"] = feat["客单价"].fillna(0.0)
feat["平均会话时长(分钟)"] = feat["平均会话时长(分钟)"].fillna(0.0)
save(feat, "user_features.csv")
print("用户特征表已保存 user_features.csv")

section("1. 转化漏斗")
ev = {e: etype_clean.get(e, 0) for e in ["view", "cart", "purchase"]}
ev_u = {
    "view": int((uf["n_view"] > 0).sum()),
    "cart": int((uf["n_cart"] > 0).sum()),
    "purchase": int((uf["n_pur"] > 0).sum()),
}
funnel = pd.DataFrame({
    "阶段": ["view(浏览)", "cart(加购)", "purchase(购买)"],
    "事件数": [ev["view"], ev["cart"], ev["purchase"]],
    "用户数": [ev_u["view"], ev_u["cart"], ev_u["purchase"]],
})
funnel["用户转化率%"] = [100.0, 100.0 * ev_u["cart"] / ev_u["view"], 100.0 * ev_u["purchase"] / ev_u["cart"]]
print("三阶段漏斗（事件级 & 用户级）:")
print(funnel.to_string(index=False))
print(f"\n事件级转化率: view→cart {pct(ev['cart'],ev['view']):.3f}%   "
      f"cart→purchase {pct(ev['purchase'],ev['cart']):.3f}%   "
      f"view→purchase {pct(ev['purchase'],ev['view']):.3f}%")
print(f"用户级转化率: view→cart {pct(ev_u['cart'],ev_u['view']):.3f}%   "
      f"cart→purchase {pct(ev_u['purchase'],ev_u['cart']):.3f}%   "
      f"view→purchase {pct(ev_u['purchase'],ev_u['view']):.3f}%")
save(funnel, "behavior_01_转化漏斗.csv")

section("2. 分品类漏斗（TOP5）")
l1df = pd.DataFrame({"view": l1["view"], "cart": l1["cart"], "purchase": l1["purchase"]}).fillna(0).astype(int)
l1df["view→purchase%"] = (100.0 * l1df["purchase"] / l1df["view"]).round(3)
l1df["cart→purchase%"] = (100.0 * l1df["purchase"] / l1df["cart"].replace(0, np.nan)).round(3)
top5 = l1df.sort_values("purchase", ascending=False).head(5)
print(top5.to_string())
save(l1df.sort_values("purchase", ascending=False), "behavior_02_分品类漏斗.csv", index=True)

section("3. 购买路径分析")


def path(r):
    if r.n_pur > 0 and r.n_cart > 0:
        return "浏览→加购→购买"
    if r.n_pur > 0:
        return "浏览后直接购买"
    if r.n_cart > 0:
        return "加购后未购买"
    return "纯浏览"


uf["path"] = uf.apply(path, axis=1)
pc = uf["path"].value_counts()
path_df = pd.DataFrame({"用户数": pc, "占比%": (100.0 * pc / n_users).round(2)})
print(path_df.to_string())
save(path_df, "behavior_03_购买路径.csv", index=True)

section("4. 复购分析")
purchasers = uf[uf["n_pur"] > 0]
n_pur_users = len(purchasers)
rep = int((purchasers["n_pur"] >= 2).sum())
aov_rep = purchasers.loc[purchasers["n_pur"] >= 2, "spend"].sum() / purchasers.loc[purchasers["n_pur"] >= 2, "n_pur"].sum()
aov_first = purchasers.loc[purchasers["n_pur"] == 1, "spend"].sum() / purchasers.loc[purchasers["n_pur"] == 1, "n_pur"].sum()
print(f"购买用户数: {fmt(n_pur_users)}")
print(f"复购用户(>=2次): {fmt(rep)}  复购率: {pct(rep, n_pur_users):.2f}%")
print(f"复购用户客单价: {aov_rep:.2f}   首购用户客单价: {aov_first:.2f}")
rep_dist = purchasers["n_pur"].value_counts().sort_index().head(10)
print("\n用户购买次数分布(前10):")
print(pd.DataFrame({"购买次数": rep_dist.index, "用户数": rep_dist.values}).to_string(index=False))
save(pd.DataFrame({
    "指标": ["购买用户数", "复购用户数", "复购率%", "复购用户客单价", "首购用户客单价"],
    "值": [n_pur_users, rep, round(pct(rep, n_pur_users), 2), round(aov_rep, 2), round(aov_first, 2)],
}), "behavior_04_复购分析.csv")

section("5. RFM 分群")
ref_day = max_pur_day if max_pur_day >= 0 else 60
print(f"参考基准日（数据内最后购买日）: 2019-10-01 + {ref_day} 天")
rfm = purchasers[["user_id", "n_pur", "spend", "last_pur_day"]].copy()
rfm["R"] = ref_day - rfm["last_pur_day"]
rfm = rfm.rename(columns={"n_pur": "F", "spend": "M"})
# 用 rank(method="first") 保证 qcut 分箱唯一
rfm["R_score"] = pd.qcut(rfm["R"].rank(method="first", ascending=False), 5, labels=[5, 4, 3, 2, 1]).astype(int)
rfm["F_score"] = pd.qcut(rfm["F"].rank(method="first"), 5, labels=[1, 2, 3, 4, 5]).astype(int)
rfm["M_score"] = pd.qcut(rfm["M"].rank(method="first"), 5, labels=[1, 2, 3, 4, 5]).astype(int)


def segment(r):
    R, F, M = int(r.R_score), int(r.F_score), int(r.M_score)
    if R >= 4 and F >= 4 and M >= 4:
        return "Champions(忠实高价值)"
    if R >= 4 and F <= 2:
        return "New(新客户)"
    if R <= 2:
        return "At Risk(流失风险)" if F >= 2 else "Lost(已流失)"
    return "Loyal(忠诚)"


rfm["segment"] = rfm.apply(segment, axis=1)
seg_sum = rfm.groupby("segment").agg(
    人数=("user_id", "size"),
    平均购买次数=("F", "mean"),
    平均消费=("M", "mean"),
    总消费额=("M", "sum"),
).reset_index()
seg_sum["占比%"] = (100.0 * seg_sum["人数"] / n_pur_users).round(2)
seg_sum = seg_sum.sort_values("人数", ascending=False)
print(seg_sum.to_string(index=False))
save(seg_sum, "behavior_05_RFM分群.csv")
save(rfm[["user_id", "R", "F", "M", "R_score", "F_score", "M_score", "segment"]], "rfm_purchasers.csv")

section("6. 可视化")

fig, ax = plt.subplots(figsize=(7, 4.5))
stages = ["view(浏览)", "cart(加购)", "purchase(购买)"]
uv = [ev_u["view"], ev_u["cart"], ev_u["purchase"]]
bars = ax.bar(stages, uv, color=[CAT[0], CAT[1], CAT[2]], width=0.6)
ax.set_yscale("log")
for b, x in zip(bars, uv):
    ax.text(b.get_x() + b.get_width() / 2, x, fmt(x), ha="center", va="bottom", fontsize=9, color=INK)
ax.set_title("转化漏斗（用户级，对数轴）")
ax.set_ylabel("用户数（log）")
ax.spines[["top", "right"]].set_visible(False)
savefig(fig, "behavior_转化漏斗.png")

fig, ax = plt.subplots(figsize=(8, 4.5))
p = path_df.sort_values("用户数")
bars = ax.barh(p.index, p["用户数"], color=CAT[0], height=0.6)
for b, pctv in zip(bars, p["占比%"]):
    ax.text(b.get_width(), b.get_y() + b.get_height() / 2, f"  {pctv:.1f}%", va="center", fontsize=9, color=INK)
ax.set_title("用户行为路径分布")
ax.set_xlabel("用户数")
ax.spines[["top", "right"]].set_visible(False)
savefig(fig, "behavior_购买路径.png")

fig, ax = plt.subplots(figsize=(8, 4.5))
s = seg_sum.sort_values("人数")
bars = ax.barh(s["segment"], s["人数"], color=SEQ_BLUE[4], height=0.6)
for b, v, pc_ in zip(bars, s["人数"], s["占比%"]):
    ax.text(b.get_width(), b.get_y() + b.get_height() / 2, f"  {fmt(v)} ({pc_:.1f}%)", va="center", fontsize=9, color=INK)
ax.set_title("RFM 客户分群人数分布")
ax.set_xlabel("人数")
ax.spines[["top", "right"]].set_visible(False)
savefig(fig, "behavior_RFM分群.png")

section("第三节完成")
print("结果已保存至 results/。")
