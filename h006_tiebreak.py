#!/usr/bin/env python3
"""H006 v1 平局裁决（IS 段 2000-2016）：D2 与 D3 在高 IVol 组内方向不一致，查一次。

背景：诊断脚本的结果里，D2 说高 IVol 组内动量腿的 Rank IC 是 +0.0150（正），
但 D3 说同一组内按动量分的五组未来收益均值是递减的（赢家减中段 -0.096%、中段减输家 -0.163%）。
Rank IC 与均值收益一个看秩、一个看均值；20 日收益是偏态厚尾的，均值会被少数极端值拖动，
所以两者可以不一致——但也可能是诊断脚本有 bug。裁决只做三件事，全部只用 IS 段：
  (a) 组内按动量分的五组，各组未来收益的平均秩（与 D2 同一个量：若 D2 是对的，平均秩必递增）。
  (b) 各组未来收益的中位数（不受极端值拖动）。
  (c) 各组未来收益的缩尾均值（每日按 1%/99% 分位截断后再平均）。
高、低两组都算：低组 D2 的 IC 是 -0.0205（负），是第二道一致性检查——
若低组三项也递减，则均值计算本身没问题，分歧只在高组；若低组三项递增，则 D3 的均值路径有问题。

裁决标准（跑之前定好）：
  若 (a) 在高组递增且 (b)/(c) 至少一项在高组递增：D2 得证，D3 的负均值是尾部假象，
  按原定规则（D1 与 D2 通过）考虑 OOS。
  若 (a) 在高组递减：D2 存疑，停下查脚本，不考虑 OOS。

用法（在仓库根目录跑）：python3 h006_tiebreak.py
结果打印到终端，并存一份 JSON 到 results/。本脚本是一次性诊断，不进 git 仓库。
"""

import json
import os
import sys
from datetime import datetime

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools", "backtest"))

import engine
import backtest_is as bi

F_MOM = "delay(close, 21) / delay(close, 147) - 1"          # C19 动量片段
F_GATE = ("gt(rank(delay(ts_mean(ivol20, 252), 21)), 0.667)"
          " - gt(0.333, rank(delay(ts_mean(ivol20, 252), 21)))")

SEG_START, SEG_END = "2000-01-01", "2016-12-31"
H = 20


def _quintile_profiles(mom, gate, label):
    """在高/低两组内，按动量五分位，返回三项：平均标签秩、中位数标签收益、缩尾均值标签收益。"""
    out = {}
    for gname, gval in (("high", 1.0), ("low", -1.0)):
        grp = (gate == gval)
        mom_g = mom.where(grp)
        pct = mom_g.rank(axis=1, pct=True)
        lab = label.where(mom_g.notna())
        lab_rank = lab.rank(axis=1, pct=True)
        q01 = lab.quantile(0.01, axis=1)
        q99 = lab.quantile(0.99, axis=1)
        lab_win = lab.clip(lower=q01, upper=q99, axis=0)
        prof = {"mean_rank": [], "median": [], "winsor_mean": []}
        for qi in range(5):
            lo, hi = qi / 5, (qi + 1) / 5
            if qi == 0:
                m = (pct >= 0) & (pct <= hi)
            else:
                m = (pct > lo) & (pct <= hi)
            prof["mean_rank"].append(float(lab_rank.where(m).mean(axis=1).mean()))
            prof["median"].append(float(lab.where(m).median(axis=1).mean()))
            prof["winsor_mean"].append(float(lab_win.where(m).mean(axis=1).mean()))
        out[gname] = prof
    return out


def _increasing(xs):
    """只看两端：Q5 高于 Q1 即算递增（中间五分位有噪声，不要求严格单调）。"""
    return xs[-1] > xs[0]


def main():
    print("H006 v1 平局裁决（IS 段 2000-2016）：D2（Rank IC）与 D3（均值收益）方向不一致，查一次")
    engine.LOAD_END = "2016-12-31"
    wide = engine.load_wide()
    label = bi._label(wide["close"], H)
    mom = engine.eval_formula(F_MOM, wide)
    gate = engine.eval_formula(F_GATE, wide)
    mom = mom[(mom.index >= SEG_START) & (mom.index <= SEG_END)]
    gate = gate[(gate.index >= SEG_START) & (gate.index <= SEG_END)]

    prof = _quintile_profiles(mom, gate, label)
    for gname in ("high", "low"):
        p = prof[gname]
        print(f"\n[{gname} 组] 按动量五分位 Q1（输家）→ Q5（赢家）")
        print("  平均标签秩   " + " ".join(f"{x:.3f}" for x in p["mean_rank"]))
        print("  中位数收益%  " + " ".join(f"{x * 100:.3f}" for x in p["median"]))
        print("  缩尾均值收益% " + " ".join(f"{x * 100:.3f}" for x in p["winsor_mean"]))

    h = prof["high"]
    a_up = _increasing(h["mean_rank"])
    b_up = _increasing(h["median"])
    c_up = _increasing(h["winsor_mean"])
    print("\n[裁决]")
    print(f"  高组 Q5-Q1：平均标签秩 {h['mean_rank'][-1] - h['mean_rank'][0]:+.3f}；"
          f"中位数 {(h['median'][-1] - h['median'][0]) * 100:+.3f}%；"
          f"缩尾均值 {(h['winsor_mean'][-1] - h['winsor_mean'][0]) * 100:+.3f}%")
    print(f"  高组平均标签秩递增：{'是' if a_up else '否'}；"
          f"中位数递增：{'是' if b_up else '否'}；缩尾均值递增：{'是' if c_up else '否'}")
    if a_up and (b_up or c_up):
        print("  D2 得证：D3 的负均值是尾部假象，高组内动量确实为正；按原定规则考虑 OOS。")
        verdict = "D2_confirmed"
    elif not a_up:
        print("  D2 存疑：平均标签秩也不递增，停下查脚本，不考虑 OOS。")
        verdict = "D2_suspect"
    else:
        print("  未决：平均秩递增但中位数与缩尾均值都不递增，分布形态异常，先不考虑 OOS。")
        verdict = "undecided"

    os.makedirs("results", exist_ok=True)
    now = datetime.now()
    path = f"results/h006_tiebreak_{now:%Y%m%d_%H%M%S}.json"
    record = {"公式_动量腿": F_MOM, "数据段": "is", "统计区间": [SEG_START, SEG_END],
              "生成时间": now.isoformat(timespec="seconds"),
              "profiles": prof, "裁决": verdict}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2, default=float)
    print(f"\n结果已存：{path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
