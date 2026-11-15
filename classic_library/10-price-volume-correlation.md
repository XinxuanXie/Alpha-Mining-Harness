# 十、量价相关

价格与成交量之间的同步与背离关系。构造以价量相关与协方差、秩相关及其变化为主，多为复合构造。

符号约定：returns 为日收益率，adv{d} 为 d 日平均成交量，vw = (high + low + close) / 3（原文 WorldQuant 101 的 vwap 在本库的落地口径，本库无 vwap 字段），IndNeutralize 为行业内去均值，scale 为截面归一化，非整数窗口向下取整。本家族条目多出自 Kakushadze (2015) 公式化 Alpha，公式按原文记号。

- **C68 WQ#2 量价背离**：`-1 * ts_corr(rank(delta(log(volume), 2)), rank((close - open) / open), 6)`，量变化与日内收益的 6 日秩相关取负，经济意义：量价背离反映上涨缺乏成交确认，预示短期反转。
- **C69 WQ#3 开盘价量相关**：`-1 * ts_corr(rank(open), rank(volume), 10)`，经济意义：开盘价量负相关反映开盘需求疲弱，预示收益反转。
- **C71 WQ#6 开盘价量相关（原值）**：`-1 * ts_corr(open, volume, 10)`，经济意义：开盘价量同步性过高反映追涨过度，取负预示反转。
- **C76 WQ#13 价量秩协方差**：`-1 * rank(ts_cov(rank(close), rank(volume), 5))`，经济意义：价量协方差过高反映交易拥挤，预示截面反转。
- **C77 WQ#14 跌幅与价量相关**：`(-1 * rank(delta(returns, 3))) * ts_corr(open, volume, 10)`，经济意义：超跌且价量共振的股票存在承接买入迹象，预示反弹。
- **C78 WQ#15 高价量秩相关累积**：`-1 * ts_sum(rank(ts_corr(rank(high), rank(volume), 3)), 3)`，经济意义：高位价量相关累积过强反映买盘衰竭，预示反转。
- **C79 WQ#16 高价量协方差**：`-1 * rank(ts_cov(rank(high), rank(volume), 5))`，经济意义：高价区价量协方差过大反映冲高乏力，预示反转。
- **C85 WQ#22 高价量相关变化**：`-1 * (delta(ts_corr(high, volume, 5), 5) * rank(ts_std(close, 20)))`，经济意义：价量相关骤升伴随高波动，反映投机过热，预示反转。
- **C88 WQ#26 量价时序秩相关峰值**：`-1 * ts_max(ts_corr(ts_rank(volume, 5), ts_rank(high, 5), 5), 3)`，经济意义：量价时序相关峰值过高反映趋势拥挤，预示反转。
- **C89 WQ#28 量价低点校准**：`scale(ts_corr(adv20, low, 5) + ((high + low) / 2) - close)`，scale 为截面归一化（原文式），经济意义：价格在日内区间的位置与成交量配合，度量买卖力量对比，预示短期方向。
- **C97 WQ#40 高价波动×量价相关**：`(-1 * rank(ts_std(high, 10))) * ts_corr(high, volume, 10)`，经济意义：低波动下价量齐升反映稳健吸筹，预示收益延续。
- **C99 WQ#44 高价量秩相关**：`-1 * ts_corr(high, rank(volume), 5)`，经济意义：高价与放量同步出现反映追高拥挤，取负预示反转。
- **C100 WQ#45 均价×价量相关衰减**：`-1 * (rank(ts_mean(delay(close, 5), 20)) * ts_corr(close, volume, 2) * rank(ts_corr(ts_sum(close, 5), ts_sum(close, 20), 2)))`，经济意义：中期强势叠加短窗价量共振反映趋势过热，预示反转。
- **C109 WQ#61 典型价距低点 vs 量相关**：`(rank(vw - ts_min(vw, 16)) < rank(ts_corr(vw, adv180, 18))) ? 1 : 0` 取负（原文为布尔比较式），经济意义：价格位置与长期量价相关背离，预示均值回归。
- **C110 WQ#65 开盘混合价 vs 开盘距低点**：`(rank(ts_corr(open * 0.008 + vw * 0.992, ts_sum(adv60, 9), 6)) < rank(open - ts_min(open, 14))) ? -1 : 0`（原文式，权重按原文混合价），经济意义：开盘价脱离低点的幅度超过量价相关支撑时，预示反转。
- **C111 WQ#71 量价秩相关衰减**：`max(ts_rank(decay_linear(ts_corr(ts_rank(close, 3), ts_rank(adv180, 12), 18), 4), 16), ts_rank(decay_linear(rank((low + open) - 2 * vw)^2, 16), 4))`（原文式），经济意义：长期量价秩相关经衰减加权，度量趋势的成交确认程度，预示延续。
- **C112 WQ#72 中价量相关比率**：`rank(decay_linear(ts_corr((high + low) / 2, adv40, 9), 10)) / rank(decay_linear(ts_corr(ts_rank(vw, 4), ts_rank(volume, 19), 7), 3))`（原文式），经济意义：中价量相关相对典型价量相关的强弱，度量买盘确认的质量。
- **C113 WQ#74 收盘量相关 vs 混合价量秩相关**：`(rank(ts_corr(close, ts_sum(adv30, 37), 15)) < rank(ts_corr(rank(high * 0.026 + vw * 0.974), rank(volume), 11))) ? -1 : 0`（原文式），经济意义：收盘确认弱于高位量价相关时，预示上涨动能不足。
- **C114 WQ#75 典型价量相关 vs 低价量相关**：`(rank(ts_corr(vw, volume, 4)) < rank(ts_corr(rank(low), rank(adv50), 12))) ? 1 : 0`（原文式），经济意义：低价区量价相关强于典型价时，反映低位承接积极，预示反弹。
- **C115 WQ#77 中价偏离与中价量相关取小**：`min(rank(decay_linear(((high + low) / 2 + high) - (vw + high), 20)), rank(decay_linear(ts_corr((high + low) / 2, adv40, 3), 6)))`（原文式），经济意义：价格偏离与量价相关取弱，筛选有成交确认的趋势信号。
- **C116 WQ#78 低价混合量相关幂**：`rank(ts_corr(ts_sum(low * 0.352 + vw * 0.648, 20), ts_sum(adv40, 20), 7))^rank(ts_corr(rank(vw), rank(volume), 6))`（原文式），经济意义：低价量相关的幂次放大反映底部成交结构变化，预示方向转折。
- **C117 WQ#81 典型价量相关乘积**：`(rank(log(product(rank(rank(ts_corr(vw, ts_sum(adv10, 50), 8))^4), 15))) < rank(ts_corr(rank(vw), rank(volume), 5))) ? -1 : 0`（原文式），经济意义：长窗量价相关累积强于短窗时，反映趋势确认过度，预示反转。
- **C118 WQ#83 区间相对强弱×量**：`(rank(delay((high - low) / ts_mean(close, 5), 2)) * rank(rank(volume))) / (((high - low) / ts_mean(close, 5)) / (vw - close))`（原文式），经济意义：振幅与成交量的结构关系度量买卖压力不对称，预示短期方向。
- **C120 WQ#85 混合收盘量相关幂**：`rank(ts_corr(high * 0.877 + close * 0.123, adv30, 10))^rank(ts_corr(ts_rank((high + low) / 2, 4), ts_rank(volume, 10), 7))`（原文式），经济意义：量价相关的幂次结构反映趋势确认的非线性强度，预示延续性差异。
- **C121 WQ#86 收盘量相关 vs 典型价偏离**：`(ts_rank(ts_corr(close, ts_sum(adv20, 15), 6), 20) < rank((open + close) - (vw + open))) ? -1 : 0`（原文式），经济意义：量价相关弱于收盘偏离时，反映价格上涨缺乏成交支撑，预示反转。
- **C122 WQ#88 四价秩差与量相关取小**：`min(rank(decay_linear((rank(open) + rank(low)) - (rank(high) + rank(close)), 8)), ts_rank(decay_linear(ts_corr(ts_rank(close, 8), ts_rank(adv60, 21), 8), 7), 3))`（原文式），经济意义：四价秩差与量价相关取弱，度量价格形态中未经成交确认的偏离。
- **C124 WQ#92 均线形态与低价量相关取小**：`min(ts_rank(decay_linear(where((high + low) / 2 + close < low + open, 1, 0), 15), 19), ts_rank(decay_linear(ts_corr(rank(low), rank(adv30), 8), 7), 7))`（原文式），经济意义：弱势价格形态与低价量相关取弱，度量下行压力的成交确认程度。
- **C127 WQ#96 量价秩相关与收盘量峰值相关取大**：`max(ts_rank(decay_linear(ts_corr(rank(vw), rank(volume), 4), 4), 8), ts_rank(decay_linear(ts_argmax(ts_corr(ts_rank(close, 7), ts_rank(adv60, 4), 4), 13), 14), 13)) * -1`（原文式），经济意义：量价相关峰值时点与相关强度共同度量趋势成熟度，取负预示反转。
- **C128 WQ#98 典型价量相关衰减差**：`rank(decay_linear(ts_corr(vw, ts_sum(adv5, 26), 5), 7)) - rank(decay_linear(ts_rank(ts_argmin(ts_corr(rank(open), rank(adv15), 21), 9), 7), 8))`（原文式），经济意义：短窗量价相关与开盘量相关低点的相对位置，度量成交确认的边际变化。
- **C129 WQ#99 中价量和相关 vs 低价量相关**：`(rank(ts_corr(ts_sum((high + low) / 2, 20), ts_sum(adv60, 20), 9)) < rank(ts_corr(low, volume, 6))) ? -1 : 0`（原文式），经济意义：中价量相关弱于低价量相关时，反映承接集中于低位，预示反转。
- **C130 WQ#100 区间位置行业中性×量比**：`-(1.5 * scale(IndNeutralize(IndNeutralize(rank((((close - low) - (high - close)) / (high - low)) * volume), 子行业), 子行业)) - scale(IndNeutralize(ts_corr(close, rank(adv20), 5) - rank(ts_argmin(close, 30)), 子行业))) * (volume / adv20)`（原文 Alpha#100），经济意义：行业中性的区间位置与量比共同度量资金流强度，预示截面收益差异。
- **C159 价量相关 CORR**：`ts_corr(close, log(volume + 1), 20)`，价格与对数成交量相关，经济意义：价量同步上升反映买入意愿与价格趋势相互确认，预示延续。
- **C160 价量变化相关 CORD**：`ts_corr(close / delay(close, 1), log(volume / delay(volume, 1) + 1), 20)`，收益率与量变化率相关，经济意义：收益与成交量变化同步，反映信息冲击下交易意愿的共振强度。
