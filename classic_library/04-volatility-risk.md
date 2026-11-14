# 四、波动与风险

波动、偏度、贝塔等风险特征与收益的关系，主体为低风险占优。构造以滚动波动、回归贝塔、残差统计与 OHLC 波动估计量为主。

- **C08 低波动**：`neg(ts_std(close / delay(close, 1) - 1, 60))`
- **C09 彩票 MAX**：`neg(ts_max(close / delay(close, 1) - 1, 20))`，近月单日最大涨幅取负
- **C10 低贝塔**：`neg(ts_corr(close / delay(close, 1) - 1, mktret, 252) * ts_std(close / delay(close, 1) - 1, 252) / ts_std(mktret, 252))`，252 日贝塔取负
- **C38 市场贝塔·5 年**：`ts_beta(close / delay(close, 1) - 1, mktret, 1260)`，窗口 5 年，与 C10 的区别在窗口（Fama & MacBeth 1973；OSAP: Beta）
- **C39 FP 贝塔**：以三日重叠收益计算的相关×波动比，`ts_corr(close / delay(close, 3) - 1, 市场三日收益, 1260) * ts_std(close / delay(close, 3) - 1, 1260) / ts_std(市场三日收益, 1260)`，市场三日收益为程序自算量（Frazzini & Pedersen 2014；OSAP: BetaFP）
- **C40 尾部风险贝塔**：`ts_beta(returns, 尾部冲击序列, 252)`，尾部冲击序列为每日截面收益 5% 分位以下股票的平均收益（程序自算）（Kelly & Jiang 2014；OSAP: BetaTailRisk）
- **C41 特质波动·1 年 CAPM**：`neg(过去 1 年日收益对市场收益回归的残差标准差)`，残差序列为程序预计算量（Ali, Hwang & Trombley 2003；OSAP: IdioVolAHT）
- **C42 已实现波动·1 月**：`neg(ts_std(close / delay(close, 1) - 1, 21))`，与 C08 的区别在窗口与总波动口径（Ang et al. 2006；OSAP: RealizedVol）
- **C43 协偏度·月频**：`ts_mean((r - ts_mean(r, 60)) * power(mktret - ts_mean(mktret, 60), 2), 60) / (ts_std(r, 60) * power(ts_std(mktret, 60), 2))`，月频口径、窗口 60 个月，r 为个股月收益（程序自算）（Harvey & Siddique 2000；OSAP: Coskewness）
- **C44 协偏度·日频**：`ts_mean((r - ts_mean(r, 252)) * power(mktret - ts_mean(mktret, 252), 2), 252) / (ts_std(r, 252) * power(ts_std(mktret, 252), 2))`，日频口径、窗口 1 年，r 为个股日收益（程序自算）（Ang, Chen & Xing 2006；OSAP: CoskewACX）
- **C45 收益偏度**：`neg(ts_skew(close / delay(close, 1) - 1, 21))`，近月日收益偏度取负（Bali, Engle & Murray 2015；OSAP: ReturnSkew）
- **C46 特质偏度·CAPM**：`neg(过去 1 个月 CAPM 残差的偏度)`，残差序列为程序预计算量（Bali, Engle & Murray 2015；OSAP: ReturnSkewCAPM）
- **C93 WQ#34 波动比×日跌**：`rank((1 - rank(ts_std(returns, 2) / ts_std(returns, 5))) + (1 - rank(delta(close, 1))))`
- **C146 价格离散 STD**：`ts_std(close, 20) / close`，价格标准差按现价归一
- **C169 量加权波动比 WVMA**：`ts_std(abs(returns) * volume, 20) / ts_mean(abs(returns) * volume, 20)`，量加权涨跌幅的变异系数
- **C179 平均真实波幅比 ATR**：`ts_mean(max(high - low, abs(high - delay(close, 1)), abs(low - delay(close, 1))), 14) / close`（Wilder 1978）
- **C193 Parkinson 波动**：`sqrt(ts_mean(power(log(high / low), 2), 20) / (4 * log(2)))`，仅用日内高低极值估计波动（Parkinson 1980）
- **C194 Garman-Klass 波动**：`sqrt(ts_mean(0.5 * power(log(high / low), 2) - (2 * log(2) - 1) * power(log(close / open), 2), 20))`，高低极值与开收结合（Garman & Klass 1980）
- **C195 Rogers-Satchell 波动**：`sqrt(ts_mean(log(high / close) * log(high / open) + log(low / close) * log(low / open), 20))`，允许漂移的极值估计（Rogers & Satchell 1991）
- **C196 Yang-Zhang 波动**：`sqrt(σ²_隔夜 + k * σ²_开收 + (1 - k) * σ²_RS)`，σ²_RS 为 Rogers-Satchell 方差（C195 同口径）、k = 0.34 / (1.34 + (n + 1) / (n - 1))、n = 20（Yang & Zhang 2000；程序自算）
- **C197 Roll 隐含价差**：`2 * sqrt(max(-ts_cov(returns, delay(returns, 1), 60), 0))`，由收益负自协方差反推有效价差（Roll 1984；程序自算）
- **C198 下行半方差占比**：`ts_sum(power(min(returns, 0), 2), 20) / ts_sum(power(returns, 2), 20)`，下行波动占总波动之比（程序自算）
- **C199 跳跃方差占比**：`(已实现方差 - 双幂变差) / 已实现方差`，20 日口径（Barndorff-Nielsen & Shephard 2004；双幂变差为程序自算）
- **C200 隔夜方差占比**：`ts_sum(power(open / delay(close, 1) - 1, 2), 20) / ts_sum(power(close / delay(close, 1) - 1, 2), 20)`，隔夜波动占全日波动之比（程序自算）
