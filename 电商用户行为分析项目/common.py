# -*- coding: utf-8 -*-
"""公共工具：路径、dtype、输出、绘图样式、分块读取。"""
import os
import sys

# 修复 Windows 控制台中文乱码
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

DATA_DIR = "F:/kaggle-data"
RESULT_DIR = os.path.join(DATA_DIR, "results")
PLOT_DIR = os.path.join(RESULT_DIR, "plots")
FILES = {
    "Oct": os.path.join(DATA_DIR, "2019-Oct.csv"),
    "Nov": os.path.join(DATA_DIR, "2019-Nov.csv"),
}
CHUNKSIZE = 1_000_000

# 固定 dtype：避免推断开销；category_id 约 2.1e18 仍在 int64 范围
DTYPE = {
    "event_time": "string",
    "event_type": "category",
    "product_id": "int64",
    "category_id": "int64",
    "category_code": "string",
    "brand": "string",
    "price": "float64",
    "user_id": "int64",
    "user_session": "string",
}

CAT = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
EVENT_COLORS = {"view": "#2a78d6", "cart": "#eb6834", "purchase": "#1baf7a"}
SEQ_BLUE = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#2a78d6", "#256abf", "#184f95", "#0d366b"]
INK = "#0b0b0b"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
SURFACE = "#fcfcfb"


def ensure_dirs():
    os.makedirs(RESULT_DIR, exist_ok=True)
    os.makedirs(PLOT_DIR, exist_ok=True)


def setup_style():
    plt.rcParams.update({
        "font.sans-serif": ["Microsoft YaHei", "SimHei", "DejaVu Sans"],
        "axes.unicode_minus": False,
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "axes.edgecolor": AXIS,
        "axes.labelcolor": INK,
        "text.color": INK,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "axes.grid": True,
        "grid.color": GRID,
        "grid.linewidth": 0.6,
        "axes.axisbelow": True,
        "figure.dpi": 110,
        "savefig.dpi": 130,
        "savefig.bbox": "tight",
    })


def section(title):
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def save(df, name, index=False):
    p = os.path.join(RESULT_DIR, name)
    df.to_csv(p, index=index, encoding="utf-8-sig")
    print(f"  [saved] results/{name}")
    return p


def savefig(fig, name):
    p = os.path.join(PLOT_DIR, name)
    fig.savefig(p)
    plt.close(fig)
    print(f"  [saved fig] results/plots/{name}")
    return p


def iter_chunks(path, chunksize=CHUNKSIZE):
    return pd.read_csv(path, chunksize=chunksize, dtype=DTYPE)


def fmt(x):
    return f"{x:,}"


def pct(a, b):
    return 0.0 if b == 0 else 100.0 * a / b


def welford_finalize(n, s, ss):
    """由 sum/sumsq 计算均值与样本标准差(ddof=1)。"""
    if n == 0:
        return float("nan"), float("nan")
    mean = s / n
    var = (ss - n * mean * mean) / (n - 1) if n > 1 else 0.0
    return mean, float(np.sqrt(max(var, 0.0)))


REF_DAY = pd.Timestamp("2019-10-01")


def clean_chunk(chunk, parse_time=True):
    """对单个分块做清洗：缺失填充 → 去 price<=0 → 去重 → 类型转换 → 品类拆分。"""
    chunk = chunk.copy()
    chunk["category_code"] = chunk["category_code"].fillna("unknown")
    chunk["brand"] = chunk["brand"].fillna("unknown")
    chunk = chunk[chunk["price"] > 0]
    chunk = chunk.drop_duplicates()
    if parse_time:
        chunk["event_time"] = pd.to_datetime(chunk["event_time"], format="%Y-%m-%d %H:%M:%S UTC")
    chunk["user_id"] = chunk["user_id"].astype("int64")
    chunk["product_id"] = chunk["product_id"].astype("int64")
    chunk["category_id"] = chunk["category_id"].astype("int64")
    parts = chunk["category_code"].str.split(".")
    chunk["cat_level1"] = parts.str[0].fillna("unknown")
    chunk["cat_level2"] = parts.str[1].fillna("unknown")
    chunk["cat_level3"] = parts.str[2].fillna("unknown")
    return chunk


def day_index(dt):
    """事件时间 -> 天序号（2019-10-01=0）。"""
    return (dt - REF_DAY).dt.days.astype("int64")


class UserAgg:
    """按 user_id 的流式聚合，内存 O(唯一用户数)。

    归约方式：sum / min(哨兵999) / max(哨兵-1) / or(按位或)。
    """

    COLS = [
        ("n_view", np.int64, "sum", 0),
        ("n_cart", np.int64, "sum", 0),
        ("n_pur", np.int64, "sum", 0),
        ("spend", np.float64, "sum", 0.0),
        ("first_pur_day", np.int64, "min", 999),
        ("last_pur_day", np.int64, "max", -1),
        ("days_mask", np.int64, "or", 0),
        ("sum_dur", np.float64, "sum", 0.0),
        ("n_sess", np.int64, "sum", 0),
    ]

    def __init__(self):
        self.map = {}  # user_id -> 行号
        self.n = 0
        self.cap = 0
        self.arrays = {c[0]: np.zeros(0, dtype=c[1]) for c in self.COLS}

    def _ensure(self, need):
        if need <= self.cap:
            return
        newcap = int(max(need, self.cap * 2, 1_000_000))
        for name, dt, _mode, init in self.COLS:
            a = self.arrays[name]
            na = np.empty(newcap, dtype=dt)
            na[:len(a)] = a
            if init != 0:
                na[len(a):] = init
            self.arrays[name] = na
        self.cap = newcap

    def add(self, user_ids, values):
        """user_ids: int64 数组；values: {列名: 同长数组}，仅更新出现的列。"""
        ids = np.asarray(user_ids, dtype=np.int64)
        uniq, inv = np.unique(ids, return_inverse=True)
        idx = np.empty(len(uniq), dtype=np.int64)
        new_count = 0
        for i, u in enumerate(uniq):
            j = self.map.get(u)
            if j is None:
                j = self.n + new_count
                self.map[u] = j
                new_count += 1
            idx[i] = j
        if new_count:
            self._ensure(self.n + new_count)
            self.n += new_count
        rowidx = idx[inv]
        for name, dt, mode, init in self.COLS:
            if name not in values:
                continue
            v = np.asarray(values[name])
            arr = self.arrays[name]
            if mode == "sum":
                np.add.at(arr, rowidx, v)
            elif mode == "min":
                np.minimum.at(arr, rowidx, v)
            elif mode == "max":
                np.maximum.at(arr, rowidx, v)
            elif mode == "or":
                np.bitwise_or.at(arr, rowidx, v.astype(np.int64))

    def to_frame(self):
        d = {"user_id": np.fromiter(self.map.keys(), dtype=np.int64, count=self.n)}
        for name, _dt, _mode, _init in self.COLS:
            d[name] = self.arrays[name][:self.n]
        return pd.DataFrame(d)
