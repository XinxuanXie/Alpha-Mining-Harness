"""回测统一入口：一段口径、一张成绩单 v2、一组基线对照、一张登记表。
用法：
  python tools/backtest/backtest.py --segment is --formula "neg(close / delay(close, 20) - 1)"
  python tools/backtest/backtest.py --segment is --batch formulas.txt
  python tools/backtest/backtest.py --segment is --formula "..." --hypothesis H006 --version v1
  python tools/backtest/backtest.py --segment holdout --formula "..." --allow-holdout --holdout-reason "OOS 通过，研究者授权"
成绩单只算不判：过不过门由调用方看数字决定。门槛不变：20 日 IC >= 0.02 且 ICIR >= 0.2。
holdout 段封存：不加 --allow-holdout 并写原因，直接拒绝；原因与日期写进登记。
"""

import argparse
import getpass
import hashlib
import json
import math
import os
import subprocess
import sys
from datetime import datetime

import numpy as np
import pandas as pd

# 本脚本在 tools/backtest/ 下，engine.py 在仓库根目录；同目录的 render_registry 也要能 import
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import engine
from engine import MIN_STOCKS

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
BASELINES_JSON = os.path.join(ROOT, "benchmarks", "baselines.json")
NULL_JSON = os.path.join(ROOT, "benchmarks", "is_null.json")
REGISTRY_PATH = os.path.join(ROOT, "research", "registry.jsonl")

# ============================================================
# 数据段（集中一处；三个旧脚本已删，只留这一个入口）
# ============================================================
SEGMENTS = {
    # 段名：(加载止日，统计起日，统计止日，段中文名)
    # OOS 加载须越过段尾：标签要用到段尾之后 21 天的价格
    "is": ("2016-12-31", "2010-01-01", "2016-12-31", "IS 段"),
    "oos": ("2020-04-30", "2017-01-01", "2019-12-31", "OOS 段"),
    "holdout": ("2026-09-30", "2020-01-01", "2026-09-30", "holdout 段"),
}
JUDGE_H = 20  # 判定期限（日）
COST_BPS = 10  # 单边成本（bps），与 V2.1 的 10bps 一致
ENTRY_NOTE = "标签 close(t+1+h)/close(t+1)-1：t+1 日收盘入场（非次日开盘）"

# ============================================================
# 算指标：基础量为日 IC（截面 Spearman 相关）
# 标签：close(t+1+h)/close(t+1)-1，即从次日起算的 h 日收益
# ============================================================
def _label(close, h):
    return close.shift(-(1 + h)) / close.shift(-1) - 1

def _ic_series(factor, label):
    """逐日截面 Spearman 相关，返回去掉缺失日的日 IC 序列。"""
    fr = factor.rank(axis=1, method="average")
    lr = label.rank(axis=1, method="average")
    mask = fr.notna() & lr.notna()
    f = fr.where(mask).fillna(0.0)
    l = lr.where(mask).fillna(0.0)
    n = mask.sum(axis=1).astype(float)
    sx, sy = f.sum(axis=1), l.sum(axis=1)
    sxx, syy = (f * f).sum(axis=1), (l * l).sum(axis=1)
    sxy = (f * l).sum(axis=1)
    cov = sxy - sx * sy / n
    var_x = sxx - sx * sx / n
    var_y = syy - sy * sy / n
    denom = np.sqrt(var_x * var_y)
    daily = (cov / denom).where((n >= MIN_STOCKS) & (var_x > 0) & (var_y > 0))
    return daily.dropna()

def _mean_or_none(series):
    return None if len(series) == 0 else float(series.mean())

def _t_of(series):
    if len(series) < 2:
        return None
    sd = float(series.std())
    if not sd:
        return None
    return float(series.mean() / (sd / np.sqrt(len(series))))

def _newey_west_t(series, lag=20):
    """日 IC 序列的 Newey-West t 值（Bartlett 核，滞后阶数 = 判定期限 20 日）。"""
    x = np.asarray(series.dropna(), dtype=float)
    t = len(x)
    if t < 2:
        return None
    mean = float(x.mean())
    d = x - mean
    var = float(np.dot(d, d) / t)
    for j in range(1, min(lag, t - 1) + 1):
        gamma_j = float(np.dot(d[j:], d[:-j]) / t)
        var += 2 * (1 - j / (lag + 1)) * gamma_j
    if var <= 0:
        return None
    se = math.sqrt(var / t)
    return float(mean / se) if se else None

def _yearly_ic(series):
    """按日历年分组的 IC 均值与 ICIR。"""
    out = {}
    for yr, g in series.groupby(series.index.year):
        sd = float(g.std()) if len(g) >= 2 else None
        out[str(yr)] = {
            "IC均值": float(g.mean()),
            "ICIR": float(g.mean() / sd) if sd else None,
            "天数": int(len(g)),
        }
    return out

def compute_metrics(factor, wide):
    """算 IC 均值、ICIR、t 值、各持有期 IC 与覆盖率（判定期限 20 日），返回字典；算不出的记 None。"""
    close = wide["close"]
    label = _label(close, JUDGE_H)
    daily = _ic_series(factor, label)
    ic_mean = _mean_or_none(daily)
    sd = float(daily.std()) if len(daily) >= 2 else None
    icir = float(ic_mean / sd) if (ic_mean is not None and sd) else None
    t_val = _t_of(daily)

    by_h = {str(hh): (ic_mean if hh == JUDGE_H else _mean_or_none(_ic_series(factor, _label(close, hh))))
            for hh in (1, 5, 10, 20, 60)}

    # 覆盖率只在因子所在段内算：分母是段内有价格的股票日数，不含加载窗口的其余日期
    close_in = close.reindex(factor.index)
    coverage = float((factor.notna() & close_in.notna()).sum().sum() / close_in.notna().sum().sum())

    return {
        "IC均值": ic_mean, "ICIR": icir, "t值": t_val,
        "各持有期IC": by_h,
        "覆盖率": coverage,
    }

# ============================================================
# 序列：日 IC 与五组日收益（成绩单与报告共用同一份计算，不重复实现）
# ============================================================
def daily_ic_series(factor, wide, h=JUDGE_H):
    """逐日截面 Rank IC 序列（h 日标签）。"""
    return _ic_series(factor, _label(wide["close"], h))

def quintile_daily(factor, wide, h=JUDGE_H):
    """按因子截面分位分五组，返回每日五组平均标签收益（行=日期，列=Q1..Q5）。"""
    label = _label(wide["close"], h)
    fr = factor.rank(axis=1, pct=True)
    lab = label.where(factor.notna())
    cols = []
    for qi in range(5):
        lo, hi = qi / 5, (qi + 1) / 5
        mask = (fr > lo) & (fr <= hi) if qi else (fr >= 0) & (fr <= hi)
        cols.append(lab.where(mask).mean(axis=1))
    return pd.DataFrame(cols, index=["Q1", "Q2", "Q3", "Q4", "Q5"]).T

# ============================================================
# 成绩单 v2 新增量：换手、成本后收益、行业中性 IC
# 口径写死：Q5 做多 / Q1 做空等权，日频再平衡；换手 = 当日权重变化绝对值之和的日均值
# ============================================================
def portfolio_weights(factor):
    """Q5 做多 / Q1 做空等权组合的日权重（每腿权重和为 +1 / -1，无持仓日为 0）。"""
    fr = factor.rank(axis=1, pct=True)
    long_m = fr > 0.8
    short_m = fr <= 0.2
    n_long = long_m.sum(axis=1).replace(0, np.nan)
    n_short = short_m.sum(axis=1).replace(0, np.nan)
    w = long_m.div(n_long, axis=0).fillna(0.0) - short_m.div(n_short, axis=0).fillna(0.0)
    return w.fillna(0.0)

def turnover(factor):
    """换手率：当日权重变化绝对值之和的日均值（只计有持仓的日子）。"""
    w = portfolio_weights(factor)
    dw = w.diff().abs().sum(axis=1)
    active = w.abs().sum(axis=1) > 0
    s = dw[active].dropna()
    return float(s.mean()) if len(s) else None

def sector_neutral_ic_series(factor, wide):
    """行业中性日 IC：每日先在 GICS 行业内对因子去均值，再算截面 Spearman IC。
    行业信息缺失（engine.SECTOR_OF 为空）时返回 None。无行业归属的股票当日记缺失。"""
    if not engine.SECTOR_OF:
        return None
    label = _label(wide["close"], JUDGE_H)
    cols_by_sector = {}
    for c in factor.columns:
        s = engine.SECTOR_OF.get(int(c))
        if s:
            cols_by_sector.setdefault(s, []).append(c)
    dm = pd.DataFrame(np.nan, index=factor.index, columns=factor.columns)
    for cols in cols_by_sector.values():
        sub = factor[cols]
        dm[cols] = sub.sub(sub.mean(axis=1), axis=0)
    return _ic_series(dm, label)

def quick_stats(factor, wide, cost_bps=COST_BPS):
    """轻量统计（基线对照与零分布用）：只算 20 日 IC、多空价差、换手、成本后收益。"""
    daily = daily_ic_series(factor, wide)
    qdf = quintile_daily(factor, wide)
    spread = float((qdf["Q5"] - qdf["Q1"]).mean())
    to = turnover(factor)
    cost_adj = spread - to * cost_bps / 10000.0 if to is not None else None
    return {
        "IC均值": _mean_or_none(daily),
        "ICIR": float(daily.mean() / daily.std()) if len(daily) >= 2 and daily.std() else None,
        "多空价差": spread,
        "换手率": to,
        "成本后多空收益": cost_adj,
    }

# ============================================================
# 成绩单 v2：原有 15 项全部保留，新增 6 项 + 入场口径注记
# 新增指标只报告、不进门。门槛不变。
# ============================================================
def scorecard(factor, wide, cost_bps=COST_BPS):
    m = compute_metrics(factor, wide)
    daily_ic = daily_ic_series(factor, wide)
    # 因子自相关：逐日截面 Pearson(fac_t, fac_{t-1}) 取均值（当日重合股票 ≥30 才计入）
    prev = factor.shift(1)
    both = factor.notna() & prev.notna()
    ac = []
    for i in range(factor.shape[0]):
        mask = both.iloc[i]
        if mask.sum() >= 30:
            a = factor.iloc[i][mask]
            b = prev.iloc[i][mask]
            if a.std() > 0 and b.std() > 0:
                ac.append(np.corrcoef(a, b)[0, 1])
    autocorr = float(np.nanmean(ac)) if ac else None
    # 分组：五组日收益取全段均值；单调性、多空价差由此派生
    qdf = quintile_daily(factor, wide)
    q_avg = [float(x) for x in qdf.mean()]
    mono = float(np.corrcoef(np.arange(1, 6), pd.Series(q_avg).rank())[0, 1])
    spread = qdf["Q5"] - qdf["Q1"]
    spread_mean = float(spread.mean())
    to = turnover(factor)
    cost_adj = spread_mean - to * cost_bps / 10000.0 if to is not None else None
    sn = sector_neutral_ic_series(factor, wide)
    return {
        "IC均值": m["IC均值"], "ICIR": m["ICIR"], "t值": m["t值"],
        "覆盖率": m["覆盖率"], "因子自相关": autocorr,
        "各持有期IC": m["各持有期IC"],
        "五组收益": q_avg, "分组单调性": mono,
        "多空价差": spread_mean, "多空胜率": float((spread.dropna() > 0).mean()),
        "方向一致率": float((daily_ic > 0).mean()),
        "换手率": to,
        "成本后多空收益": cost_adj,
        "行业中性IC": float(sn.mean()) if sn is not None and len(sn) else None,
        "Newey-West t": _newey_west_t(daily_ic, lag=JUDGE_H),
        "分年IC": _yearly_ic(daily_ic),
        "有效天数": int(len(daily_ic)),
        "入场口径": ENTRY_NOTE,
    }

def scorecard_text(sc):
    """成绩单的固定文本格式：只有数字，不含判定。"""
    def r(x, n=4):
        return None if x is None else round(x, n)
    lines = [
        f"20日IC {r(sc['IC均值'])}",
        f"ICIR {r(sc['ICIR'], 3)}",
        f"t值 {r(sc['t值'], 2)}",
        f"Newey-West t {r(sc.get('Newey-West t'), 2)}",
        f"覆盖率 {r(sc['覆盖率'], 3)}",
        f"有效天数 {sc.get('有效天数')}",
        f"因子自相关 {r(sc['因子自相关'], 3)}",
        "持有期IC " + " ".join(f"{k}日 {r(v)}" for k, v in sc["各持有期IC"].items()),
        "五组收益% " + " ".join(str(round(x * 100, 2)) for x in sc["五组收益"]),
        f"分组单调性 {r(sc['分组单调性'], 2)}",
        f"多空价差% {round(sc['多空价差'] * 100, 2)}",
        f"换手率 {r(sc.get('换手率'), 3)}",
        f"成本后多空收益% {round(sc['成本后多空收益'] * 100, 2) if sc.get('成本后多空收益') is not None else None}",
        f"多空胜率 {r(sc['多空胜率'], 3)}",
        f"方向一致率 {r(sc['方向一致率'], 3)}",
        f"行业中性IC {r(sc.get('行业中性IC'))}",
        f"入场口径 {sc.get('入场口径', '')}",
    ]
    by_year = sc.get("分年IC") or {}
    if by_year:
        lines.append("分年IC " + " ".join(f"{y}:{r(v['IC均值'])}" for y, v in sorted(by_year.items())))
    return "\n".join(lines)

# ============================================================
# 基线对照：同段、同口径跑固定基线集
# 输出 ΔIC、Δ成本后收益、与各基线的截面 rank 相关（|ρ| >= 0.90 标“重复嫌疑”）
# ============================================================
def load_baselines():
    with open(BASELINES_JSON, encoding="utf-8") as f:
        return json.load(f)

def load_null():
    if not os.path.exists(NULL_JSON):
        return None
    with open(NULL_JSON, encoding="utf-8") as f:
        return json.load(f)

def percentile_of(ic, null_doc):
    """全库百分位：该 IC 在零分布可跑条目中的排名（%）。零分布未生成时返回 None。"""
    if null_doc is None or ic is None:
        return None
    ics = [it["ic"] for it in null_doc.get("items", []) if it.get("ic") is not None]
    if not ics:
        return None
    below = sum(1 for x in ics if x < ic)
    return {"percentile": round(100.0 * below / len(ics), 1), "n": len(ics)}

def compare_baselines(factor, wide, seg_start, seg_end, cost_bps=COST_BPS):
    """候选因子与基线集逐条对照。基线求值失败时记 error，不中断整轮。"""
    doc = load_baselines()
    cand = quick_stats(factor, wide, cost_bps)
    rows = []
    for b in doc["baselines"]:
        row = {"id": b["id"], "name": b.get("name", ""), "formula": b["formula"]}
        try:
            bf = engine.eval_formula(b["formula"], wide)
            bf = bf[(bf.index >= seg_start) & (bf.index <= seg_end)]
            bs = quick_stats(bf, wide, cost_bps)
            rc = _ic_series(factor, bf)
            rho = float(rc.mean()) if len(rc) else None
        except Exception as e:
            row["error"] = str(e)
            rows.append(row)
            continue
        row["IC均值"] = bs["IC均值"]
        row["成本后多空收益"] = bs["成本后多空收益"]
        row["dIC"] = (cand["IC均值"] - bs["IC均值"]
                      if cand["IC均值"] is not None and bs["IC均值"] is not None else None)
        row["d成本后多空收益"] = (cand["成本后多空收益"] - bs["成本后多空收益"]
                                  if cand["成本后多空收益"] is not None
                                  and bs["成本后多空收益"] is not None else None)
        row["rank相关"] = rho
        row["重复嫌疑"] = bool(rho is not None and abs(rho) >= 0.90)
        rows.append(row)
    return {"version": doc["version"], "candidate": cand, "baselines": rows}

def baselines_text(comp):
    lines = [f"基线对照（{comp['version']}）："]
    for row in comp["baselines"]:
        if "error" in row:
            lines.append(f"  {row['id']}：求值失败：{row['error']}")
            continue
        def r(x, n=4):
            return None if x is None else round(x, n)
        flag = " 重复嫌疑" if row.get("重复嫌疑") else ""
        lines.append(
            f"  {row['id']} {row['name']}：IC {r(row['IC均值'])}，ΔIC {r(row['dIC'])}，"
            f"Δ成本后收益% {round(row['d成本后多空收益'] * 100, 2) if row['d成本后多空收益'] is not None else None}，"
            f"rank相关 {r(row['rank相关'], 3)}{flag}")
    return "\n".join(lines)

# ============================================================
# 登记：research/registry.jsonl，一行一个冻结版本；同一公式 + 同一段只记一次
# ============================================================
def formula_hash(formula):
    return hashlib.sha256(formula.encode("utf-8")).hexdigest()[:16]

def data_version(wide):
    close = wide["close"]
    rng = f"{close.index.min().date()} 至 {close.index.max().date()}"
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        commit = "unknown"
    return {"panel_range": rng, "git_commit": commit}

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

def append_registry(record):
    """同一公式哈希 + 同一段已存在时不重复记，返回 (是否新增, 记录)。"""
    for r in load_registry():
        if r["formula_hash"] == record["formula_hash"] and r["segment"] == record["segment"]:
            return False, r
    os.makedirs(os.path.dirname(REGISTRY_PATH), exist_ok=True)
    with open(REGISTRY_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return True, record

def _created_by():
    try:
        return getpass.getuser()
    except Exception:
        return "researcher"

# ============================================================
# 主流程：公式（文字）→ 检查 → 求值 → 切段 → 成绩单 v2 → 基线对照 → 登记
# ============================================================
def parse_batch(path):
    """批量文件：每行一个公式，或 hypothesis<TAB>version<TAB>公式；空行与 # 开头行跳过。"""
    runs = []
    with open(path, encoding="utf-8") as f:
        for ln, raw in enumerate(f, 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) == 3:
                runs.append({"hypothesis": parts[0].strip() or None,
                             "version": parts[1].strip() or None,
                             "formula": parts[2].strip()})
            elif len(parts) == 1:
                runs.append({"hypothesis": None, "version": None, "formula": parts[0]})
            else:
                print(f"批量文件第 {ln} 行格式不对（应为“公式”或“假设<TAB>版本<TAB>公式”），跳过")
    return runs

def run_one(formula, wide, seg, seg_start, seg_end, seg_name, args, null_doc):
    """跑一条公式：求值、成绩单、基线对照、百分位、打印、存档、登记。返回 0/1。"""
    ok, bad = engine.check_whitelist(formula)
    if not ok:
        print(f"公式错误：{'、'.join(bad)} 不在清单内")
        return 1
    try:
        fac = engine.eval_formula(formula, wide)
    except Exception as e:
        print(f"计算失败：{e}")
        return 1
    fac = fac[(fac.index >= seg_start) & (fac.index <= seg_end)]
    card = scorecard(fac, wide, cost_bps=args.cost_bps)
    comp = compare_baselines(fac, wide, seg_start, seg_end, cost_bps=args.cost_bps)
    pct = percentile_of(card["IC均值"], null_doc)
    print(scorecard_text(card))
    print(baselines_text(comp))
    if pct is None:
        print("全库百分位：未生成（先跑 tools/backtest/run_null.py 生成 benchmarks/is_null.json）")
    else:
        print(f"全库百分位：{pct['percentile']}%（共 {pct['n']} 条可跑经典因子）")
    # 存档：results/ 里一份时间戳 JSON（原始产物；登记表是索引）
    os.makedirs("results", exist_ok=True)
    now = datetime.now()
    path = f"results/{seg}_{now:%Y%m%d_%H%M%S}_{now.microsecond // 1000:03d}.json"
    n = 1
    while os.path.exists(path):
        path = f"results/{seg}_{now:%Y%m%d_%H%M%S}_{now.microsecond // 1000:03d}_{n}.json"
        n += 1
    record = {"公式": formula, "数据段": seg, "统计区间": [seg_start, seg_end],
              "生成时间": now.isoformat(timespec="seconds"),
              "成本bps": args.cost_bps, "成绩单": card,
              "基线对照": comp, "全库百分位": pct}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2, default=float)
    print(f"成绩单已存：{path}")
    if not args.no_register:
        notes = args.notes or ""
        if seg == "holdout":
            notes = (notes + f"；holdout 原因：{args.holdout_reason}" if notes
                     else f"holdout 原因：{args.holdout_reason}")
        status_default = {"is": "IS 已验证", "oos": "OOS 已验证",
                          "holdout": "holdout 已跑"}[seg]
        reg = {
            "hypothesis_id": args.hypothesis,
            "version": args.version,
            "formula": formula,
            "formula_hash": formula_hash(formula),
            "segment": seg,
            "scorecard_v2": card,
            "baselines": comp,
            "percentile": pct,
            "cost_bps": args.cost_bps,
            "data_version": data_version(wide),
            "created_at": now.isoformat(timespec="seconds"),
            "created_by": _created_by(),
            "direction": args.direction or "",
            "holding_period": args.holding_period,
            "params": args.params or "",
            "oos_rule": args.oos_rule or "",
            "is_end": SEGMENTS["is"][2],
            "status": args.status or status_default,
            "notes": notes,
        }
        added, _ = append_registry(reg)
        if added:
            print(f"登记：已追加 research/registry.jsonl（{args.hypothesis or ''}{' ' if args.hypothesis else ''}{args.version or ''}）")
        else:
            print("登记：同一公式 + 同一段已登记过，本次不重复记")
        try:
            import render_registry
            render_registry.render()
            print("登记视图：research/experiment_registry.md 已重新生成")
        except Exception as e:
            print(f"登记视图生成失败（登记本身已写）：{e}")
    if args.report:
        out = subprocess.run([sys.executable, os.path.join(ROOT, "report.py"),
                              formula, "--segment", seg],
                             capture_output=False)
        if out.returncode != 0:
            print("报告生成失败（成绩单与登记不受影响）")
            return 1
    return 0

def main():
    ap = argparse.ArgumentParser(description="回测统一入口：成绩单 v2 + 基线对照 + 登记")
    ap.add_argument("--segment", choices=list(SEGMENTS), default="is")
    ap.add_argument("--formula", default=None)
    ap.add_argument("--batch", default=None)
    ap.add_argument("--hypothesis", default=None)
    ap.add_argument("--version", default=None)
    ap.add_argument("--direction", default=None)
    ap.add_argument("--holding-period", default="20日")
    ap.add_argument("--params", default=None)
    ap.add_argument("--oos-rule", default=None)
    ap.add_argument("--status", default=None)
    ap.add_argument("--notes", default=None)
    ap.add_argument("--cost-bps", type=int, default=COST_BPS)
    ap.add_argument("--allow-holdout", action="store_true")
    ap.add_argument("--holdout-reason", default=None)
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--no-register", action="store_true")
    args = ap.parse_args()
    if args.segment == "holdout" and not args.allow_holdout:
        print("holdout 段封存：须加 --allow-holdout 并用 --holdout-reason 写明原因")
        return 2
    if args.segment == "holdout" and not (args.holdout_reason or "").strip():
        print("holdout 段封存：须用 --holdout-reason 写明原因")
        return 2
    if bool(args.formula) == bool(args.batch):
        print("须且只能给 --formula 或 --batch 其中一个")
        return 2
    runs = ([{"hypothesis": args.hypothesis, "version": args.version, "formula": args.formula}]
            if args.formula else parse_batch(args.batch))
    if not runs:
        print("没有可跑的公式")
        return 2
    # 先过白名单再加载数据：公式写错不用等数据加载完才报错
    for run in runs:
        ok, bad = engine.check_whitelist(run["formula"])
        if not ok:
            print(f"公式错误：{'、'.join(bad)} 不在清单内：{run['formula']}")
            return 1
    load_end, seg_start, seg_end, seg_name = SEGMENTS[args.segment]
    engine.LOAD_END = load_end
    try:
        wide = engine.load_wide()
    except Exception as e:
        print(f"数据加载失败：{e}")
        return 1
    null_doc = load_null()
    code = 0
    for run in runs:
        a = argparse.Namespace(**{**vars(args),
                                  "hypothesis": run["hypothesis"] or args.hypothesis,
                                  "version": run["version"] or args.version})
        print(f"=== {seg_name} · {run['formula']} ===")
        rc = run_one(run["formula"], wide, args.segment, seg_start, seg_end,
                     seg_name, a, null_doc)
        code = code or rc
    return code

if __name__ == "__main__":
    raise SystemExit(main())
