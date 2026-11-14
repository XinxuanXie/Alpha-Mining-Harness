# 十三、OHLC 波动与价差估计量

用开高低收估计波动与有效价差的计量构造 8 条。作为因子使用时方向取负（低波动、低价差、低跳跃占优）。

本族为用 OHLC 构造的估计量，作为因子使用时方向取负（低波动、低价差、低跳跃占优）。

- **C193 Parkinson 波动**：`sqrt(ts_mean(power(log(high / low), 2), 20) / (4 * log(2)))`，仅用日内高低极值估计波动（Parkinson 1980）
- **C194 Garman-Klass 波动**：`sqrt(ts_mean(0.5 * power(log(high / low), 2) - (2 * log(2) - 1) * power(log(close / open), 2), 20))`，高低极值与开收结合（Garman & Klass 1980）
- **C195 Rogers-Satchell 波动**：`sqrt(ts_mean(log(high / close) * log(high / open) + log(low / close) * log(low / open), 20))`，允许漂移的极值估计（Rogers & Satchell 1991）
- **C196 Yang-Zhang 波动**：隔夜方差、开收方差与 Rogers-Satchell 方差按最优权重组合（Yang & Zhang 2000；程序自算）
- **C197 Roll 隐含价差**：`2 * sqrt(max(-ts_cov(returns, delay(returns, 1), 60), 0))`，由收益负自协方差反推有效价差（Roll 1984；程序自算）
- **C198 下行半方差占比**：`ts_sum(power(min(returns, 0), 2), 20) / ts_sum(power(returns, 2), 20)`，下行波动占总波动之比（程序自算）
- **C199 跳跃方差占比**：`(已实现方差 - 双幂变差) / 已实现方差`，20 日口径（Barndorff-Nielsen & Shephard 2004；双幂变差为程序自算）
- **C200 隔夜方差占比**：`ts_sum(power(open / delay(close, 1) - 1, 2), 20) / ts_sum(power(close / delay(close, 1) - 1, 2), 20)`，隔夜波动占全日波动之比（程序自算）
