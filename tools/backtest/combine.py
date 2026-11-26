"""等权多因子合成：把一组因子各做截面百分位排名后等权平均，得到一条合成信号，再跑成绩单 v2。
用法：
  python tools/backtest/combine.py --segment is --formulas "f1" "f2" "f3"
  python tools/backtest/combine.py --segment is --batch formulas.txt [--hypothesis COMBO --version v1]
不拟合、不学权重：合成只是 rank 平均。评价除了成绩单 v2，还输出
合成对组合内最好单因子的增量（ΔIC、Δ成本后收益）与各成分两两 rank 相关。
合成结果同样登记进 research/registry.jsonl，公式记为 equal_weight_rank_avg(...)。
"""

import argparse
import json
import os
import sys
from datetime import datetime

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import engine
import backtest as bt

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")


def combine_factors(factors):
    """各因子截面百分位排名（0~1）后等权平均；某格全部成分缺失时记缺失。"""
    ranks = [f.rank(axis=1, pct=True) for f in factors]
    stacked = pd.concat(ranks, axis=1, keys=range(len(ranks)))
    combined = stacked.T.groupby(level=1).mean().T
    return combined


def pairwise_rank_corr(factors, labels):
    """成分两两截面 rank 相关（日均 Spearman），返回 {(i, j): rho}。"""
    out = {}
    for i in range(len(factors)):
        for j in range(i + 1, len(factors)):
            rc = bt._ic_series(factors[i], factors[j])
            out[(labels[i], labels[j])] = float(rc.mean()) if len(rc) else None
    return out


def main():
    ap = argparse.ArgumentParser(description="等权多因子合成（rank 平均，不拟合）")
    ap.add_argument("--segment", choices=list(bt.SEGMENTS), default="is")
    ap.add_argument("--formulas", nargs="+", default=None)
    ap.add_argument("--batch", default=None)
    ap.add_argument("--hypothesis", default=None)
    ap.add_argument("--version", default=None)
    ap.add_argument("--notes", default=None)
    ap.add_argument("--cost-bps", type=int, default=bt.COST_BPS)
    ap.add_argument("--no-register", action="store_true")
    args = ap.parse_args()
    if bool(args.formulas) == bool(args.batch):
        print("须且只能给 --formulas 或 --batch 其中一个")
        return 2
    if args.formulas:
        formulas = list(args.formulas)
    else:
        formulas = []
        for run in bt.parse_batch(args.batch):
            formulas.append(run["formula"])
    if len(formulas) < 2:
        print("合成至少需要 2 条公式")
        return 2
    for f in formulas:
        ok, bad = engine.check_whitelist(f)
        if not ok:
            print(f"公式错误：{'、'.join(bad)} 不在清单内：{f}")
            return 1
    load_end, seg_start, seg_end, seg_name = bt.SEGMENTS[args.segment]
    engine.LOAD_END = load_end
    try:
        wide = engine.load_wide()
    except Exception as e:
        print(f"数据加载失败：{e}")
        return 1
    factors = []
    try:
        for f in formulas:
            fac = engine.eval_formula(f, wide)
            factors.append(fac[(fac.index >= seg_start) & (fac.index <= seg_end)])
    except Exception as e:
        print(f"计算失败：{e}")
        return 1
    combined = combine_factors(factors)
    card = bt.scorecard(combined, wide, cost_bps=args.cost_bps)
    singles = [bt.quick_stats(f, wide, cost_bps=args.cost_bps) for f in factors]
    best_i = max(range(len(singles)),
                 key=lambda i: (singles[i]["IC均值"] is not None, singles[i]["IC均值"] or -9e9))
    best = singles[best_i]
    d_ic = (card["IC均值"] - best["IC均值"]
            if card["IC均值"] is not None and best["IC均值"] is not None else None)
    d_ca = (card["成本后多空收益"] - best["成本后多空收益"]
            if card["成本后多空收益"] is not None and best["成本后多空收益"] is not None else None)
    labels = [f"F{i + 1}" for i in range(len(formulas))]
    pair_corr = pairwise_rank_corr(factors, labels)
    combo_formula = "equal_weight_rank_avg(" + "; ".join(formulas) + ")"
    print(bt.scorecard_text(card))
    print(f"成分单因子 IC：" + "、".join(
        f"{labels[i]} {round(s['IC均值'], 4) if s['IC均值'] is not None else None}" for i, s in enumerate(singles)))
    print(f"最好单因子：{labels[best_i]}（IC {round(best['IC均值'], 4) if best['IC均值'] is not None else None}）"
          f"，合成 ΔIC {round(d_ic, 4) if d_ic is not None else None}"
          f"，Δ成本后收益% {round(d_ca * 100, 2) if d_ca is not None else None}")
    for (a, b), rho in pair_corr.items():
        print(f"成分 rank 相关 {a}-{b}：{round(rho, 3) if rho is not None else None}")
    pct = bt.percentile_of(card["IC均值"], bt.load_null())
    if pct is None:
        print("全库百分位：未生成（先跑 tools/backtest/run_null.py 生成 benchmarks/is_null.json）")
    else:
        print(f"全库百分位：{pct['percentile']}%（共 {pct['n']} 条可跑经典因子）")
    os.makedirs("results", exist_ok=True)
    now = datetime.now()
    path = f"results/{args.segment}_combo_{now:%Y%m%d_%H%M%S}_{now.microsecond // 1000:03d}.json"
    record = {"公式": combo_formula, "成分": formulas, "数据段": args.segment,
              "统计区间": [seg_start, seg_end], "生成时间": now.isoformat(timespec="seconds"),
              "成本bps": args.cost_bps, "成绩单": card,
              "最好单因子": {"label": labels[best_i], "公式": formulas[best_i], **best},
              "dIC_vs_best": d_ic, "d成本后多空收益_vs_best": d_ca,
              "成分rank相关": {f"{a}-{b}": v for (a, b), v in pair_corr.items()},
              "全库百分位": pct}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2, default=float)
    print(f"成绩单已存：{path}")
    if not args.no_register:
        reg = {
            "hypothesis_id": args.hypothesis,
            "version": args.version,
            "formula": combo_formula,
            "formula_hash": bt.formula_hash(combo_formula),
            "segment": args.segment,
            "scorecard_v2": card,
            "baselines": None,
            "percentile": pct,
            "cost_bps": args.cost_bps,
            "data_version": bt.data_version(wide),
            "created_at": now.isoformat(timespec="seconds"),
            "created_by": bt._created_by(),
            "direction": "",
            "holding_period": "20日",
            "params": "",
            "oos_rule": "",
            "is_end": bt.SEGMENTS["is"][2],
            "status": {"is": "IS 已验证", "oos": "OOS 已验证", "holdout": "holdout 已跑"}[args.segment],
            "notes": (args.notes or "") + f"；等权合成 {len(formulas)} 条成分",
        }
        added, _ = bt.append_registry(reg)
        print("登记：已追加 research/registry.jsonl" if added else "登记：同一公式 + 同一段已登记过，本次不重复记")
        try:
            import render_registry
            render_registry.render()
            print("登记视图：research/experiment_registry.md 已重新生成")
        except Exception as e:
            print(f"登记视图生成失败（登记本身已写）：{e}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
