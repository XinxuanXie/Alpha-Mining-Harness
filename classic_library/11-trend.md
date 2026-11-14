# 十一、趋势与均线

价格相对自身均线与趋势线的位置和强度。构造以均线比、趋势回归（斜率、拟合度、残差）、高低点出现时点与趋势强度指标为主。

- **C145 均线比 MA**：`ts_mean(close, 20) / close`，均线相对现价
- **C147 趋势斜率 BETA**：`ts_slope(close, 20) / close`，价格对时间线性回归斜率（程序自算）
- **C148 趋势拟合 RSQR**：`power(ts_corr(close, 时间序号, 20), 2)`，价格对时间序号线性回归的 R²（程序自算），趋势线性程度
- **C149 趋势残差 RESI**：`(close - ts_fitted(close, 时间序号, 20)) / close`，价格对时间序号线性回归的当期残差按现价归一（程序自算），偏离趋势的程度
- **C156 距高点天数 IMAX**：`ts_argmax(high, 20) / 20`，距窗口最高价出现的天数占比
- **C157 距低点天数 IMIN**：`ts_argmin(low, 20) / 20`，距窗口最低价出现的天数占比
- **C158 高低点时差 IMXD**：`(ts_argmax(high, 20) - ts_argmin(low, 20)) / 20`，最高与最低出现时点之差
- **C174 MACD 柱**：`(EMA(close, 12) - EMA(close, 26)) - EMA(EMA(close, 12) - EMA(close, 26), 9)`，快慢均线差与其信号线之差（Appel 1979；EMA 为程序自算）
- **C180 趋势强度 ADX**：`EMA(DX, 14)`，其中 +DI = 100 * EMA(+DM, 14) / EMA(真实波幅, 14)、-DI 同理、DX = 100 * |+DI - -DI| / (+DI + -DI)，DM 为方向 movement（Wilder 1978；程序自算）
- **C182 Aroon 振荡器**：`(25 - 距 25 日最高的天数) / 25 * 100 - (25 - 距 25 日最低的天数) / 25 * 100`（Chande 1994），高低点新鲜程度之差
- **C183 去趋势价格 DPO**：`close - delay(ts_mean(close, 20), 11)`，价格减去前移半周期均线（程序自算）
- **C190 三重平滑变化率 TRIX**：`EMA(EMA(EMA(close, 15), 15), 15) / delay(EMA(EMA(EMA(close, 15), 15), 15), 1) - 1`，三重指数平滑后的单日变化率（Hutson 1984；EMA 为程序自算）
- **C191 涡旋差**：`ts_sum(high - delay(low, 1), 14) / ts_sum(真实波幅, 14) - ts_sum(delay(high, 1) - low, 14) / ts_sum(真实波幅, 14)`（Botes & Siepman 2010；程序自算），正负涡旋之差
- **C192 趋势效率比**：`(close - delay(close, 10)) / ts_sum(abs(delta(close, 1)), 10)`，净位移占总路径之比（Kaufman 1995）
