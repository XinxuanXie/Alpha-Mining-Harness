"""单因子回测报告：输入公式与数据段，生成一个自包含 HTML 文件（零外部依赖，离线可看）。
形态参照 WorldQuant BRAIN 结果页：一张多空累计收益主图、一张成绩单表、一张分年表。
用法：python report.py "neg(close / delay(close, 20) - 1)" --segment train --out report.html
只呈现不判定：报告只有数字与图。公式求值由 engine.py 完成，指标由回测脚本完成。"""

import argparse
import html
import math
from datetime import datetime

import numpy as np
import pandas as pd

import engine
from backtest_train import daily_ic_series, quintile_daily, scorecard  # 指标函数与三个回测脚本同一份实现

# ============================================================
# 数据段（与回测脚本同一口径：加载止日、统计区间、段名）
# ============================================================
SEGMENTS = {
    "train": ("2016-12-31", "2000-01-01", "2016-12-31", "训练段"),
    "test": ("2020-04-30", "2017-01-01", "2019-12-31", "测试段"),
    "verify": ("2026-09-30", "2020-01-01", "2026-09-30", "验证段"),
}

# ============================================================
# 画图：把一条日序列画成 SVG 折线（静态内嵌，无 JS）
# ============================================================
def svg_curve(series, width=920, height=300):
    s = series.dropna()
    pad_l, pad_r, pad_t, pad_b = 56, 10, 10, 22
    pw, ph = width - pad_l - pad_r, height - pad_t - pad_b
    lo, hi = float(s.min()), float(s.max())
    if hi - lo < 1e-12:
        hi = lo + 1e-12
    xs = np.linspace(0, pw, len(s))
    ys = ph - (s.to_numpy() - lo) / (hi - lo) * ph
    pts = " ".join(f"{pad_l + x:.1f},{pad_t + y:.1f}" for x, y in zip(xs, ys))
    out = [f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">']
    for frac, val in ((0.0, hi), (0.5, (hi + lo) / 2), (1.0, lo)):
        y = pad_t + ph * frac
        out.append(f'<line x1="{pad_l}" y1="{y:.0f}" x2="{pad_l + pw}" y2="{y:.0f}" stroke="#ddd"/>')
        out.append(f'<text x="4" y="{y + 4:.0f}" font-size="11" fill="#888">{val:.2f}</text>')
    years = {}
    for i, d in enumerate(s.index):
        years.setdefault(d.year, i)
    for yr, i in years.items():
        x = pad_l + xs[i]
        out.append(f'<text x="{x:.0f}" y="{height - 6}" font-size="11" fill="#888">{yr}</text>')
    out.append(f'<polyline points="{pts}" fill="none" stroke="#2563eb" stroke-width="1.4"/>')
    out.append("</svg>")
    return "".join(out)

# ============================================================
# 主流程：公式 → 求值 → 成绩单＋多空收益序列＋分年表 → 拼 HTML
# ============================================================
def fmt(x, n=4):
    return "—" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.{n}f}"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("formula")
    ap.add_argument("--segment", choices=list(SEGMENTS), default="train")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    load_end, seg_start, seg_end, seg_name = SEGMENTS[a.segment]
    ok, bad = engine.check_whitelist(a.formula)
    if not ok:
        print("公式错误：" + "、".join(bad) + " 不在清单内")
        return 1
    engine.TRAIN_END = load_end
    wide = engine.load_wide()
    try:
        fac = engine.eval_formula(a.formula, wide)
    except Exception as e:
        print(f"计算失败：{e}")
        return 1
    fac = fac[(fac.index >= seg_start) & (fac.index <= seg_end)]
    sc = scorecard(fac, wide)

    # 多空组合日收益：当日五分位最高组减最低组（1 日收益），逐日复利成累计曲线
    qd1 = quintile_daily(fac, wide, h=1)
    ls = (qd1["Q5"] - qd1["Q1"]).dropna()
    curve = (1 + ls).cumprod()
    ann = float(ls.mean() * 252)
    sharpe = float(ls.mean() / ls.std() * math.sqrt(252)) if ls.std() else None
    mdd = float((curve / curve.cummax() - 1).min())

    # 分年表：与成绩单同一口径（20 日 IC 与 20 日多空价差）
    ic = daily_ic_series(fac, wide)
    qd = quintile_daily(fac, wide)
    spread = qd["Q5"] - qd["Q1"]
    year_rows = []
    for yr in sorted(set(ic.index.year)):
        y_ic = ic[ic.index.year == yr]
        y_sp = spread[spread.index.year == yr].dropna()
        sd = float(y_ic.std()) if len(y_ic) >= 2 else None
        t = float(y_ic.mean() / (sd / math.sqrt(len(y_ic)))) if sd else None
        year_rows.append(
            f"<tr><td>{yr}</td><td>{fmt(y_ic.mean())}</td>"
            f"<td>{fmt(float(y_ic.mean() / sd), 3) if sd else '—'}</td>"
            f"<td>{fmt(t, 2)}</td><td>{fmt(float(y_sp.mean()) * 100, 2)}%</td>"
            f"<td>{fmt(float((y_ic > 0).mean()), 3)}</td></tr>")

    q = sc["五组收益"]
    page = f"""<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8">
<title>因子回测报告 · {seg_name}</title>
<style>
body {{ font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif; margin: 32px auto; max-width: 980px; padding: 0 16px; color: #1a1a1a; }}
code {{ background: #f3f4f6; padding: 2px 6px; border-radius: 4px; font-size: 14px; }}
.meta {{ color: #666; font-size: 13px; margin-top: 6px; }}
.chips {{ display: flex; gap: 12px; margin: 18px 0 6px; flex-wrap: wrap; }}
.chip {{ border: 1px solid #e5e7eb; border-radius: 8px; padding: 8px 14px; font-size: 13px; color: #555; }}
.chip b {{ display: block; font-size: 18px; color: #1a1a1a; margin-top: 2px; }}
h2 {{ font-size: 16px; margin: 26px 0 10px; }}
table {{ border-collapse: collapse; font-size: 13.5px; }}
th, td {{ border: 1px solid #e5e7eb; padding: 5px 12px; text-align: right; }}
th {{ background: #f9fafb; }}
td:first-child, th:first-child {{ text-align: left; }}
</style></head><body>
<h1 style="font-size:19px">因子回测报告</h1>
<div><code>{html.escape(a.formula)}</code></div>
<div class="meta">{seg_name}（{seg_start} 至 {seg_end}）· {len(ic)} 个交易日 · 生成于 {datetime.now():%Y-%m-%d %H:%M}</div>
<div class="chips">
<div class="chip">20日IC<b>{fmt(sc['IC均值'])}</b></div>
<div class="chip">ICIR<b>{fmt(sc['ICIR'], 3)}</b></div>
<div class="chip">t值<b>{fmt(sc['t值'], 2)}</b></div>
<div class="chip">多空价差（20日）<b>{fmt(sc['多空价差'] * 100, 2)}%</b></div>
</div>

<h2>多空组合累计收益</h2>
<div class="meta">五分位最高组做多、最低组做空，等权，1 日收益逐日复利 · 年化 {fmt(ann * 100, 1)}% · Sharpe {fmt(sharpe, 2)} · 最大回撤 {fmt(mdd * 100, 1)}%</div>
{svg_curve(curve)}

<h2>成绩单</h2>
<table>
<tr><th colspan="2">总判（20日）</th><th colspan="2">持有期 IC</th><th colspan="2">分组（20日）</th></tr>
<tr><td>IC均值</td><td>{fmt(sc['IC均值'])}</td><td>1日</td><td>{fmt(sc['各持有期IC']['1'])}</td><td>五组收益%</td><td>{' / '.join(fmt(x * 100, 2) for x in q)}</td></tr>
<tr><td>ICIR</td><td>{fmt(sc['ICIR'], 3)}</td><td>5日</td><td>{fmt(sc['各持有期IC']['5'])}</td><td>分组单调性</td><td>{fmt(sc['分组单调性'], 2)}</td></tr>
<tr><td>t值</td><td>{fmt(sc['t值'], 2)}</td><td>10日</td><td>{fmt(sc['各持有期IC']['10'])}</td><td>多空价差</td><td>{fmt(sc['多空价差'] * 100, 2)}%</td></tr>
<tr><td>覆盖率</td><td>{fmt(sc['覆盖率'], 3)}</td><td>20日</td><td>{fmt(sc['各持有期IC']['20'])}</td><td>多空胜率</td><td>{fmt(sc['多空胜率'], 3)}</td></tr>
<tr><td>因子自相关</td><td>{fmt(sc['因子自相关'], 3)}</td><td>60日</td><td>{fmt(sc['各持有期IC']['60'])}</td><td>方向一致率</td><td>{fmt(sc['方向一致率'], 3)}</td></tr>
</table>

<h2>分年表</h2>
<table>
<tr><th>年份</th><th>IC</th><th>ICIR</th><th>t值</th><th>多空价差</th><th>方向一致率</th></tr>
{''.join(year_rows)}
</table>
</body></html>"""
    out = a.out or f"report_{a.segment}.html"
    with open(out, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"报告已生成：{out}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
