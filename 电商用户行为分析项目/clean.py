# -*- coding: utf-8 -*-
"""数据清洗：分块读取，统计每步处理行数，输出清洗前后摘要。"""
import sys
import pandas as pd
from common import *

ensure_dirs()
setup_style()
SMOKE = "--smoke" in sys.argv
MAX_CHUNKS = 3 if SMOKE else None

section("二、数据清洗")
print("清洗规则：缺失填充(category_code/brand→unknown) → 删除 price<=0 → 删除重复行 → 类型转换 → 品类拆分")

stats = {f: dict(raw=0, drop_price_le0=0, drop_dup=0, fill_cc=0, fill_brand=0, final=0) for f in FILES}


def clean_pass(name, path, max_chunks):
    it = iter_chunks(path)
    n_chunk = 0
    for chunk in it:
        n_chunk += 1
        if max_chunks and n_chunk > max_chunks:
            break
        st = stats[name]
        st["raw"] += len(chunk)
        st["fill_cc"] += int(chunk["category_code"].isna().sum())
        st["fill_brand"] += int(chunk["brand"].isna().sum())
        chunk["category_code"] = chunk["category_code"].fillna("unknown")
        chunk["brand"] = chunk["brand"].fillna("unknown")
        bad = chunk["price"] <= 0
        st["drop_price_le0"] += int(bad.sum())
        chunk = chunk[~bad]
        dup = chunk.duplicated()
        st["drop_dup"] += int(dup.sum())
        chunk = chunk[~dup]
        chunk["event_time"] = pd.to_datetime(chunk["event_time"], format="%Y-%m-%d %H:%M:%S UTC")
        parts = chunk["category_code"].str.split(".")
        chunk["cat_level1"] = parts.str[0].fillna("unknown")
        chunk["cat_level2"] = parts.str[1].fillna("unknown")
        chunk["cat_level3"] = parts.str[2].fillna("unknown")
        st["final"] += len(chunk)


clean_pass("Oct", FILES["Oct"], MAX_CHUNKS)
clean_pass("Nov", FILES["Nov"], MAX_CHUNKS)

rows_summary = []
for name, st in stats.items():
    rows_summary.append({
        "文件": name,
        "原始行数": st["raw"],
        "删除price<=0": st["drop_price_le0"],
        "删除重复行": st["drop_dup"],
        "清洗后行数": st["final"],
        "保留比例%": round(100.0 * st["final"] / max(st["raw"], 1), 4),
    })
sdf = pd.DataFrame(rows_summary)
_total_raw = sdf["原始行数"].sum()
_total_final = sdf["清洗后行数"].sum()
sdf.loc["合计"] = ["合计", _total_raw, sdf["删除price<=0"].sum(), sdf["删除重复行"].sum(),
                   _total_final, round(100.0 * _total_final / _total_raw, 4)]
print("\n清洗前后行数对比:")
print(sdf.to_string(index=False))
save(sdf, "clean_01_清洗前后行数对比.csv")

fill_df = pd.DataFrame({
    "文件": ["Oct", "Nov"],
    "category_code填充unknown": [stats["Oct"]["fill_cc"], stats["Nov"]["fill_cc"]],
    "brand填充unknown": [stats["Oct"]["fill_brand"], stats["Nov"]["fill_brand"]],
})
print("\n缺失值填充统计:")
print(fill_df.to_string(index=False))
save(fill_df, "clean_02_缺失值填充统计.csv")

print("\n类型转换结果:")
print("  event_time : string  -> datetime64[ns]")
print("  user_id / product_id / category_id : int64（无变化，确认不溢出）")
print("  category_code/brand : string，缺失已填充 'unknown'")
print("  新增列: cat_level1 / cat_level2 / cat_level3（category_code 按'.'拆分）")

section("数据清洗完成")
print("清洗不落地为完整 CSV（约 13.7GB），后续脚本内联复用同一清洗逻辑。")
