"""经典库抽取：把 classic_library/*.md 里 200 条目的公式抽成机器可读的表。
用法：python tools/backtest/extract_library.py
产物：
  classic_library/formulas.json —— 每条：编号、家族、名称、公式原文、白名单状态
  benchmarks/gap_report.md —— 不可跑条目清单（原因）与 engine 修补解锁的条目
只做文本解析与白名单校验，不接触数据；白名单通过只代表“可试算”，
真正可跑与否由 tools/backtest/run_null.py 在有数据的机器上试算后判定。
"""

import json
import os
import re
import sys

# 本脚本在 tools/backtest/ 下，engine.py 在仓库根目录
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

import engine

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
LIB_DIR = os.path.join(ROOT, "classic_library")
FORMULAS_JSON = os.path.join(LIB_DIR, "formulas.json")
GAP_MD = os.path.join(ROOT, "benchmarks", "gap_report.md")

ENTRY_RE = re.compile(r"^-\s+\*\*(C\d+)\s+([^*]+?)\*\*[：:]\s*")
NEEDS_FIX_RES = [
    (re.compile(r"\breturns\b"), "uses returns"),
    (re.compile(r"\bts_quantile\s*\("), "uses ts_quantile"),
    (re.compile(r"\bts_cov\s*\("), "uses ts_cov"),
    (re.compile(r"(?<![\w])min\s*\("), "uses min"),
    (re.compile(r"(?<![\w])max\s*\("), "uses max"),
]


def parse_file(path):
    """解析一个家族文件，返回 (家族名, [条目])。条目公式取行内第一个反引号段。"""
    family = None
    items = []
    unparsed = []
    with open(path, encoding="utf-8") as f:
        for ln, raw in enumerate(f, 1):
            line = raw.strip()
            if line.startswith("# ") and family is None:
                family = line[2:].strip()
                continue
            if not line.startswith("- **C"):
                continue
            m = ENTRY_RE.match(line)
            if not m:
                unparsed.append((ln, line[:120]))
                continue
            rest = line[m.end():]
            tick = rest.find("`")
            if tick < 0:
                unparsed.append((ln, line[:120]))
                continue
            end = rest.find("`", tick + 1)
            if end < 0:
                unparsed.append((ln, line[:120]))
                continue
            formula = rest[tick + 1:end].strip()
            items.append({
                "id": m.group(1),
                "family": family,
                "family_file": os.path.basename(path),
                "name": m.group(2).strip(),
                "formula": formula,
            })
    return family, items, unparsed


def main():
    all_items = []
    unparsed_all = []
    for fname in sorted(os.listdir(LIB_DIR)):
        if not fname.endswith(".md"):
            continue
        family, items, unparsed = parse_file(os.path.join(LIB_DIR, fname))
        all_items.extend(items)
        for ln, text in unparsed:
            unparsed_all.append((fname, ln, text))
    if unparsed_all:
        print("有条目解析失败（格式变了，需人工看）：")
        for fname, ln, text in unparsed_all:
            print(f"- {fname}:{ln} {text}")
        return 1
    all_items.sort(key=lambda it: int(it["id"][1:]))

    for it in all_items:
        ok, bad = engine.check_whitelist(it["formula"])
        needs_fix = [tag for rx, tag in NEEDS_FIX_RES if rx.search(it["formula"])]
        it["needs_engine_fix"] = bool(needs_fix)
        it["engine_fix_tags"] = needs_fix
        if ok:
            it["status"] = "runnable"
            it["reason"] = ""
        else:
            it["status"] = "excluded"
            seen = []
            for b in bad:
                if b not in seen:
                    seen.append(b)
            it["reason"] = "；".join(seen)

    runnable = [it for it in all_items if it["status"] == "runnable"]
    excluded = [it for it in all_items if it["status"] == "excluded"]
    unlocked = [it for it in runnable if it["needs_engine_fix"]]
    out = {
        "generated_by": "tools/backtest/extract_library.py",
        "total": len(all_items),
        "runnable": len(runnable),
        "excluded": len(excluded),
        "note": "runnable 只代表通过白名单校验；真正可跑与否由 run_null.py 试算后判定。",
        "items": all_items,
    }
    with open(FORMULAS_JSON, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    lines = [
        "# 经典库可跑性缺口报告",
        "",
        "由 `tools/backtest/extract_library.py` 生成；白名单校验，不接触数据。",
        "",
        f"共 {len(all_items)} 条：白名单通过 {len(runnable)} 条，排除 {len(excluded)} 条。",
        f"其中 {len(unlocked)} 条靠本次 engine 修补解锁（`returns` 字段、`ts_quantile`/`ts_cov`/`min`/`max` 算子）。",
        "白名单通过只代表公式写得合法，真正可跑与否以 `run_null.py` 在有数据的机器上的试算为准；",
        "试算失败的条目会记进 `benchmarks/is_null.json` 的 excluded 栏。",
        "",
        "## 排除条目（需重写，不硬凑）",
        "",
        "| 编号 | 家族 | 公式原文 | 原因 |",
        "|---|---|---|---|",
    ]
    for it in excluded:
        formula = it["formula"].replace("|", "\\|")
        lines.append(f"| {it['id']} | {it['family']} | `{formula}` | {it['reason']} |")
    lines += [
        "",
        "## 靠 engine 修补解锁的条目",
        "",
        "以下条目在旧 engine 下跑不了（缺 `returns` 字段或新算子），本次修补后白名单通过：",
        "",
    ]
    for it in unlocked:
        lines.append(f"- {it['id']} {it['name']}（{', '.join(it['engine_fix_tags'])}）")
    from collections import Counter
    reason_count = Counter()
    for it in excluded:
        for r in it["reason"].split("；"):
            reason_count[r] += 1
    lines += [
        "",
        "## 排除原因统计",
        "",
        "同一条目有多个原因时各计一次；数量最大的几组是下一批修库时最值得先动的：",
        "",
    ]
    for r, n in reason_count.most_common():
        lines.append(f"- {n} 条：{r}")
    lines += [
        "",
        "## 已知库内容错误（待修，与可跑性无关）",
        "",
        "- C140：库中 `C140 = 2·C134−1` 的关系式是错的。第 4 轮复核的正确关系：close>open 时 `C140 = 2(C134+C138)−1`，且 `C135−C137 = −C139`。",
        "- C41：库原文是文字描述（`neg(过去 1 年日收益对市场收益回归的残差标准差)`），不是可算公式；",
        "  基线集里暂用 `neg(ts_std(resid_ret, 252))` 作为可算近似（252 日残差标准差取负），见 `benchmarks/baselines.json` 的注记。",
        "",
    ]
    os.makedirs(os.path.dirname(GAP_MD), exist_ok=True)
    with open(GAP_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"共 {len(all_items)} 条：白名单通过 {len(runnable)} 条（含 engine 修补解锁 {len(unlocked)} 条），排除 {len(excluded)} 条")
    print(f"写出 {FORMULAS_JSON}")
    print(f"写出 {GAP_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
