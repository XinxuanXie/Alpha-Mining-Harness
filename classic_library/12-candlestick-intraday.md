# 十二、K线与日内形态

单日价格形态：影线、实体、区间位置与日内路径。构造以开高低收之间的相对关系为主。

- **C81 WQ#18 价差与开收相关**：`-1 * rank(ts_std(abs(close - open), 5) + (close - open) + ts_corr(close, open, 10))`
- **C105 WQ#54 日内力量比**：`(-1 * ((low - close) * open^5)) / ((low - high) * close^5)`（原文式）
- **C132 实体涨幅 KMID**：`(close - open) / open`，当日实体涨跌幅
- **C133 振幅 KLEN**：`(high - low) / open`，当日振幅
- **C134 实体占比 KMID2**：`(close - open) / (high - low)`，实体占振幅之比
- **C135 上影 KUP**：`(high - max(open, close)) / open`，上影线长度
- **C136 上影占比 KUP2**：`(high - max(open, close)) / (high - low)`，上影占振幅之比
- **C137 下影 KLOW**：`(min(open, close) - low) / open`，下影线长度
- **C138 下影占比 KLOW2**：`(min(open, close) - low) / (high - low)`，下影占振幅之比
- **C139 收盘偏移 KSFT**：`(2 * close - high - low) / open`，收盘相对区间中点偏移
- **C140 收盘偏移占比 KSFT2**：`(2 * close - high - low) / (high - low)`，同上按振幅归一
- **C141 开盘比 OPEN0**：`open / close`，当日开盘相对收盘
- **C142 最高比 HIGH0**：`high / close`，当日最高相对收盘
- **C143 最低比 LOW0**：`low / close`，当日最低相对收盘
- **C185 移动便利 EMV**：`((high + low) / 2 - delay((high + low) / 2, 1)) / (volume / (high - low))` 的 14 日均值（Arms 1989；程序自算），单位量推动的价格位移
- **C187 多头力量**：`high - EMA(close, 13)`（Elder 1993），最高价相对趋势均线的超出
