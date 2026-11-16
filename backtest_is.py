"""IS 段回测：输入一条因子公式，输出 15 项指标。只有数字，不做判定。
用法：python backtest_is.py "neg(close / delay(close, 20) - 1)"
指标在本文件内计算；公式求值由 engine.py 完成。结果除打印外，还存一份 JSON 到 results/ 目录。"""

import json
import os
import sys
from datetime import datetime

import numpy as np
import pandas as pd

import engine
from engine import MIN_STOCKS

# ============================================================
# 数据段（三个回测脚本唯一不同的地方）
# ============================================================
LOAD_END = "2016-12-31"
SEG_START, SEG_END = "2000-01-01", "2016-12-31"  # 指标统计哪一段的因子值
SEGMENT = "is"                                  # 本脚本的数据段名
JUDGE_H = 20  # 判定期限（日）

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
# 成绩单：15 项指标一次算齐（总判 5＋持有期 5＋分组 5）
# 只算不判：本节只产出数字，过不过门由调用方看数字决定
# ============================================================
def scorecard(factor, wide):
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
    return {
        "IC均值": m["IC均值"], "ICIR": m["ICIR"], "t值": m["t值"],
        "覆盖率": m["覆盖率"], "因子自相关": autocorr,
        "各持有期IC": m["各持有期IC"],
        "五组收益": q_avg, "分组单调性": mono,
        "多空价差": float(spread.mean()), "多空胜率": float((spread.dropna() > 0).mean()),
        "方向一致率": float((daily_ic > 0).mean()),
    }

def scorecard_text(sc):
    """成绩单的固定文本格式：只有数字，不含判定。"""
    def r(x, n=4):
        return None if x is None else round(x, n)
    lines = [
        f"20日IC {r(sc['IC均值'])}",
        f"ICIR {r(sc['ICIR'], 3)}",
        f"t值 {r(sc['t值'], 2)}",
        f"覆盖率 {r(sc['覆盖率'], 3)}",
        f"因子自相关 {r(sc['因子自相关'], 3)}",
        "持有期IC " + " ".join(f"{k}日 {r(v)}" for k, v in sc["各持有期IC"].items()),
        "五组收益% " + " ".join(str(round(x * 100, 2)) for x in sc["五组收益"]),
        f"分组单调性 {r(sc['分组单调性'], 2)}",
        f"多空价差% {round(sc['多空价差'] * 100, 2)}",
        f"多空胜率 {r(sc['多空胜率'], 3)}",
        f"方向一致率 {r(sc['方向一致率'], 3)}",
    ]
    return "\n".join(lines)



# ============================================================
# 主流程：公式（文字）→ 检查 → 求值 → 切段 → 算指标 → 打印并存档
# ============================================================
def main():
    if len(sys.argv) != 2:
        print('用法：python backtest_is.py "<公式>"')
        return 1
    formula = sys.argv[1]
    ok, bad = engine.check_whitelist(formula)
    if not ok:
        print("公式错误：" + "、".join(bad) + " 不在清单内")
        return 1
    engine.LOAD_END = LOAD_END
    wide = engine.load_wide()
    try:
        fac = engine.eval_formula(formula, wide)
        fac = fac[(fac.index >= SEG_START) & (fac.index <= SEG_END)]
        card = scorecard(fac, wide)
        print(scorecard_text(card))
        os.makedirs("results", exist_ok=True)
        now = datetime.now()
        path = f"results/{SEGMENT}_{now:%Y%m%d_%H%M%S}_{now.microsecond // 1000:03d}.json"
        n = 1
        while os.path.exists(path):
            path = f"results/{SEGMENT}_{now:%Y%m%d_%H%M%S}_{now.microsecond // 1000:03d}_{n}.json"
            n += 1
        record = {"公式": formula, "数据段": SEGMENT, "统计区间": [SEG_START, SEG_END],
                  "生成时间": datetime.now().isoformat(timespec="seconds"), "成绩单": card}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2, default=float)
        print(f"成绩单已存：{path}")
    except Exception as e:
        print(f"计算失败：{e}")
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
