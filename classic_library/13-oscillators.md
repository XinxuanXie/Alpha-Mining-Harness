# 十三、摆动与超买超卖

把涨跌幅或价格位置压入有界区间的摆动指标，度量超买超卖程度。构造以上涨与下跌幅度和之比、区间位置及其平滑为主。

- **C106 WQ#55 随机位置与量相关**：`-1 * ts_corr(rank((close - ts_min(low, 12)) / (ts_max(high, 12) - ts_min(low, 12))), rank(volume), 6)`
- **C155 随机值 RSV**：`(close - ts_min(low, 20)) / (ts_max(high, 20) - ts_min(low, 20))`，收盘在窗口高低区间的位置
- **C164 上涨幅度占比 SUMP**：`ts_sum(max(delta(close, 1), 0), 20) / ts_sum(abs(delta(close, 1)), 20)`，涨幅占总变动之比
- **C165 下跌幅度占比 SUMN**：`ts_sum(max(-delta(close, 1), 0), 20) / ts_sum(abs(delta(close, 1)), 20)`，跌幅占总变动之比
- **C166 净变动占比 SUMD**：`(ts_sum(max(delta(close, 1), 0), 20) - ts_sum(max(-delta(close, 1), 0), 20)) / ts_sum(abs(delta(close, 1)), 20)`，涨幅与跌幅之差占总变动之比
- **C173 相对强弱 RSI**：`100 - 100 / (1 + ts_mean(上涨日涨幅, 14) / ts_mean(下跌日跌幅, 14))`（Wilder 1978），方向按原文以高值为强
- **C175 布林位置 %B**：`(close - (ts_mean(close, 20) - 2 * ts_std(close, 20))) / (4 * ts_std(close, 20))`，价格在布林带内的位置（Bollinger 1992）
- **C176 商品通道 CCI**：`((high + low + close) / 3 - ts_mean(典型价, 20)) / (0.015 * ts_mean(abs(典型价 - ts_mean(典型价, 20)), 20))`（Lambert 1980；典型价与平均绝对偏差为程序自算）
- **C177 资金流量 MFI**：`100 - 100 / (1 + ts_sum(典型价上涨日资金流, 14) / ts_sum(典型价下跌日资金流, 14))`，资金流为典型价乘以成交量（Quong & Soudack 1989）
- **C181 质量指数**：`(ts_sum(EMA(振幅, 9) / EMA(EMA(振幅, 9), 9), 25))`，振幅单/双重平滑之比的 25 日和，高值预示趋势反转（Dorsey 1992；EMA 为程序自算）
- **C188 终极振荡器**：`100 * (4 * A7 + 2 * A14 + A28) / 7`，其中 A_N = ts_sum(买压, N) / ts_sum(真实区间, N)，买压 = close - min(low, delay(close, 1))，真实区间 = max(high, delay(close, 1)) - min(low, delay(close, 1))（Williams 1985；程序自算）
- **C189 钱德动量 CMO**：`(ts_sum(上涨幅, 14) - ts_sum(下跌幅, 14)) / (ts_sum(上涨幅, 14) + ts_sum(下跌幅, 14)) * 100`（Chande 1994）
