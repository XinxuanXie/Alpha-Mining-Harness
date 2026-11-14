# 十、量价相关

价格与成交量之间的同步与背离关系。构造以价量相关与协方差、秩相关及其变化为主，多为复合构造。

符号约定：returns 为日收益率，adv{d} 为 d 日平均成交量，vw = (high + low + close) / 3（原文 WorldQuant 101 的 vwap 在本库的落地口径，本库无 vwap 字段），IndNeutralize 为行业内去均值，scale 为截面归一化，非整数窗口向下取整。本家族条目多出自 Kakushadze (2015) 公式化 Alpha，公式按原文记号。

- **C68 WQ#2 量价背离**：`-1 * ts_corr(rank(delta(log(volume), 2)), rank((close - open) / open), 6)`，量变化与日内收益的 6 日秩相关取负
- **C69 WQ#3 开盘价量相关**：`-1 * ts_corr(rank(open), rank(volume), 10)`
- **C71 WQ#6 开盘价量相关（原值）**：`-1 * ts_corr(open, volume, 10)`
- **C76 WQ#13 价量秩协方差**：`-1 * rank(ts_cov(rank(close), rank(volume), 5))`
- **C77 WQ#14 跌幅与价量相关**：`(-1 * rank(delta(returns, 3))) * ts_corr(open, volume, 10)`
- **C78 WQ#15 高价量秩相关累积**：`-1 * ts_sum(rank(ts_corr(rank(high), rank(volume), 3)), 3)`
- **C79 WQ#16 高价量协方差**：`-1 * rank(ts_cov(rank(high), rank(volume), 5))`
- **C85 WQ#22 高价量相关变化**：`-1 * (delta(ts_corr(high, volume, 5), 5) * rank(ts_std(close, 20)))`
- **C88 WQ#26 量价时序秩相关峰值**：`-1 * ts_max(ts_corr(ts_rank(volume, 5), ts_rank(high, 5), 5), 3)`
- **C89 WQ#28 量价低点校准**：`scale(ts_corr(adv20, low, 5) + ((high + low) / 2) - close)`，scale 为截面归一化（原文式）
- **C97 WQ#40 高价波动×量价相关**：`(-1 * rank(ts_std(high, 10))) * ts_corr(high, volume, 10)`
- **C99 WQ#44 高价量秩相关**：`-1 * ts_corr(high, rank(volume), 5)`
- **C100 WQ#45 均价×价量相关衰减**：`-1 * (rank(ts_mean(delay(close, 5), 20)) * ts_corr(close, volume, 2) * rank(ts_corr(ts_sum(close, 5), ts_sum(close, 20), 2)))`
- **C109 WQ#61 典型价距低点 vs 量相关**：`(rank(vw - ts_min(vw, 16)) < rank(ts_corr(vw, adv180, 18))) ? 1 : 0` 取负（原文为布尔比较式）
- **C110 WQ#65 开盘混合价 vs 开盘距低点**：`(rank(ts_corr(open * 0.008 + vw * 0.992, ts_sum(adv60, 9), 6)) < rank(open - ts_min(open, 14))) ? -1 : 0`（原文式，权重按原文混合价）
- **C111 WQ#71 量价秩相关衰减**：`max(ts_rank(decay_linear(ts_corr(ts_rank(close, 3), ts_rank(adv180, 12), 18), 4), 16), ts_rank(decay_linear(rank((low + open) - 2 * vw)^2, 16), 4))`（原文式）
- **C112 WQ#72 中价量相关比率**：`rank(decay_linear(ts_corr((high + low) / 2, adv40, 9), 10)) / rank(decay_linear(ts_corr(ts_rank(vw, 4), ts_rank(volume, 19), 7), 3))`（原文式）
- **C113 WQ#74 收盘量相关 vs 混合价量秩相关**：`(rank(ts_corr(close, ts_sum(adv30, 37), 15)) < rank(ts_corr(rank(high * 0.026 + vw * 0.974), rank(volume), 11))) ? -1 : 0`（原文式）
- **C114 WQ#75 典型价量相关 vs 低价量相关**：`(rank(ts_corr(vw, volume, 4)) < rank(ts_corr(rank(low), rank(adv50), 12))) ? 1 : 0`（原文式）
- **C115 WQ#77 中价偏离与中价量相关取小**：`min(rank(decay_linear(((high + low) / 2 + high) - (vw + high), 20)), rank(decay_linear(ts_corr((high + low) / 2, adv40, 3), 6)))`（原文式）
- **C116 WQ#78 低价混合量相关幂**：`rank(ts_corr(ts_sum(low * 0.352 + vw * 0.648, 20), ts_sum(adv40, 20), 7))^rank(ts_corr(rank(vw), rank(volume), 6))`（原文式）
- **C117 WQ#81 典型价量相关乘积**：`(rank(log(product(rank(rank(ts_corr(vw, ts_sum(adv10, 50), 8))^4), 15))) < rank(ts_corr(rank(vw), rank(volume), 5))) ? -1 : 0`（原文式）
- **C118 WQ#83 区间相对强弱×量**：`(rank(delay((high - low) / ts_mean(close, 5), 2)) * rank(rank(volume))) / (((high - low) / ts_mean(close, 5)) / (vw - close))`（原文式）
- **C120 WQ#85 混合收盘量相关幂**：`rank(ts_corr(high * 0.877 + close * 0.123, adv30, 10))^rank(ts_corr(ts_rank((high + low) / 2, 4), ts_rank(volume, 10), 7))`（原文式）
- **C121 WQ#86 收盘量相关 vs 典型价偏离**：`(ts_rank(ts_corr(close, ts_sum(adv20, 15), 6), 20) < rank((open + close) - (vw + open))) ? -1 : 0`（原文式）
- **C122 WQ#88 四价秩差与量相关取小**：`min(rank(decay_linear((rank(open) + rank(low)) - (rank(high) + rank(close)), 8)), ts_rank(decay_linear(ts_corr(ts_rank(close, 8), ts_rank(adv60, 21), 8), 7), 3))`（原文式）
- **C124 WQ#92 均线形态与低价量相关取小**：`min(ts_rank(decay_linear(where((high + low) / 2 + close < low + open, 1, 0), 15), 19), ts_rank(decay_linear(ts_corr(rank(low), rank(adv30), 8), 7), 7))`（原文式）
- **C127 WQ#96 量价秩相关与收盘量峰值相关取大**：`max(ts_rank(decay_linear(ts_corr(rank(vw), rank(volume), 4), 4), 8), ts_rank(decay_linear(ts_argmax(ts_corr(ts_rank(close, 7), ts_rank(adv60, 4), 4), 13), 14), 13)) * -1`（原文式）
- **C128 WQ#98 典型价量相关衰减差**：`rank(decay_linear(ts_corr(vw, ts_sum(adv5, 26), 5), 7)) - rank(decay_linear(ts_rank(ts_argmin(ts_corr(rank(open), rank(adv15), 21), 9), 7), 8))`（原文式）
- **C129 WQ#99 中价量和相关 vs 低价量相关**：`(rank(ts_corr(ts_sum((high + low) / 2, 20), ts_sum(adv60, 20), 9)) < rank(ts_corr(low, volume, 6))) ? -1 : 0`（原文式）
- **C130 WQ#100 区间位置行业中性×量比**：`-(1.5 * scale(IndNeutralize(IndNeutralize(rank((((close - low) - (high - close)) / (high - low)) * volume), 子行业), 子行业)) - scale(IndNeutralize(ts_corr(close, rank(adv20), 5) - rank(ts_argmin(close, 30)), 子行业))) * (volume / adv20)`（原文 Alpha#100）
- **C159 价量相关 CORR**：`ts_corr(close, log(volume + 1), 20)`，价格与对数成交量相关
- **C160 价量变化相关 CORD**：`ts_corr(close / delay(close, 1), log(volume / delay(volume, 1) + 1), 20)`，收益率与量变化率相关
