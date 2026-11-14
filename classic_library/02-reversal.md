# 二、反转

涨跌过度后的均值回归，含短期与长期两型。构造以区间收益取负、距高低点的回归与条件触发为主。

- **C01 短期反转**：`-(close / delay(close, 20) - 1)`，近 1 个月涨跌取负
- **C02 长期反转**：`-(close / delay(close, 756) - 1)`，近 3 年涨跌取负
- **C26 长期反转（剔除近一年）**：`-(delay(close, 252) / delay(close, 756) - 1)`，取 t-36 至 t-13 个月收益取负（De Bondt & Thaler 1985；OSAP: LRreversal）
- **C27 中期反转**：`-(delay(close, 273) / delay(close, 378) - 1)`，取 t-18 至 t-13 个月收益取负（De Bondt & Thaler 1985；OSAP: MRreversal）
- **C67 WQ#1 条件波动峰值时点**：`rank(ts_argmax(signed_power(where(returns < 0, ts_std(returns, 20), close), 2), 5)) - 0.5`，下跌时取波动、上涨时取价格，平方后取 5 日内峰值时点排序
- **C70 WQ#4 低价时序秩**：`-1 * ts_rank(rank(low), 9)`
- **C72 WQ#7 放量急跌反转**：`where(adv20 < volume, -1 * ts_rank(abs(delta(close, 7)), 60) * sign(delta(close, 7)), -1)`，放量时 7 日涨跌的时序秩取负
- **C74 WQ#9 趋势顺势**：`where(0 < ts_min(delta(close, 1), 5), delta(close, 1), where(ts_max(delta(close, 1), 5) < 0, delta(close, 1), -1 * delta(close, 1)))`，5 日同向时顺势、混合时反向
- **C75 WQ#12 量变价反**：`sign(delta(volume, 1)) * (-1 * delta(close, 1))`
- **C80 WQ#17 价格秩×加速度×量比**：`(-1 * rank(ts_rank(close, 10))) * rank(delta(delta(close, 1), 1)) * rank(ts_rank(volume / adv20, 5))`
- **C82 WQ#19 周反转×年动量**：`(-1 * sign((close - delay(close, 7)) + delta(close, 7))) * (1 + rank(1 + ts_sum(returns, 250)))`
- **C84 WQ#21 均线带状态**：`where(ts_mean(close, 8) + ts_std(close, 8) < ts_mean(close, 2), -1, where(ts_mean(close, 2) < ts_mean(close, 8) - ts_std(close, 8), 1, where(volume / adv20 >= 1, 1, -1)))`，2 日均线相对 8 日均线 ±1 倍标准差带的位置状态，结合量比记 ±1
- **C86 WQ#23 高位回落**：`where(ts_mean(high, 20) < high, -1 * delta(high, 2), 0)`，创 20 日均值上方新高时取负
- **C87 WQ#24 长趋势未动则反转**：`where(delta(ts_mean(close, 100), 100) / delay(close, 100) <= 0.05, -(close - ts_min(close, 100)), -delta(close, 3))`，100 日均线变化率不超过 5% 时取距低点幅度取负，否则取 3 日跌幅取负
- **C91 WQ#31 衰减反转组合**：`rank(rank(rank(decay_linear(-1 * rank(rank(delta(close, 10))), 10)))) + rank(-1 * delta(close, 3)) + sign(scale(ts_corr(adv20, low, 12)))`
- **C92 WQ#33 开收倒数差**：`rank(-1 * (1 - open / close))`，日内涨幅排序取负
- **C96 WQ#38 价格秩×开收比**：`(-1 * rank(ts_rank(close, 10))) * rank(close / open)`
- **C98 WQ#43 量比秩×周跌秩**：`ts_rank(volume / adv20, 20) * ts_rank(-1 * delta(close, 7), 8)`
- **C101 WQ#46 价格路径曲率**：`where(s > 0.25, -1, where(s < 0, 1, -delta(close, 1)))`，其中 s = ((delay(close, 20) - delay(close, 10)) / 10) - ((delay(close, 10) - close) / 10)，为前后两段 10 日斜率之差
- **C102 WQ#49 路径曲率·严阈值**：`where(s < -0.1, 1, -delta(close, 1))`，s 的定义同 C101（原文 Alpha#49）
- **C104 WQ#53 收盘位置变化**：`-1 * delta(((close - low) - (high - close)) / (close - low), 9)`，收盘在日内区间位置的 9 日变化取负
- **C107 WQ#57 距峰值衰减**：`-1 * ((close - vw) / decay_linear(rank(ts_argmax(close, 30)), 2))`，收盘偏离典型价、按距 30 日高点时点的衰减权重缩放
- **C108 WQ#60 区间位置量加权×峰值时点**：`-(2 * scale(rank(((close - low) - (high - close)) / (high - low) * volume)) - scale(rank(ts_argmax(close, 10))))`（原文式）
- **C119 WQ#84 典型价距高点幂变换**：`signed_power(ts_rank(vw - ts_max(vw, 15), 21), delta(close, 5))`（原文式）
- **C123 WQ#90 距高点×行业量低相关**：`(rank(close - ts_max(close, 5))^ts_rank(ts_corr(IndNeutralize(adv40, subindustry), low, 5), 3)) * -1`（原文式）
- **C125 WQ#94 典型价距低点幂**：`(rank(vw - ts_min(vw, 12))^ts_rank(ts_corr(ts_rank(vw, 20), ts_rank(adv60, 4), 18), 3)) * -1`（原文式）
- **C126 WQ#95 开盘距低点 vs 中价量相关幂**：`(rank(open - ts_min(open, 12)) < ts_rank(rank(ts_corr(ts_sum((high + low) / 2, 19), ts_sum(adv40, 19), 13))^5, 12)) ? 1 : 0`（原文式）
