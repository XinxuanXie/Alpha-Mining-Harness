"""把登记表里的成绩单摘要写回假设池对应条目。

用法：
  python tools/backtest/pool_sync.py --hypothesis H006 [--version v1] [--segment is]
  python tools/backtest/pool_sync.py --all [--dry-run]

只读 research/registry.jsonl，只改 research/hypothesis_pool.md。
成绩单块由本脚本生成，格式固定、幂等：同一（编号，版本，数据段）重跑只更新块内容，
不重复写；不要手工改块内文字，也不要手工抄数字进池子。
登记里没有对应编号、或池中找不到该编号条目的，打印警告并跳过，不建新条目、不修池子。
等权合成等非池内对子的登记行（编号为空）直接跳过。
"""

import argparse
import json
import os
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
POOL_PATH = os.path.join(ROOT, "research", "hypothesis_pool.md")
REGISTRY_PATH = os.path.join(ROOT, "research", "registry.jsonl")

SEG_LABEL = {
    "is": "IS（2010–2016）",
    "oos": "OOS（2017–2019）",
    "holdout": "holdout（2020–2026）",
}

BAR_IC = 0.02
BAR_ICIR = 0.2


def _r(x, n=4):
    return "—" if x is None else f"{x:.{n}f}"


def _pct(x, n=2):
    return "—" if x is None else f"{x * 100:.{n}f}%"


def _signed(x, n=4):
    return "—" if x is None else f"{x:+.{n}f}"


def load_registry(path):
    recs = []
    if not os.path.exists(path):
        return recs
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                recs.append(json.loads(line))
    return recs


def verdict(sc):
    ic = sc.get("IC均值")
    icir = sc.get("ICIR")
    if ic is None or icir is None:
        return "成绩单不完整，无法判定"
    if ic >= BAR_IC and icir >= BAR_ICIR:
        return "达到参考线（20日IC ≥ 0.02 且 ICIR ≥ 0.2）"
    return "未达参考线（20日IC ≥ 0.02 且 ICIR ≥ 0.2）"


def baseline_line(comp):
    if not comp:
        return "基线对照：未跑"
    rows = comp.get("baselines") or []
    if not rows:
        return "基线对照：未跑"
    parts = []
    for row in rows:
        if "error" in row:
            parts.append(f"{row['id']} 求值失败")
            continue
        flag = "重复嫌疑" if row.get("重复嫌疑") else ""
        parts.append(
            f"{row['id']} ΔIC {_signed(row.get('dIC'))}，"
            f"Δ成本后收益 {_pct(row.get('d成本后多空收益'))}，"
            f"rank相关 {_r(row.get('rank相关'), 3)}"
            + (f"（{flag}）" if flag else "")
        )
    ver = comp.get("version", "")
    return f"基线对照（{ver}）：{"；".join(parts)}"


def percentile_line(pct):
    if not pct or pct.get("percentile") is None:
        return "全库百分位：未生成（先跑 tools/backtest/run_null.py）"
    return f"全库百分位：{pct['percentile']}%（n={pct.get('n')}）"


def build_block(rec):
    hid = rec.get("hypothesis_id") or ""
    ver = rec.get("version") or ""
    seg = rec.get("segment") or ""
    sc = rec.get("scorecard_v2") or {}
    begin = f"<!-- pool-sync:{hid}:{ver}:{seg} begin -->"
    end = f"<!-- pool-sync:{hid}:{ver}:{seg} end -->"
    seg_label = SEG_LABEL.get(seg, seg)
    created = rec.get("created_at") or "—"
    lines = [
        begin,
        "- 回测成绩单（`tools/backtest/pool_sync.py` 生成，请勿手工改）：",
        f"  - 版本 {ver} · 数据段 {seg_label} · 登记时间 {created}",
        f"  - 20日IC {_r(sc.get('IC均值'))} · ICIR {_r(sc.get('ICIR'), 3)} · "
        f"Newey-West t {_r(sc.get('Newey-West t'), 2)} · "
        f"行业中性IC {_r(sc.get('行业中性IC'))} · "
        f"覆盖率 {_r(sc.get('覆盖率'), 3)} · 有效天数 {sc.get('有效天数') if sc.get('有效天数') is not None else '—'}",
        f"  - 多空价差 {_pct(sc.get('多空价差'))} · "
        f"成本后多空收益 {_pct(sc.get('成本后多空收益'))} · "
        f"换手率 {_r(sc.get('换手率'), 3)} · "
        f"多空胜率 {_r(sc.get('多空胜率'), 3)} · 分组单调性 {_r(sc.get('分组单调性'), 2)}",
        f"  - {percentile_line(rec.get('percentile'))} · {baseline_line(rec.get('baselines'))}",
        f"  - 结论：{verdict(sc)}",
        end,
    ]
    return begin, end, lines


def find_section(lines, hid):
    """返回 (start, end)：start 为 '### Hxxx' 标题行下标；end 为下一条 '---' 或 '### ' 行下标（不含），无则为文件尾。找不到返回 (None, None)。"""
    start = None
    for i, line in enumerate(lines):
        s = line.strip()
        if s == f"### {hid}" or s.startswith(f"### {hid} "):
            start = i
            break
    if start is None:
        return None, None
    end = len(lines)
    for j in range(start + 1, len(lines)):
        s = lines[j].strip()
        if s == "---" or s.startswith("### "):
            end = j
            break
    return start, end


def sync_record(lines, rec):
    """把一条登记写进池子对应条目。返回 (changed, message)。"""
    hid = rec.get("hypothesis_id") or ""
    ver = rec.get("version") or ""
    seg = rec.get("segment") or ""
    begin, end, block = build_block(rec)
    start, sec_end = find_section(lines, hid)
    if start is None:
        return False, f"{hid} {ver} {seg}：池中无此编号条目，跳过"
    # 块已存在则原地替换（块的第一行就是 begin 标记，整块替换，不留残行）
    for i in range(start, sec_end):
        if lines[i].strip() == begin:
            for j in range(i, sec_end):
                if lines[j].strip() == end:
                    lines[i:j + 1] = block
                    return True, f"{hid} {ver} {seg}：已更新成绩单块"
            return False, f"{hid} {ver} {seg}：成绩单块标记不完整（有 begin 无 end），请手工检查后重跑"
    # 不存在则插入：接在该条目内最后一个成绩单块之后，否则接在条目末尾
    insert_at = sec_end
    for i in range(start, sec_end):
        if lines[i].strip().startswith("<!-- pool-sync:") and lines[i].strip().endswith(" end -->"):
            insert_at = i + 1
    # 块前留一空行（若上一行非空）
    prefix = []
    if insert_at > start and lines[insert_at - 1].strip() != "":
        prefix = [""]
    lines[insert_at:insert_at] = prefix + block + [""]
    return True, f"{hid} {ver} {seg}：已写入成绩单块"


def main():
    ap = argparse.ArgumentParser(description="把 registry.jsonl 的成绩单摘要写回 hypothesis_pool.md")
    ap.add_argument("--hypothesis", default=None, help="对子编号，如 H006")
    ap.add_argument("--version", default=None)
    ap.add_argument("--segment", default=None, choices=["is", "oos", "holdout"])
    ap.add_argument("--all", action="store_true", help="同步登记表里全部池内对子")
    ap.add_argument("--dry-run", action="store_true", help="只打印将要做的事，不写文件")
    ap.add_argument("--pool", default=POOL_PATH)
    ap.add_argument("--registry", default=REGISTRY_PATH)
    args = ap.parse_args()
    if not args.all and not args.hypothesis:
        print("用法：--hypothesis Hxxx 或 --all")
        return 1
    recs = load_registry(args.registry)
    selected = []
    for r in recs:
        hid = r.get("hypothesis_id") or ""
        if not hid:
            continue
        if args.all:
            selected.append(r)
        elif hid == args.hypothesis:
            if args.version and r.get("version") != args.version:
                continue
            if args.segment and r.get("segment") != args.segment:
                continue
            selected.append(r)
    if not selected:
        print("登记表里没有匹配的记录")
        return 1
    with open(args.pool, encoding="utf-8") as f:
        lines = f.read().split("\n")
    failed = 0
    for r in selected:
        changed, msg = sync_record(lines, r)
        if args.dry_run:
            print(f"[dry-run] {msg}")
        else:
            print(msg)
        if not changed:
            failed += 1
    if args.dry_run:
        print("dry-run：未写文件")
        return 0 if failed == 0 else 1
    with open(args.pool, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"已写回 {args.pool}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
