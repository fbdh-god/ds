# -*- coding: utf-8 -*-
"""探索性数据分析（EDA）：单趟分块读取，累积各项指标。"""
import sys
import time
import numpy as np
import pandas as pd
from collections import Counter
from common import *

ensure_dirs()
setup_style()

SMOKE = "--smoke" in sys.argv
MAX_CHUNKS = 3 if SMOKE else None
# 系统抽样间隔：目标每文件约 100 万行样本（Oct≈4245 万 → 42；Nov≈6700 万 → 67）
K = {"Oct": 42, "Nov": 67}

section("一、探索性数据分析 (EDA)")
print(f"分块读取 chunksize={fmt(CHUNKSIZE)}" + ("  [SMOKE 模式: 每文件前3块]" if SMOKE else ""))

rows = {}
etype = {}
missing = {}
sample_list = {}
price_stat = {}
for et in ["view", "cart", "purchase", "all"]:
    price_stat[et] = dict(n=0, sum=0.0, sumsq=0.0, min=float("inf"), max=-float("inf"), zero=0, neg=0)
t_min = None
t_max = None
daily = {"Oct": Counter(), "Nov": Counter()}
hourly = Counter()
user_events = {"Oct": Counter(), "Nov": Counter(), "All": Counter()}
user_pur = Counter()
prod_set = set()
cat_set = set()
brand_set = set()
prod_pur = Counter()
cat_pur = Counter()
brand_pur = Counter()
cat_map = {}
l1 = {"view": Counter(), "cart": Counter(), "purchase": Counter()}
sess_samples = []
SESS_FRAC = 0.10
dup_rows = 0


def process_file(name, path, k, max_chunks):
    global t_min, t_max, dup_rows
    it = iter_chunks(path)
    n_chunk = 0
    for chunk in it:
        n_chunk += 1
        if max_chunks and n_chunk > max_chunks:
            break
        t0 = time.time()
        n = len(chunk)
        rows[name] = rows.get(name, 0) + n
        vc = chunk["event_type"].value_counts()
        for et, c in vc.items():
            etype.setdefault(name, Counter())[et] += c
            etype.setdefault("All", Counter())[et] += c
        miss = chunk.isna().sum()
        for col in DTYPE:
            missing.setdefault(name, Counter())[col] += int(miss.get(col, 0))
        positions = np.arange(n) + (rows[name] - n)
        take = np.flatnonzero(positions % k == 0)
        if take.size:
            sample_list.setdefault(name, []).append(chunk.iloc[take])
        dt = pd.to_datetime(chunk["event_time"], format="%Y-%m-%d %H:%M:%S UTC")
        if t_min is None or dt.min() < t_min:
            t_min = dt.min()
        if t_max is None or dt.max() > t_max:
            t_max = dt.max()
        p = chunk["price"]
        for et in ["view", "cart", "purchase"]:
            sub = p[chunk["event_type"] == et]
            if len(sub):
                st = price_stat[et]
                st["n"] += len(sub)
                st["sum"] += sub.sum()
                st["sumsq"] += (sub * sub).sum()
                st["min"] = min(st["min"], sub.min())
                st["max"] = max(st["max"], sub.max())
                st["zero"] += int((sub == 0).sum())
                st["neg"] += int((sub < 0).sum())
        st = price_stat["all"]
        st["n"] += n
        st["sum"] += p.sum()
        st["sumsq"] += (p * p).sum()
        st["min"] = min(st["min"], p.min())
        st["max"] = max(st["max"], p.max())
        st["zero"] += int((p == 0).sum())
        st["neg"] += int((p < 0).sum())
        pur = chunk["event_type"] == "purchase"
        if pur.any():
            dp = dt[pur]
            daily[name].update(dp.dt.strftime("%Y-%m-%d").value_counts().to_dict())
            hourly.update(dp.dt.hour.value_counts().to_dict())
            puro = chunk.loc[pur]
            user_pur.update(puro["user_id"].value_counts().to_dict())
            prod_pur.update(puro["product_id"].value_counts().to_dict())
            cat_pur.update(puro["category_id"].value_counts().to_dict())
            brand_pur.update(puro["brand"].value_counts().to_dict())
        user_events[name].update(chunk["user_id"].value_counts().to_dict())
        user_events["All"].update(chunk["user_id"].value_counts().to_dict())
        prod_set.update(chunk["product_id"].tolist())
        cat_set.update(chunk["category_id"].tolist())
        brand_set.update(chunk["brand"].dropna().tolist())
        cc = chunk[chunk["category_code"].notna()][["category_id", "category_code"]].drop_duplicates("category_id")
        cat_map.update(dict(zip(cc["category_id"], cc["category_code"])))
        codes = chunk["category_code"].fillna("").str.split(".").str[0]
        codes = codes.mask(codes == "", "unknown")
        for et in ["view", "cart", "purchase"]:
            l1[et].update(codes[chunk["event_type"] == et].value_counts().to_dict())
        tmp = pd.DataFrame({
            "session": chunk["user_session"],
            "n": 1,
            "is_cart": (chunk["event_type"] == "cart").astype("int8"),
            "is_pur": (chunk["event_type"] == "purchase").astype("int8"),
            "t_min": dt, "t_max": dt,
        })
        sess = tmp.groupby("session").agg(
            n=("n", "size"), n_cart=("is_cart", "sum"), n_pur=("is_pur", "sum"),
            t_min=("t_min", "min"), t_max=("t_max", "max"))
        sess_samples.append(sess.sample(frac=SESS_FRAC, random_state=42))
        dup_rows += int(chunk.duplicated().sum())
        if n_chunk % 5 == 0:
            print(f"  [{name}] chunk {n_chunk}  累计 {fmt(rows[name])} 行  ({time.time()-t0:.1f}s/块)")


process_file("Oct", FILES["Oct"], K["Oct"], MAX_CHUNKS)
process_file("Nov", FILES["Nov"], K["Nov"], MAX_CHUNKS)

section("1. 数据规模")
total = sum(rows.values())
print(f"10月(Oct)总行数: {fmt(rows.get('Oct',0))}")
print(f"11月(Nov)总行数: {fmt(rows.get('Nov',0))}")
print(f"两月合计行数: {fmt(total)}")
et_df = pd.DataFrame(etype).fillna(0).astype(int).T
et_df["合计"] = et_df.sum(axis=1)
et_df = et_df[["view", "cart", "purchase", "合计"]]
print(et_df.to_string())
save(et_df, "eda_01_event_type分布.csv", index=True)

section("2. 缺失值检查")
for name in ["Oct", "Nov"]:
    sdf = pd.concat(sample_list[name], ignore_index=True)
    miss_sample = sdf.isna().sum()
    rate = (100.0 * miss_sample / len(sdf)).round(3)
    mdf = pd.DataFrame({"缺失数": miss_sample, "缺失率%": rate})
    mdf.loc["__样本行数__"] = [len(sdf), np.nan]
    print(f"\n[{name}] 抽样 {fmt(len(sdf))} 行的缺失情况:")
    print(mdf.to_string())
    save(mdf, f"eda_02a_缺失值_抽样_{name}.csv", index=True)
for name in ["Oct", "Nov"]:
    tot_r = rows[name]
    mdf = pd.DataFrame({
        "缺失数": {c: missing[name].get(c, 0) for c in DTYPE},
        "缺失率%": {c: round(100.0 * missing[name].get(c, 0) / tot_r, 3) for c in DTYPE},
    })
    print(f"\n[{name}] 全量精确缺失（{fmt(tot_r)} 行）:")
    print(mdf.to_string())
    save(mdf, f"eda_02b_缺失值_全量_{name}.csv", index=True)

section("3. price 字段探查")


def price_row(st):
    mean, std = welford_finalize(st["n"], st["sum"], st["sumsq"])
    return [st["n"], st["min"], st["max"], mean, std, st["zero"], st["neg"]]


price_df = pd.DataFrame(
    {et: price_row(price_stat[et]) for et in ["all", "view", "cart", "purchase"]},
    index=["count", "min", "max", "mean", "std(ddof=1)", "0值数", "负值数"]).T
print(price_df.to_string(float_format=lambda x: f"{x:,.4f}"))
save(price_df, "eda_03_price描述统计.csv", index=True)
oct_sample = pd.concat(sample_list["Oct"], ignore_index=True)
nov_sample = pd.concat(sample_list["Nov"], ignore_index=True)
all_sample = pd.concat([oct_sample, nov_sample], ignore_index=True)
qdf = all_sample.groupby("event_type")["price"].quantile([0.25, 0.5, 0.75, 0.9, 0.99]).unstack()
qdf.columns = ["p25", "p50(中位数)", "p75", "p90", "p99"]
qdf.loc["all"] = all_sample["price"].quantile([0.25, 0.5, 0.75, 0.9, 0.99]).values
print(f"\nprice 分位数（基于抽样 {fmt(len(all_sample))} 行）:")
print(qdf.round(2).to_string())
save(qdf, "eda_03b_price分位数.csv", index=True)

section("4. event_type 与整体转化率")
tot = etype["All"]
v = tot.get("view", 0)
c = tot.get("cart", 0)
p_ = tot.get("purchase", 0)
print(f"view={fmt(v)} ({pct(v,total):.2f}%)   cart={fmt(c)} ({pct(c,total):.2f}%)   purchase={fmt(p_,)} ({pct(p_,total):.2f}%)")
conv = pd.DataFrame({
    "指标": ["view→cart", "cart→purchase", "view→purchase"],
    "分子": [c, p_, p_], "分母": [v, c, v],
    "转化率%": [round(pct(c, v), 4), round(pct(p_, c), 4), round(pct(p_, v), 4)],
})
print(conv.to_string(index=False))
save(conv, "eda_04_整体转化率.csv")

section("5. 时间分析")
print(f"event_time 范围: {t_min}  ~  {t_max}")
daily_df = pd.DataFrame({"Oct购买": daily["Oct"], "Nov购买": daily["Nov"]}).fillna(0).astype(int).sort_index()
daily_df["合计"] = daily_df.sum(axis=1)
print(f"\n按天购买量（共 {len(daily_df)} 天）:")
print(daily_df.to_string())
save(daily_df, "eda_05a_每日购买量.csv", index=True)
peak = daily_df["Nov购买"].max()
peak_day = daily_df["Nov购买"].idxmax()
print(f"\n11月购买峰值: {peak_day} 当日 {fmt(int(peak))} 次购买"
      + ("  ← 双11" if peak_day == "2019-11-11" else ""))
hour_df = pd.DataFrame({"hour": range(24), "购买量": [hourly.get(h, 0) for h in range(24)]})
print("\n按小时购买量（两月合计）:")
print(hour_df.to_string(index=False))
save(hour_df, "eda_05b_按小时购买量.csv")
print(f"购买最多时段: {hour_df.loc[hour_df['购买量'].idxmax(),'hour']}:00")

section("6. 用户分析")
u_oct = len(user_events["Oct"])
u_nov = len(user_events["Nov"])
u_all = len(user_events["All"])
print(f"10月独立用户: {fmt(u_oct)}   11月独立用户: {fmt(u_nov)}   两月独立用户: {fmt(u_all)}")
ev_arr = np.array(list(user_events["All"].values()), dtype=np.int64)
q = np.percentile(ev_arr, [50, 75, 90, 99])
udf = pd.DataFrame({"用户事件次数分位数": ["50%", "75%", "90%", "99%"], "值": q.astype(int)})
print("\n每用户行为次数分布（两月）:")
print(udf.to_string(index=False))
save(udf, "eda_06a_用户事件次数分位数.csv")
pusers = len(user_pur)
repur = sum(1 for x in user_pur.values() if x >= 2)
print(f"\n购买用户: {fmt(pusers)} ({pct(pusers,u_all):.2f}%)   "
      f"仅浏览用户: {fmt(u_all-pusers)} ({pct(u_all-pusers,u_all):.2f}%)")
print(f"复购用户(购买>=2次): {fmt(repur)}  复购率(占购买用户): {pct(repur,pusers):.2f}%")
save(pd.DataFrame({"指标": ["独立用户", "购买用户", "仅浏览用户", "复购用户", "复购率%"],
                   "值": [u_all, pusers, u_all - pusers, repur, round(pct(repur, pusers), 2)]}),
     "eda_06b_用户构成.csv")

section("7. 商品分析")
print(f"独立商品数: {fmt(len(prod_set))}   独立品类数: {fmt(len(cat_set))}   独立品牌数: {fmt(len(brand_set))}")
top_prod = pd.DataFrame(prod_pur.most_common(10), columns=["product_id", "购买次数"])
top_cat = pd.DataFrame(cat_pur.most_common(10), columns=["category_id", "购买次数"])
top_cat["category_code"] = top_cat["category_id"].map(cat_map)
top_brand = pd.DataFrame(brand_pur.most_common(10), columns=["brand", "购买次数"])
print("\n购买次数 TOP10 商品:"); print(top_prod.to_string(index=False)); save(top_prod, "eda_07a_TOP10商品.csv")
print("\n购买次数 TOP10 品类:"); print(top_cat.to_string(index=False)); save(top_cat, "eda_07b_TOP10品类.csv")
print("\n购买次数 TOP10 品牌:"); print(top_brand.to_string(index=False)); save(top_brand, "eda_07c_TOP10品牌.csv")
l1df = pd.DataFrame({"view": l1["view"], "cart": l1["cart"], "purchase": l1["purchase"]}).fillna(0).astype(int)
l1df["转化率view→purchase%"] = (100.0 * l1df["purchase"] / l1df["view"]).round(3)
l1df = l1df.sort_values("purchase", ascending=False)
print("\n各一级品类浏览/加购/购买/转化率:")
print(l1df.to_string())
save(l1df, "eda_07d_一级品类分析.csv", index=True)

section("8. 会话分析（基于会话抽样）")
sess_all = pd.concat(sess_samples, ignore_index=True)
print(f"抽样会话数: {fmt(len(sess_all))}")
sq = np.percentile(sess_all["n"], [50, 75, 90, 99])
sdf = pd.DataFrame({"每会话事件数分位数": ["50%", "75%", "90%", "99%"], "值": sq.astype(int)})
print("\n每个 user_session 的事件数分位数:")
print(sdf.to_string(index=False))
save(sdf, "eda_08a_会话事件数分位数.csv")


def path(r):
    if r.n_pur > 0 and r.n_cart > 0:
        return "浏览+加购+购买"
    if r.n_pur > 0:
        return "浏览+直接购买"
    if r.n_cart > 0:
        return "浏览+加购(未购买)"
    return "纯浏览"


sess_all["path"] = sess_all.apply(path, axis=1)
pc = sess_all["path"].value_counts()
pdf = pd.DataFrame({"会话数": pc, "占比%": (100.0 * pc / len(sess_all)).round(2)})
print("\n会话行为路径分布:")
print(pdf.to_string())
save(pdf, "eda_08b_会话路径分布.csv")
dur_min = (sess_all["t_max"] - sess_all["t_min"]).dt.total_seconds() / 60.0
dur_min = dur_min.clip(lower=0)
ddf = pd.DataFrame({"会话时长(分钟)分位数": ["50%", "75%", "90%", "99%", "max"],
                    "值": [round(np.percentile(dur_min, [50, 75, 90, 99])[i], 2) for i in range(4)] + [round(dur_min.max(), 2)]})
print("\n会话时长分布(分钟):")
print(ddf.to_string(index=False))
save(ddf, "eda_08c_会话时长分位数.csv")

section("9. 数据质量汇总")
qual = pd.DataFrame({
    "检查项": ["重复行(块内)", "user_id 为空", "price 为0", "price 为负",
               "category_code 缺失", "brand 缺失"],
    "数量": [dup_rows, missing["All"].get("user_id", 0) if "All" in missing else sum(missing[n]["user_id"] for n in ["Oct", "Nov"]),
             price_stat["all"]["zero"], price_stat["all"]["neg"],
             sum(missing[n]["category_code"] for n in ["Oct", "Nov"]),
             sum(missing[n]["brand"] for n in ["Oct", "Nov"])],
})
qual["占比%"] = (100.0 * qual["数量"] / total).round(4)
print(qual.to_string(index=False))
save(qual, "eda_09_数据质量汇总.csv")

section("10. 可视化")

fig, ax = plt.subplots(figsize=(7, 4.5))
types = ["view", "cart", "purchase"]
cnt = [etype["All"].get(t, 0) for t in types]
colors = [EVENT_COLORS[t] for t in types]
bars = ax.bar(types, cnt, color=colors, width=0.6)
ax.set_yscale("log")
ax.set_title("事件类型分布（两月合计，对数轴）")
ax.set_ylabel("事件数（log）")
for b, c in zip(bars, cnt):
    ax.text(b.get_x() + b.get_width() / 2, c, f"{fmt(c)}\n({pct(c, total):.2f}%)",
            ha="center", va="bottom", fontsize=9, color=INK)
ax.spines[["top", "right"]].set_visible(False)
savefig(fig, "eda_事件类型分布.png")

fig, ax = plt.subplots(figsize=(11, 4.8))
x = pd.to_datetime(daily_df.index)
ax.plot(x, daily_df["Oct购买"], color=CAT[0], lw=2, label="10月")
ax.plot(x, daily_df["Nov购买"], color=CAT[1], lw=2, label="11月")
if "2019-11-11" in daily_df.index:
    pk = pd.Timestamp("2019-11-11")
    ax.scatter([pk], [daily_df.loc["2019-11-11", "Nov购买"]], color=CAT[2], zorder=5, s=40)
    ax.annotate("双11峰值\n" + fmt(int(daily_df.loc["2019-11-11", "Nov购买"])),
                xy=(pk, daily_df.loc["2019-11-11", "Nov购买"]), xytext=(pk, daily_df.loc["2019-11-11", "Nov购买"] * 1.15),
                ha="center", fontsize=9, color=INK,
                arrowprops=dict(arrowstyle="->", color=MUTED))
ax.set_title("每日购买量趋势（10月 vs 11月）")
ax.set_ylabel("购买次数")
ax.legend()
ax.spines[["top", "right"]].set_visible(False)
savefig(fig, "eda_每日购买量.png")

fig, ax = plt.subplots(figsize=(9, 4.5))
ax.bar(hour_df["hour"].astype(str), hour_df["购买量"], color=SEQ_BLUE[4], width=0.7)
ax.set_title("按小时购买量分布（两月合计）")
ax.set_xlabel("小时（0-23）")
ax.set_ylabel("购买次数")
ax.spines[["top", "right"]].set_visible(False)
savefig(fig, "eda_按小时购买量.png")

fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
ax = axes[0]
ax.hist(all_sample["price"], bins=60, color=SEQ_BLUE[4], alpha=0.9)
ax.set_yscale("log")
ax.set_title("price 分布（对数轴）")
ax.set_xlabel("price")
ax.set_ylabel("样本数（log）")
ax.spines[["top", "right"]].set_visible(False)
ax = axes[1]
all_sample.boxplot(column="price", by="event_type", ax=ax, patch_artist=True,
                   showfliers=False, grid=False)
ax.set_yscale("log")
for patch, t in zip(ax.patches, types):
    patch.set_facecolor(EVENT_COLORS[t])
ax.set_title("price 按事件类型（对数轴，去离群点）")
ax.set_xlabel("event_type")
ax.set_ylabel("price（log）")
ax.spines[["top", "right"]].set_visible(False)
plt.suptitle("")
fig.tight_layout()
savefig(fig, "eda_price分布.png")

fig, ax = plt.subplots(figsize=(8, 4.5))
clipped = ev_arr[(ev_arr >= 1) & (ev_arr <= 50)]
ax.hist(clipped, bins=49, color=CAT[0], alpha=0.9)
ax.set_yscale("log")
ax.set_title(f"每用户事件次数分布（截取1-50次，占用户{100*len(clipped)/len(ev_arr):.1f}%）")
ax.set_xlabel("事件次数")
ax.set_ylabel("用户数（log）")
ax.spines[["top", "right"]].set_visible(False)
savefig(fig, "eda_用户事件次数分布.png")

fig, ax = plt.subplots(figsize=(8, 5))
top_l1 = l1df.head(12).iloc[::-1]
bars = ax.barh(top_l1.index, top_l1["purchase"], color=CAT[0], height=0.6)
for b, cv, pur in zip(bars, top_l1["转化率view→purchase%"], top_l1["purchase"]):
    ax.text(b.get_width(), b.get_y() + b.get_height() / 2,
            f"  {fmt(int(pur))}  (转化{cv:.2f}%)", va="center", fontsize=8, color=INK)
ax.set_title("各一级品类购买量 TOP12")
ax.set_xlabel("购买次数")
ax.spines[["top", "right"]].set_visible(False)
savefig(fig, "eda_一级品类购买量.png")

fig, ax = plt.subplots(figsize=(8, 4.5))
dd = dur_min[(dur_min <= 60)]
ax.hist(dd, bins=60, color=CAT[2], alpha=0.9)
ax.set_yscale("log")
ax.set_title(f"会话时长分布（0-60分钟，占会话{100*len(dd)/len(dur_min):.1f}%）")
ax.set_xlabel("会话时长（分钟）")
ax.set_ylabel("会话数（log）")
ax.spines[["top", "right"]].set_visible(False)
savefig(fig, "eda_会话时长分布.png")

section("EDA 完成")
print("中间结果 CSV 已保存至 results/，图表已保存至 results/plots/。")
