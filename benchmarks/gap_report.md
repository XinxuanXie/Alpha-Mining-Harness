# 经典库可跑性缺口报告

由 `tools/backtest/extract_library.py` 生成；白名单校验，不接触数据。

共 200 条：白名单通过 127 条，排除 73 条。
其中 25 条靠本次 engine 修补解锁（`returns` 字段、`ts_quantile`/`ts_cov`/`min`/`max` 算子）。
白名单通过只代表公式写得合法，真正可跑与否以 `run_null.py` 在有数据的机器上的试算为准；
试算失败的条目会记进 `benchmarks/is_null.json` 的 excluded 栏。

## 排除条目（需重写，不硬凑）

| 编号 | 家族 | 公式原文 | 原因 |
|---|---|---|---|
| C22 | 一、动量 | `mean over 窗口对 (s, l) of sign(ts_mean(close, s) / ts_mean(close, l) - 1) * (close / delay(close, l) - 1)` | 语法错误：invalid syntax |
| C25 | 一、动量 | `where(上市月数处于截面最短五分位, delay(close, 21) / delay(close, 147) - 1, 缺失)` | 字段 上市月数处于截面最短五分位；字段 缺失 |
| C33 | 三、季节性 | `(ts_sum(月收益, 12) - 去年同月月收益) / 11` | 字段 去年同月月收益；字段 月收益 |
| C34 | 三、季节性 | `-mean(月收益, 过去第 2–5 年的非同月月份)` | 语法错误：invalid character '–' (U+2013) |
| C35 | 三、季节性 | `-mean(月收益, 过去第 6–10 年的非同月月份)` | 语法错误：invalid character '–' (U+2013) |
| C36 | 三、季节性 | `-mean(月收益, 过去第 11–15 年的非同月月份)` | 语法错误：invalid character '–' (U+2013) |
| C37 | 三、季节性 | `-mean(月收益, 过去第 16–20 年的非同月月份)` | 语法错误：invalid character '–' (U+2013) |
| C39 | 四、波动与风险 | `ts_corr(close / delay(close, 3) - 1, 市场三日收益, 1260) * ts_std(close / delay(close, 3) - 1, 1260) / ts_std(市场三日收益, 1260)` | 字段 市场三日收益 |
| C40 | 四、波动与风险 | `ts_beta(returns, 尾部冲击序列, 252)` | 字段 尾部冲击序列 |
| C41 | 四、波动与风险 | `neg(过去 1 年日收益对市场收益回归的残差标准差)` | 语法错误：invalid syntax. Perhaps you forgot a comma? |
| C43 | 四、波动与风险 | `ts_mean((r - ts_mean(r, 60)) * power(mktret - ts_mean(mktret, 60), 2), 60) / (ts_std(r, 60) * power(ts_std(mktret, 60), 2))` | 字段 r |
| C44 | 四、波动与风险 | `ts_mean((r - ts_mean(r, 252)) * power(mktret - ts_mean(mktret, 252), 2), 252) / (ts_std(r, 252) * power(ts_std(mktret, 252), 2))` | 字段 r |
| C46 | 四、波动与风险 | `neg(过去 1 个月 CAPM 残差的偏度)` | 语法错误：invalid syntax. Perhaps you forgot a comma? |
| C50 | 五、流动性与换手 | `ts_slope(月成交量, 60) / ts_mean(月成交量, 60)` | 算子 ts_slope；字段 月成交量 |
| C51 | 五、流动性与换手 | `neg(过去 36 个月月成交量的标准差)` | 语法错误：invalid syntax. Perhaps you forgot a comma? |
| C52 | 五、流动性与换手 | `neg(过去 36 个月换手率的标准差)` | 语法错误：invalid syntax. Perhaps you forgot a comma? |
| C53 | 五、流动性与换手 | `neg(过去 36 个月换手率标准差 / 均值)` | 语法错误：invalid syntax. Perhaps you forgot a comma? |
| C54 | 五、流动性与换手 | `2 * (exp(α) - 1) / (1 + exp(α))` | 算子 exp；字段 α |
| C59 | 六、规模与价格水平 | `neg(个股在面板中首次出现以来的月数)` | 字段 个股在面板中首次出现以来的月数 |
| C60 | 八、信息扩散与行业领先滞后 | `1 - R²(受限模型) / R²(完整模型)` | 语法错误：invalid character '²' (U+00B2) |
| C61 | 八、信息扩散与行业领先滞后 | `(1*\|β1\| + 2*\|β2\| + 3*\|β3\| + 4*\|β4\|) / (\|β0\| + \|β1\| + \|β2\| + \|β3\| + \|β4\|)` | 语法错误：invalid syntax |
| C62 | 八、信息扩散与行业领先滞后 | `(1*\|t1\| + 2*\|t2\| + 3*\|t3\| + 4*\|t4\|) / (\|t0\| + \|t1\| + \|t2\| + \|t3\| + \|t4\|)` | 语法错误：invalid syntax |
| C63 | 八、信息扩散与行业领先滞后 | `赋给行业内其余股票的同业市值前 30% 股票上期平均收益 = sector_big_mean(delay(returns, 1))` | 语法错误：invalid syntax |
| C72 | 二、反转 | `where(adv20 < volume, -1 * ts_rank(abs(delta(close, 7)), 60) * sign(delta(close, 7)), -1)` | 字段 adv20 |
| C80 | 二、反转 | `(-1 * rank(ts_rank(close, 10))) * rank(delta(delta(close, 1), 1)) * rank(ts_rank(volume / adv20, 5))` | 字段 adv20 |
| C84 | 二、反转 | `where(ts_mean(close, 8) + ts_std(close, 8) < ts_mean(close, 2), -1, where(ts_mean(close, 2) < ts_mean(close, 8) - ts_std(close, 8), 1, where(volume / adv20 >= 1, 1, -1)))` | 字段 adv20 |
| C89 | 十、量价相关 | `scale(ts_corr(adv20, low, 5) + ((high + low) / 2) - close)` | 算子 scale；字段 adv20 |
| C91 | 二、反转 | `rank(rank(rank(decay_linear(-1 * rank(rank(delta(close, 10))), 10)))) + rank(-1 * delta(close, 3)) + sign(scale(ts_corr(adv20, low, 12)))` | 算子 scale；字段 adv20；算子 decay_linear |
| C98 | 二、反转 | `ts_rank(volume / adv20, 20) * ts_rank(-1 * delta(close, 7), 8)` | 字段 adv20 |
| C101 | 二、反转 | `where(s > 0.25, -1, where(s < 0, 1, -delta(close, 1)))` | 字段 s |
| C102 | 二、反转 | `where(s < -0.1, 1, -delta(close, 1))` | 字段 s |
| C107 | 二、反转 | `-1 * ((close - vw) / decay_linear(rank(ts_argmax(close, 30)), 2))` | 算子 decay_linear；字段 vw |
| C108 | 二、反转 | `-(2 * scale(rank(((close - low) - (high - close)) / (high - low) * volume)) - scale(rank(ts_argmax(close, 10))))` | 算子 scale |
| C109 | 十、量价相关 | `(rank(vw - ts_min(vw, 16)) < rank(ts_corr(vw, adv180, 18))) ? 1 : 0` | 语法错误：invalid syntax |
| C110 | 十、量价相关 | `(rank(ts_corr(open * 0.008 + vw * 0.992, ts_sum(adv60, 9), 6)) < rank(open - ts_min(open, 14))) ? -1 : 0` | 语法错误：invalid syntax |
| C111 | 十、量价相关 | `max(ts_rank(decay_linear(ts_corr(ts_rank(close, 3), ts_rank(adv180, 12), 18), 4), 16), ts_rank(decay_linear(rank((low + open) - 2 * vw)^2, 16), 4))` | 算子 decay_linear；字段 adv180；字段 vw |
| C112 | 十、量价相关 | `rank(decay_linear(ts_corr((high + low) / 2, adv40, 9), 10)) / rank(decay_linear(ts_corr(ts_rank(vw, 4), ts_rank(volume, 19), 7), 3))` | 算子 decay_linear；字段 adv40；字段 vw |
| C113 | 十、量价相关 | `(rank(ts_corr(close, ts_sum(adv30, 37), 15)) < rank(ts_corr(rank(high * 0.026 + vw * 0.974), rank(volume), 11))) ? -1 : 0` | 语法错误：invalid syntax |
| C114 | 十、量价相关 | `(rank(ts_corr(vw, volume, 4)) < rank(ts_corr(rank(low), rank(adv50), 12))) ? 1 : 0` | 语法错误：invalid syntax |
| C115 | 十、量价相关 | `min(rank(decay_linear(((high + low) / 2 + high) - (vw + high), 20)), rank(decay_linear(ts_corr((high + low) / 2, adv40, 3), 6)))` | 算子 decay_linear；字段 adv40；字段 vw |
| C116 | 十、量价相关 | `rank(ts_corr(ts_sum(low * 0.352 + vw * 0.648, 20), ts_sum(adv40, 20), 7))^rank(ts_corr(rank(vw), rank(volume), 6))` | 字段 adv40；字段 vw |
| C117 | 十、量价相关 | `(rank(log(product(rank(rank(ts_corr(vw, ts_sum(adv10, 50), 8))^4), 15))) < rank(ts_corr(rank(vw), rank(volume), 5))) ? -1 : 0` | 语法错误：invalid syntax |
| C118 | 十、量价相关 | `(rank(delay((high - low) / ts_mean(close, 5), 2)) * rank(rank(volume))) / (((high - low) / ts_mean(close, 5)) / (vw - close))` | 字段 vw |
| C119 | 二、反转 | `signed_power(ts_rank(vw - ts_max(vw, 15), 21), delta(close, 5))` | 字段 vw |
| C120 | 十、量价相关 | `rank(ts_corr(high * 0.877 + close * 0.123, adv30, 10))^rank(ts_corr(ts_rank((high + low) / 2, 4), ts_rank(volume, 10), 7))` | 字段 adv30 |
| C121 | 十、量价相关 | `(ts_rank(ts_corr(close, ts_sum(adv20, 15), 6), 20) < rank((open + close) - (vw + open))) ? -1 : 0` | 语法错误：invalid syntax |
| C122 | 十、量价相关 | `min(rank(decay_linear((rank(open) + rank(low)) - (rank(high) + rank(close)), 8)), ts_rank(decay_linear(ts_corr(ts_rank(close, 8), ts_rank(adv60, 21), 8), 7), 3))` | 算子 decay_linear；字段 adv60 |
| C123 | 二、反转 | `(rank(close - ts_max(close, 5))^ts_rank(ts_corr(IndNeutralize(adv40, subindustry), low, 5), 3)) * -1` | 算子 IndNeutralize；字段 adv40；字段 subindustry |
| C124 | 十、量价相关 | `min(ts_rank(decay_linear(where((high + low) / 2 + close < low + open, 1, 0), 15), 19), ts_rank(decay_linear(ts_corr(rank(low), rank(adv30), 8), 7), 7))` | 算子 decay_linear；字段 adv30 |
| C125 | 二、反转 | `(rank(vw - ts_min(vw, 12))^ts_rank(ts_corr(ts_rank(vw, 20), ts_rank(adv60, 4), 18), 3)) * -1` | 字段 vw；字段 adv60 |
| C126 | 二、反转 | `(rank(open - ts_min(open, 12)) < ts_rank(rank(ts_corr(ts_sum((high + low) / 2, 19), ts_sum(adv40, 19), 13))^5, 12)) ? 1 : 0` | 语法错误：invalid syntax |
| C127 | 十、量价相关 | `max(ts_rank(decay_linear(ts_corr(rank(vw), rank(volume), 4), 4), 8), ts_rank(decay_linear(ts_argmax(ts_corr(ts_rank(close, 7), ts_rank(adv60, 4), 4), 13), 14), 13)) * -1` | 算子 decay_linear；字段 vw；字段 adv60 |
| C128 | 十、量价相关 | `rank(decay_linear(ts_corr(vw, ts_sum(adv5, 26), 5), 7)) - rank(decay_linear(ts_rank(ts_argmin(ts_corr(rank(open), rank(adv15), 21), 9), 7), 8))` | 算子 decay_linear；字段 vw；字段 adv5；字段 adv15 |
| C129 | 十、量价相关 | `(rank(ts_corr(ts_sum((high + low) / 2, 20), ts_sum(adv60, 20), 9)) < rank(ts_corr(low, volume, 6))) ? -1 : 0` | 语法错误：invalid syntax |
| C130 | 十、量价相关 | `-(1.5 * scale(IndNeutralize(IndNeutralize(rank((((close - low) - (high - close)) / (high - low)) * volume), 子行业), 子行业)) - scale(IndNeutralize(ts_corr(close, rank(adv20), 5) - rank(ts_argmin(close, 30)), 子行业))) * (volume / adv20)` | 字段 adv20；算子 scale；算子 IndNeutralize；字段 子行业 |
| C147 | 十一、趋势与均线 | `ts_slope(close, 20) / close` | 算子 ts_slope |
| C148 | 十一、趋势与均线 | `power(ts_corr(close, 时间序号, 20), 2)` | 字段 时间序号 |
| C149 | 十一、趋势与均线 | `(close - ts_fitted(close, 时间序号, 20)) / close` | 算子 ts_fitted；字段 时间序号 |
| C173 | 十三、摆动与超买超卖 | `100 - 100 / (1 + ts_mean(上涨日涨幅, 14) / ts_mean(下跌日跌幅, 14))` | 字段 上涨日涨幅；字段 下跌日跌幅 |
| C174 | 十一、趋势与均线 | `(EMA(close, 12) - EMA(close, 26)) - EMA(EMA(close, 12) - EMA(close, 26), 9)` | 算子 EMA |
| C176 | 十三、摆动与超买超卖 | `((high + low + close) / 3 - ts_mean(典型价, 20)) / (0.015 * ts_mean(abs(典型价 - ts_mean(典型价, 20)), 20))` | 字段 典型价 |
| C177 | 十三、摆动与超买超卖 | `100 - 100 / (1 + ts_sum(典型价上涨日资金流, 14) / ts_sum(典型价下跌日资金流, 14))` | 字段 典型价上涨日资金流；字段 典型价下跌日资金流 |
| C178 | 五、流动性与换手 | `(OBV - delay(OBV, 20)) / ts_sum(volume, 20)` | 字段 OBV |
| C180 | 十一、趋势与均线 | `EMA(DX, 14)` | 算子 EMA；字段 DX |
| C181 | 十三、摆动与超买超卖 | `(ts_sum(EMA(振幅, 9) / EMA(EMA(振幅, 9), 9), 25))` | 算子 EMA；字段 振幅 |
| C182 | 十一、趋势与均线 | `(25 - 距 25 日最高的天数) / 25 * 100 - (25 - 距 25 日最低的天数) / 25 * 100` | 语法错误：invalid syntax. Perhaps you forgot a comma? |
| C187 | 十二、K线与日内形态 | `high - EMA(close, 13)` | 算子 EMA |
| C188 | 十三、摆动与超买超卖 | `100 * (4 * A7 + 2 * A14 + A28) / 7` | 字段 A28；字段 A7；字段 A14 |
| C189 | 十三、摆动与超买超卖 | `(ts_sum(上涨幅, 14) - ts_sum(下跌幅, 14)) / (ts_sum(上涨幅, 14) + ts_sum(下跌幅, 14)) * 100` | 字段 上涨幅；字段 下跌幅 |
| C190 | 十一、趋势与均线 | `EMA(EMA(EMA(close, 15), 15), 15) / delay(EMA(EMA(EMA(close, 15), 15), 15), 1) - 1` | 算子 EMA |
| C191 | 十一、趋势与均线 | `ts_sum(high - delay(low, 1), 14) / ts_sum(真实波幅, 14) - ts_sum(delay(high, 1) - low, 14) / ts_sum(真实波幅, 14)` | 字段 真实波幅 |
| C196 | 四、波动与风险 | `sqrt(σ²_隔夜 + k * σ²_开收 + (1 - k) * σ²_RS)` | 语法错误：invalid character '²' (U+00B2) |
| C199 | 四、波动与风险 | `(已实现方差 - 双幂变差) / 已实现方差` | 字段 已实现方差；字段 双幂变差 |

## 靠 engine 修补解锁的条目

以下条目在旧 engine 下跑不了（缺 `returns` 字段或新算子），本次修补后白名单通过：

- C67 WQ#1 条件波动峰值时点（uses returns）
- C73 WQ#8 开盘收益乘积动量（uses returns）
- C76 WQ#13 价量秩协方差（uses ts_cov）
- C77 WQ#14 跌幅与价量相关（uses returns）
- C79 WQ#16 高价量协方差（uses ts_cov）
- C82 WQ#19 周反转×年动量（uses returns）
- C93 WQ#34 波动比×日跌（uses returns）
- C94 WQ#35 量秩×区间秩×收益秩（uses returns）
- C103 WQ#52 低点抬升×长动量×量秩（uses returns）
- C135 上影 KUP（uses max）
- C136 上影占比 KUP2（uses max）
- C137 下影 KLOW（uses min）
- C138 下影占比 KLOW2（uses min）
- C152 上分位 QTLU（uses ts_quantile）
- C153 下分位 QTLD（uses ts_quantile）
- C164 上涨幅度占比 SUMP（uses max）
- C165 下跌幅度占比 SUMN（uses max）
- C166 净变动占比 SUMD（uses max）
- C169 量加权波动比 WVMA（uses returns）
- C170 放量占比 VSUMP（uses max）
- C171 缩量占比 VSUMN（uses max）
- C172 净量变占比 VSUMD（uses max）
- C179 平均真实波幅比 ATR（uses max）
- C197 Roll 隐含价差（uses returns, uses ts_cov, uses max）
- C198 下行半方差占比（uses returns, uses min）

## 排除原因统计

同一条目有多个原因时各计一次；数量最大的几组是下一批修库时最值得先动的：

- 12 条：语法错误：invalid syntax
- 10 条：字段 vw
- 9 条：算子 decay_linear
- 7 条：字段 adv20
- 6 条：语法错误：invalid syntax. Perhaps you forgot a comma?
- 5 条：算子 EMA
- 4 条：语法错误：invalid character '–' (U+2013)
- 4 条：算子 scale
- 4 条：字段 adv40
- 3 条：字段 adv60
- 2 条：字段 r
- 2 条：算子 ts_slope
- 2 条：语法错误：invalid character '²' (U+00B2)
- 2 条：字段 s
- 2 条：字段 adv30
- 2 条：算子 IndNeutralize
- 2 条：字段 时间序号
- 1 条：字段 上市月数处于截面最短五分位
- 1 条：字段 缺失
- 1 条：字段 去年同月月收益
- 1 条：字段 月收益
- 1 条：字段 市场三日收益
- 1 条：字段 尾部冲击序列
- 1 条：字段 月成交量
- 1 条：算子 exp
- 1 条：字段 α
- 1 条：字段 个股在面板中首次出现以来的月数
- 1 条：字段 adv180
- 1 条：字段 subindustry
- 1 条：字段 adv5
- 1 条：字段 adv15
- 1 条：字段 子行业
- 1 条：算子 ts_fitted
- 1 条：字段 上涨日涨幅
- 1 条：字段 下跌日跌幅
- 1 条：字段 典型价
- 1 条：字段 典型价上涨日资金流
- 1 条：字段 典型价下跌日资金流
- 1 条：字段 OBV
- 1 条：字段 DX
- 1 条：字段 振幅
- 1 条：字段 A28
- 1 条：字段 A7
- 1 条：字段 A14
- 1 条：字段 上涨幅
- 1 条：字段 下跌幅
- 1 条：字段 真实波幅
- 1 条：字段 已实现方差
- 1 条：字段 双幂变差

## 已知库内容错误（待修，与可跑性无关）

- C140：库中 `C140 = 2·C134−1` 的关系式是错的。第 4 轮复核的正确关系：close>open 时 `C140 = 2(C134+C138)−1`，且 `C135−C137 = −C139`。
- C41：库原文是文字描述（`neg(过去 1 年日收益对市场收益回归的残差标准差)`），不是可算公式；
  基线集里暂用 `neg(ts_std(resid_ret, 252))` 作为可算近似（252 日残差标准差取负），见 `benchmarks/baselines.json` 的注记。
