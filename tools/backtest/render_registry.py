"""登记视图生成：从 research/registry.jsonl 生成 research/experiment_registry.md。
用法：python tools/backtest/render_registry.py
本文件是视图的唯一来源，不要手工改表；改登记请跑回测入口，或改 jsonl 后重新生成。
"""

import json
import os

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
REGISTRY_PATH = os.path.join(ROOT, "research", "registry.jsonl")
REGISTRY_MD = os.path.join(ROOT, "research", "experiment_registry.md")

RULES = ("规则：公式、方向、持有期、参数或机制发生变化时新建版本；不得覆盖已有行。"
         "Holdout 访问需记录日期、原因和研究者明确授权。")

ROUND2_NOTE = ("第 2 轮探索性 IS（2026-11-22，研究者指令）：H005/H006 已在辩论后淘汰，"
               "补跑 IS 仅用于对照辩论判断，不改变淘汰状态、不构成 OOS 验证资格。成绩单："
               "H005-v1 `results/is_20261122_195425_231.json`、H005-v2 `results/is_20261122_195448_702.json`、"
               "H006-v1 `results/is_20261122_195449_977.json`、H006-v2 `results/is_20261122_195450_401.json`。")


def load_registry():
    if not os.path.exists(REGISTRY_PATH):
        return []
    recs = []
    with open(REGISTRY_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                recs.append(json.loads(line))
    return recs


def _fmt(x, n=4):
    return "—" if x is None else f"{x:.{n}f}"


def render():
    recs = load_registry()
    lines = [
        "# 实验登记 Experiment Registry",
        "",
        "仅主 agent 维护。本文件记录进入经验验证的冻结版本；研究阶段的候选不在此登记。",
        "",
        "本文件由 `tools/backtest/render_registry.py` 从 `research/registry.jsonl` 生成，不要手工改表；"
        "改登记请跑回测入口，或改 jsonl 后重新生成。",
        "",
        "| 版本 | 对子 | 公式哈希 | 方向 | 持有期 | 参数 | 20日IC | ICIR | 成本后多空 | 全库百分位 | IS 截止日 | 统计区间 | OOS 规则 | 状态 |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in recs:
        sc = r.get("scorecard_v2") or {}
        pct = r.get("percentile") or {}
        version = "-".join(x for x in (r.get("hypothesis_id"), r.get("version")) if x) or "—"
        rng = r.get("segment_range")
        rng_s = f"{rng[0]}~{rng[1]}" if rng else "—"
        pct_s = f"{pct['percentile']}%（n={pct['n']}）" if pct.get("percentile") is not None else "—"
        ca = sc.get("成本后多空收益")
        lines.append("| " + " | ".join([
            version,
            r.get("hypothesis_id") or "—",
            r.get("formula_hash") or "—",
            r.get("direction") or "—",
            r.get("holding_period") or "—",
            r.get("params") or "—",
            _fmt(sc.get("IC均值")),
            _fmt(sc.get("ICIR"), 3),
            f"{ca * 100:.2f}%" if ca is not None else "—",
            pct_s,
            r.get("is_end") or "—",
            rng_s,
            r.get("oos_rule") or "—",
            r.get("status") or "—",
        ]) + " |")
    lines += ["", RULES, "", ROUND2_NOTE, ""]
    with open(REGISTRY_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return len(recs)


def main():
    n = render()
    print(f"登记 {n} 行，已生成 {REGISTRY_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
