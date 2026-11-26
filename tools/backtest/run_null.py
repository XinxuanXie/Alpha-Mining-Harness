"""零分布批量跑：一次加载宽表，对 classic_library/formulas.json 里白名单通过的条目逐条试算，
输出 benchmarks/is_null.json（每条 20 日 IC/ICIR、分布分位数、可跑条数、试算失败清单）。
用法：python tools/backtest/run_null.py [--segment is] [--out benchmarks/is_null.json]
只跑 IS 段（零分布是 IS 口径的参照系）；试算失败的条目不硬凑，记进 excluded 栏。
"""

import argparse
import json
import os
import sys
from datetime import datetime

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import engine
import backtest as bt

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
FORMULAS_JSON = os.path.join(ROOT, "classic_library", "formulas.json")


def main():
    ap = argparse.ArgumentParser(description="零分布批量跑：全库白名单通过条目逐条试算 IS")
    ap.add_argument("--segment", choices=["is"], default="is")
    ap.add_argument("--out", default=os.path.join(ROOT, "benchmarks", "is_null.json"))
    args = ap.parse_args()
    with open(FORMULAS_JSON, encoding="utf-8") as f:
        lib = json.load(f)
    load_end, seg_start, seg_end, seg_name = bt.SEGMENTS[args.segment]
    engine.LOAD_END = load_end
    try:
        wide = engine.load_wide()
    except Exception as e:
        print(f"数据加载失败：{e}")
        return 1
    items, failed = [], []
    for it in lib["items"]:
        if it["status"] != "runnable":
            continue
        try:
            fac = engine.eval_formula(it["formula"], wide)
            fac = fac[(fac.index >= seg_start) & (fac.index <= seg_end)]
            daily = bt.daily_ic_series(fac, wide)
            ic = float(daily.mean()) if len(daily) else None
            icir = float(daily.mean() / daily.std()) if len(daily) >= 2 and daily.std() else None
            items.append({"id": it["id"], "family": it["family"], "formula": it["formula"],
                          "ic": ic, "icir": icir, "status": "scored", "error": ""})
        except Exception as e:
            failed.append({"id": it["id"], "family": it["family"], "formula": it["formula"],
                           "ic": None, "icir": None, "status": "failed", "error": str(e)})
    ics = [it["ic"] for it in items if it["ic"] is not None]
    quantiles = {}
    if ics:
        arr = np.array(ics)
        quantiles = {
            "median": float(np.median(arr)),
            "p75": float(np.quantile(arr, 0.75)),
            "p90": float(np.quantile(arr, 0.90)),
            "max": float(np.max(arr)),
            "min": float(np.min(arr)),
        }
    excluded = [{"id": it["id"], "family": it["family"], "reason": it["reason"]}
                for it in lib["items"] if it["status"] == "excluded"]
    out = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "generated_by": "tools/backtest/run_null.py",
        "segment": args.segment,
        "data_version": bt.data_version(wide),
        "runnable_count": len(items) + len(failed),
        "scored_count": len(items),
        "failed_count": len(failed),
        "excluded_count": len(excluded),
        "quantiles": quantiles,
        "items": items + failed,
        "excluded": excluded,
        "note": "分位数只按试算成功的条目算；白名单通过但试算失败的条目在 items 里 status=failed，不计入分位数。",
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"白名单通过 {len(items) + len(failed)} 条：试算成功 {len(items)} 条，失败 {len(failed)} 条；"
          f"库内排除 {len(excluded)} 条")
    if quantiles:
        print("20 日 IC 分布：中位 {:.4f}，75% {:.4f}，90% {:.4f}，最大 {:.4f}".format(
            quantiles["median"], quantiles["p75"], quantiles["p90"], quantiles["max"]))
    for it in failed:
        print(f"试算失败 {it['id']}：{it['error']}")
    print(f"写出 {args.out}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
