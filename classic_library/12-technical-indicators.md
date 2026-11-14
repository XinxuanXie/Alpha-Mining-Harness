# 十二、技术指标

经典技术指标 20 条，涵盖趋势、摆动与量能三类，构造互不相同。

- **C173 相对强弱 RSI**：`100 - 100 / (1 + ts_mean(上涨日涨幅, 14) / ts_mean(下跌日跌幅, 14))`（Wilder 1978），方向按原文以高值为强
- **C174 MACD 柱**：`(EMA(close, 12) - EMA(close, 26)) - EMA(EMA(close, 12) - EMA(close, 26), 9)`，快慢均线差与其信号线之差（Appel 1979；EMA 为程序自算）
- **C175 布林位置 %B**：`(close - (ts_mean(close, 20) - 2 * ts_std(close, 20))) / (4 * ts_std(close, 20))`，价格在布林带内的位置（Bollinger 1992）
- **C176 商品通道 CCI**：`((high + low + close) / 3 - ts_mean(典型价, 20)) / (0.015 * ts_mean(abs(典型价 - ts_mean(典型价, 20)), 20))`（Lambert 1980；典型价与平均绝对偏差为程序自算）
- **C177 资金流量 MFI**：`100 - 100 / (1 + ts_sum(典型价上涨日资金流, 14) / ts_sum(典型价下跌日资金流, 14))`，资金流为典型价乘以成交量（Quong & Soudack 1989）
- **C178 能量潮斜率 OBV**：OBV 为涨日加量、跌日减量的累积量，取其 20 日变化除以 20 日量和（Granville 1963；OBV 为程序自算）
- **C179 平均真实波幅比 ATR**：`ts_mean(max(high - low, abs(high - delay(close, 1)), abs(low - delay(close, 1))), 14) / close`（Wilder 1978）
- **C180 趋势强度 ADX**：由 +DI 与 -DI（方向 movement 按真实波幅归一）之差的平滑值构成，衡量趋势强度不分方向（Wilder 1978；程序自算）
- **C181 质量指数**：`(ts_sum(EMA(振幅, 9) / EMA(EMA(振幅, 9), 9), 25))`，振幅单/双重平滑之比的 25 日和，高值预示趋势反转（Dorsey 1992；EMA 为程序自算）
- **C182 Aroon 振荡器**：`(25 - 距 25 日最高的天数) / 25 * 100 - (25 - 距 25 日最低的天数) / 25 * 100`（Chande 1994），高低点新鲜程度之差
- **C183 去趋势价格 DPO**：`close - delay(ts_mean(close, 20), 11)`，价格减去前移半周期均线（程序自算）
- **C184 蔡金资金流**：`ts_sum(((close - low) - (high - close)) / (high - low) * volume, 20) / ts_sum(volume, 20)`（Chaikin 1985），收盘位置加权的量占比
- **C185 移动便利 EMV**：`((high + low) / 2 - delay((high + low) / 2, 1)) / (volume / (high - low))` 的 14 日均值（Arms 1989；程序自算），单位量推动的价格位移
- **C186 强力指数**：`(close - delay(close, 1)) * volume` 的 13 日指数平滑（Elder 1993；程序自算）
- **C187 多头力量**：`high - EMA(close, 13)`（Elder 1993），最高价相对趋势均线的超出
- **C188 终极振荡器**：7、14、28 三窗口买压（close 减去 min(low，前收））与真实区间之比按 4、2、1 加权（Williams 1985；程序自算）
- **C189 钱德动量 CMO**：`(ts_sum(上涨幅, 14) - ts_sum(下跌幅, 14)) / (ts_sum(上涨幅, 14) + ts_sum(下跌幅, 14)) * 100`（Chande 1994）
- **C190 三重平滑变化率 TRIX**：close 三重指数平滑后的单日变化率（Hutson 1984；程序自算）
- **C191 涡旋差**：`ts_sum(high - delay(low, 1), 14) / ts_sum(真实波幅, 14) - ts_sum(delay(high, 1) - low, 14) / ts_sum(真实波幅, 14)`（Botes & Siepman 2010；程序自算），正负涡旋之差
- **C192 趋势效率比**：`(close - delay(close, 10)) / ts_sum(abs(delta(close, 1)), 10)`，净位移占总路径之比（Kaufman 1995）
