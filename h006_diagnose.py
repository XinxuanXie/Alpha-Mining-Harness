#!/usr/bin/env python3
"""H006 v1 识别诊断（IS 段 2000-2016）：只算不判，结论按下面预先写死的通过线给出。

背景：H006 v1 在 IS 上 20 日 IC 0.0156（ICIR 0.202、60 日 IC 0.0235），没过 0.02 的线，
辩论已判应弃。诊断要回答的是：这个正号是不是真的条件动量，还是下面三样东西混出来的。
  A1：公式可分解为 F = 2g*r - g，其中 -g 是一条 C41 腿（多低 IVol、空高 IVol）。
  A3：高 IVol 组形成期收益离散度更大，组内赢家减输家价差在零假设下也会更大。
  A5：原文 Table 10 的 0.73 里赢家端只占 +0.22、输家端占 -0.51，七成在空头端。

三项诊断（全部只用 IS 段，与 backtest_is.py 同一套标签与 IC 口径）：
  D1 控制 C19/C41：把 H006 v1 的截面秩逐日对 C19 秩、IVol 秩做回归，取残差再算 20 日 IC。
  D2 分组 IC：在高 IVol 三分位组内与低 IVol 三分位组内，分别算动量腿的 20 日 IC 并比较。
  D3 赢家端/输家端拆分：在高 IVol 组内，赢家减中段与中段减输家的未来收益各占多少。

预先写死的通过线（跑之前定好，跑完不改）：
  D0 自检：算出的 H006 v1 20 日 IC 应约等于 0.0156（误差 ±0.001）；对不上就停下查原因。
  D1：残差 20 日 IC >= 0.01 为通过（信号在控制 C19+C41 后还剩东西）；< 0.01 为不通过。
  D2：IC_high - IC_low > 0.005 为通过（动量在高 IVol 组内确实更强）；<= 0.005 为不通过。
  D3：输家端占比 > 70% 则主张收窄为「高 IVol 输家延续」，不是对称的条件动量；
      赢家端占比 >= 30% 则对称主张保留。
  总结论：D1 与 D2 同时通过，才值得考虑 OOS；否则 H006 v1 关闭。D3 只改主张，不改总结论。

用法（在仓库根目录跑）：python3 h006_diagnose.py
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

# ============================================================
# 常量：公式（与辩论记录 H006.md 入池版逐字一致）、数据段、通过线
# ============================================================
F_H006_V1 = ("(gt(rank(delay(ts_mean(ivol20, 252), 21)), 0.667)"
             " - gt(0.333, rank(delay(ts_mean(ivol20, 252), 21))))"
             " * (2 * rank(delay(close, 21) / delay(close, 147) - 1) - 1)")
F_MOM = "delay(close, 21) / delay(close, 147) - 1"          # C19 动量片段
F_IVOL = "delay(ts_mean(ivol20, 252), 21)"                   # 门变量：252 日平均 ivol20，滞后 21 日
F_GATE = ("gt(rank(delay(ts_mean(ivol20, 252), 21)), 0.667)"
          " - gt(0.333, rank(delay(ts_mean(ivol20, 252), 21)))")

SEG_START, SEG_END = "2000-01-01", "2016-12-31"
H = 20  # 判定期限（日），与 backtest_is.py 的 JUDGE_H 一致

D0_EXPECTED_IC = 0.0156   # 已知的 H006 v1 IS 20 日 IC，用于自检
D0_TOL = 0.001
D1_BAR = 0.01
D2_BAR = 0.005
D3_LOSER_SHARE = 0.70


def _pct_rank(df):
    """截面百分比秩 (名次-1)/(股票数-1)，与 engine._rank_cs 同口径。"""
    n = df.notna().sum(axis=1)
    r = df.rank(axis=1, method="average")
    out = (r - 1).div(n - 1, axis=0)
    return out.where(n >= 2)


def _ic_mean(factor, label):
    """20 日标签下的日 IC 均值；算不出返回 None。"""
    s = bi._ic_series(factor, label)
    return None if len(s) == 0 else float(s.mean())


def _ic_series_mean_and_t(factor, label):
    s = bi._ic_series(factor, label)
    if len(s) < 2:
        return None, None, 0
    return float(s.mean()), float(s.mean() / (s.std() / np.sqrt(len(s)))), len(s)


def residualize(fac_rank, ctrl_ranks):
    """逐日把 fac_rank 对控制变量秩做截面 OLS 回归，返回残差宽表。

    fac_rank：待剥离的因子截面秩；ctrl_ranks：控制变量秩的列表。
    每天只用三者都不缺失的股票；有效股票不足 30 只的当天记缺失。
    """
    resid = pd.DataFrame(np.nan, index=fac_rank.index, columns=fac_rank.columns)
    for date, y in fac_rank.iterrows():
        mask = y.notna()
        for c in ctrl_ranks:
            mask &= c.loc[date].notna()
        if mask.sum() < 30:
            continue
        yv = y[mask].to_numpy()
        X = np.column_stack([np.ones(mask.sum())] +
                            [c.loc[date][mask].to_numpy() for c in ctrl_ranks])
        beta, *_ = np.linalg.lstsq(X, yv, rcond=None)
        resid.loc[date, mask] = yv - X @ beta
    return resid


def main():
    print("H006 v1 识别诊断（IS 段 2000-2016）")
    print("通过线：D1 残差 IC >= 0.01；D2 组间 IC 差 > 0.005；D3 输家端占比 > 70% 则主张收窄")
    engine.LOAD_END = "2016-12-31"
    wide = engine.load_wide()
    close = wide["close"]
    label = bi._label(close, H)

    fac = engine.eval_formula(F_H006_V1, wide)
    mom = engine.eval_formula(F_MOM, wide)
    ivol = engine.eval_formula(F_IVOL, wide)
    gate = engine.eval_formula(F_GATE, wide)
    for name, df in (("H006 v1", fac), ("动量腿", mom), ("IVol 门变量", ivol), ("门 g", gate)):
        df = df[(df.index >= SEG_START) & (df.index <= SEG_END)]
        if name == "H006 v1":
            fac = df
        elif name == "动量腿":
            mom = df
        elif name == "IVol 门变量":
            ivol = df
        else:
            gate = df

    # ---------- D0 自检 ----------
    ic_v1, t_v1, n_v1 = _ic_series_mean_and_t(fac, label)
    print(f"\n[D0 自检] H006 v1 20 日 IC = {ic_v1:.4f}（t = {t_v1:.2f}，{n_v1} 天）")
    if ic_v1 is None or abs(ic_v1 - D0_EXPECTED_IC) > D0_TOL:
        print(f"D0 未通过：期望约 {D0_EXPECTED_IC}，算出 {ic_v1}。先停下查原因，不要往下看结论。")
        return 1

    fac_rank = _pct_rank(fac)
    mom_rank = _pct_rank(mom)
    ivol_rank = _pct_rank(ivol)

    # ---------- D1：控制 C19 + IVol 水平 ----------
    ic_mom, _, _ = _ic_series_mean_and_t(mom, label)
    ic_neg_ivol, _, _ = _ic_series_mean_and_t(-ivol_rank, label)
    ic_gate, _, _ = _ic_series_mean_and_t(gate, label)
    # 因子与两个控制轴的截面秩相关（逐日算再平均）
    def _rank_corr(a, b):
        vals = []
        for i in range(a.shape[0]):
            m = a.iloc[i].notna() & b.iloc[i].notna()
            if m.sum() >= 30:
                vals.append(np.corrcoef(a.iloc[i][m], b.iloc[i][m])[0, 1])
        return float(np.nanmean(vals)) if vals else None
    corr_mom = _rank_corr(fac_rank, mom_rank)
    corr_ivol = _rank_corr(fac_rank, ivol_rank)
    resid = residualize(fac_rank, [mom_rank, ivol_rank])
    ic_resid, t_resid, n_resid = _ic_series_mean_and_t(resid, label)
    # 回归 R^2（逐日平均）：两个控制轴解释了 v1 的多少
    r2s = []
    for i in range(fac_rank.shape[0]):
        y = fac_rank.iloc[i]
        mask = y.notna() & mom_rank.iloc[i].notna() & ivol_rank.iloc[i].notna()
        if mask.sum() >= 30:
            yv = y[mask].to_numpy()
            X = np.column_stack([np.ones(mask.sum()), mom_rank.iloc[i][mask].to_numpy(),
                                 ivol_rank.iloc[i][mask].to_numpy()])
            beta, *_ = np.linalg.lstsq(X, yv, rcond=None)
            pred = X @ beta
            ss_res = float(((yv - pred) ** 2).sum())
            ss_tot = float(((yv - yv.mean()) ** 2).sum())
            if ss_tot > 0:
                r2s.append(1 - ss_res / ss_tot)
    r2_mean = float(np.mean(r2s)) if r2s else None
    d1_pass = ic_resid is not None and ic_resid >= D1_BAR
    print("\n[D1 控制 C19/C41]")
    print(f"  C19 动量腿单跑 20 日 IC = {ic_mom:.4f}")
    print(f"  neg IVol 秩单跑 20 日 IC = {ic_neg_ivol:.4f}（即 C41 腿的方向）")
    print(f"  门 g 单跑 20 日 IC = {ic_gate:.4f}")
    print(f"  H006 v1 与 C19 秩的截面秩相关 = {corr_mom:.3f}；与 IVol 秩 = {corr_ivol:.3f}")
    print(f"  两控制轴解释 v1 的 R^2（逐日平均）= {r2_mean:.3f}")
    print(f"  残差 20 日 IC = {ic_resid:.4f}（t = {t_resid:.2f}，{n_resid} 天）")
    print(f"  D1 结论：{'通过' if d1_pass else '不通过'}（线 {D1_BAR}）")

    # ---------- D2：分组 IC ----------
    high = (gate == 1.0)
    low = (gate == -1.0)
    ic_high, _, n_high = _ic_series_mean_and_t(mom.where(high), label)
    ic_low, _, n_low = _ic_series_mean_and_t(mom.where(low), label)
    diff = (ic_high - ic_low) if (ic_high is not None and ic_low is not None) else None
    # 支撑数：两组内形成期收益的离散度之比（A3 机制的量级）
    disp_ratio = []
    for i in range(mom.shape[0]):
        mh = mom.iloc[i][high.iloc[i]].dropna()
        ml = mom.iloc[i][low.iloc[i]].dropna()
        if len(mh) >= 30 and len(ml) >= 30:
            sh, sl = float(mh.std()), float(ml.std())
            if sl > 0:
                disp_ratio.append(sh / sl)
    disp_mean = float(np.mean(disp_ratio)) if disp_ratio else None
    d2_pass = diff is not None and diff > D2_BAR
    print("\n[D2 分组 IC：动量腿在高/低 IVol 组内]")
    print(f"  高 IVol 组内动量 20 日 IC = {ic_high:.4f}（{n_high} 天）")
    print(f"  低 IVol 组内动量 20 日 IC = {ic_low:.4f}（{n_low} 天）")
    print(f"  组间差 IC_high - IC_low = {diff:.4f}")
    print(f"  形成期收益离散度之比 高/低（逐日平均）= {disp_mean:.3f}")
    print(f"  D2 结论：{'通过' if d2_pass else '不通过'}（线 {D2_BAR}）")

    # ---------- D3：赢家端/输家端拆分 ----------
    mom_pct_high = mom.where(high).rank(axis=1, pct=True)
    lab = label.where(fac.notna())
    top = lab.where(mom_pct_high > 0.8).mean(axis=1)
    mid = lab.where((mom_pct_high > 0.4) & (mom_pct_high <= 0.6)).mean(axis=1)
    bot = lab.where(mom_pct_high <= 0.2).mean(axis=1)
    win = float((top - mid).mean())
    lose = float((mid - bot).mean())
    total = win + lose
    win_share = win / total if total else None
    lose_share = lose / total if total else None
    narrow = lose_share is not None and lose_share > D3_LOSER_SHARE
    print("\n[D3 赢家端/输家端拆分：高 IVol 组内，20 日标签收益]")
    print(f"  赢家减中段 = {win * 100:.3f}%/20 日；中段减输家 = {lose * 100:.3f}%/20 日")
    print(f"  赢家端占比 = {win_share * 100:.0f}%；输家端占比 = {lose_share * 100:.0f}%")
    print(f"  D3 结论：{'主张收窄为「高 IVol 输家延续」' if narrow else '对称主张保留'}"
          f"（输家端占比线 {D3_LOSER_SHARE * 100:.0f}%）")

    # ---------- 总结论 ----------
    overall = d1_pass and d2_pass
    print("\n[总结论]")
    print(f"  D1 {'通过' if d1_pass else '不通过'}；D2 {'通过' if d2_pass else '不通过'}；"
          f"D3 {'主张收窄' if narrow else '对称主张保留'}")
    print("  " + ("D1 与 D2 同时通过：H006 v1 值得考虑 OOS（须研究者明确确认）。"
                  if overall else
                  "H006 v1 关闭：D1 或 D2 未通过，IS 正号由 C19/C41 腿或离散度机械通道解释。"))

    os.makedirs("results", exist_ok=True)
    now = datetime.now()
    path = f"results/h006_diagnose_{now:%Y%m%d_%H%M%S}.json"
    record = {
        "公式": F_H006_V1, "数据段": "is", "统计区间": [SEG_START, SEG_END],
        "生成时间": now.isoformat(timespec="seconds"),
        "通过线": {"D1_残差IC": D1_BAR, "D2_组间IC差": D2_BAR, "D3_输家端占比": D3_LOSER_SHARE},
        "D0_自检_IC": ic_v1,
        "D1": {"IC_C19": ic_mom, "IC_negIVol秩": ic_neg_ivol, "IC_门g": ic_gate,
               "秩相关_C19": corr_mom, "秩相关_IVol": corr_ivol, "R2_均值": r2_mean,
               "残差IC": ic_resid, "残差t值": t_resid, "通过": d1_pass},
        "D2": {"IC_high": ic_high, "IC_low": ic_low, "组间差": diff,
               "离散度之比": disp_mean, "通过": d2_pass},
        "D3": {"赢家减中段": win, "中段减输家": lose,
               "赢家端占比": win_share, "输家端占比": lose_share, "主张收窄": narrow},
        "总结论_OOS值得考虑": overall,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2, default=float)
    print(f"\n结果已存：{path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
