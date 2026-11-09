# measure_classics.py — 经典因子统一测算（一次性脚本，不属于主循环）
# 用途：在与主循环完全相同的口径下测算 17 条经典因子，
#       得到参照数字与两两相关，防生成因子与经典因子无声重复。
# 口径：判定期限 20 日、训练段、成分口径、双门槛（Rank IC ≥ 0.02 且 ICIR ≥ 0.2），与 run.py 一致。
# 产物：classic_results.jsonl（逐条指标组）、data/classic_values.parquet（因子值表）、classic_corr.csv（两两日截面 Spearman 相关，
#       每 20 个交易日抽一日计算后取全期平均）。
# 运行：python measure_classics.py

import json

import numpy as np
import pandas as pd

import calc

H = 20
THRESHOLD = 0.02
ICIR_THRESHOLD = 0.2

# ============================================================
# 块一：逐条测算
# ============================================================
wide = calc.load_wide()
formulas = calc.CLASSIC_FORMULAS
values = {}
with open("classic_results.jsonl", "w", encoding="utf-8") as fh:
    for i, f in enumerate(formulas, 1):
        cid = f"C{i:02d}"
        vals = calc.eval_formula(f, wide)
        values[cid] = vals
        metrics = calc.compute_metrics(vals, wide, H)
        passed = calc.judge(metrics["IC均值"], THRESHOLD, metrics["ICIR"], ICIR_THRESHOLD)
        fh.write(json.dumps({"编号": cid, "公式": f, "判定数字": metrics,
                             "结论": "通过" if passed else "不通过"}, ensure_ascii=False) + "\n")
        print(f"{cid} RankIC {metrics['IC均值']:.4f} ICIR {metrics['ICIR']:.3f} "
              f"{'通过' if passed else '不通过'}", flush=True)

# ============================================================
# 块二：因子值存成一张表，供主循环相关性判定读取，不必重算
# ============================================================
calc.save_classics([values[f"C{i:02d}"] for i in range(1, len(formulas) + 1)])
print("因子值已存表：data/classic_values.parquet")

# ============================================================
# 块三：两两相关（月频抽样日截面 Spearman 取平均）
# ============================================================
ids = list(values)
daily_corrs = []
for d in range(0, len(wide["close"]), 20):
    day = pd.DataFrame({cid: values[cid].iloc[d] for cid in ids})
    if day.notna().sum().min() >= 30:
        daily_corrs.append(day.corr(method="spearman").values)
corr = pd.DataFrame(np.nanmean(np.stack(daily_corrs), axis=0), index=ids, columns=ids)
corr.to_csv("classic_corr.csv")
print("\n|相关| ≥ 0.5 的配对：")
found = False
for i, a in enumerate(ids):
    for b in ids[i + 1:]:
        if abs(corr.loc[a, b]) >= 0.5:
            print(f"  {a} ~ {b}: {corr.loc[a, b]:.2f}")
            found = True
if not found:
    print("  无")
print("完成：classic_results.jsonl / classic_corr.csv")
