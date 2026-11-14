# 四、波动与风险

波动、偏度、贝塔等风险特征与收益的关系，主体为低风险占优。构造以滚动波动、回归贝塔与残差统计为主。

- **C08 低波动**：`neg(ts_std(close / delay(close, 1) - 1, 60))`
- **C09 彩票 MAX**：`neg(ts_max(close / delay(close, 1) - 1, 20))`，近月单日最大涨幅取负
- **C10 低贝塔**：`neg(ts_corr(close / delay(close, 1) - 1, mktret, 252) * ts_std(close / delay(close, 1) - 1, 252) / ts_std(mktret, 252))`，252 日贝塔取负
- **C38 市场贝塔·5 年**：`ts_beta(close / delay(close, 1) - 1, mktret, 1260)`，窗口 5 年，与 C10 的区别在窗口（Fama & MacBeth 1973；OSAP: Beta）
- **C39 FP 贝塔**：以三日重叠收益计算的相关×波动比，`ts_corr(close / delay(close, 3) - 1, 市场三日收益, 1260) * ts_std(close / delay(close, 3) - 1, 1260) / ts_std(市场三日收益, 1260)`，市场三日收益为程序自算量（Frazzini & Pedersen 2014；OSAP: BetaFP）
- **C40 尾部风险贝塔**：个股收益对全市场尾部冲击序列（截面 5% 分位以下收益）的回归系数，尾部序列为程序自算量（Kelly & Jiang 2014；OSAP: BetaTailRisk）
- **C41 特质波动·1 年 CAPM**：`neg(过去 1 年日收益对市场收益回归的残差标准差)`，残差序列为程序预计算量（Ali, Hwang & Trombley 2003；OSAP: IdioVolAHT）
- **C42 已实现波动·1 月**：`neg(ts_std(close / delay(close, 1) - 1, 21))`，与 C08 的区别在窗口与总波动口径（Ang et al. 2006；OSAP: RealizedVol）
- **C43 协偏度·月频**：过去 60 个月个股收益与市场收益平方的标准化协动（月频，程序自算）（Harvey & Siddique 2000；OSAP: Coskewness）
- **C44 协偏度·日频**：过去 1 年日频计算同一协偏度（程序自算）（Ang, Chen & Xing 2006；OSAP: CoskewACX）
- **C45 收益偏度**：`neg(ts_skew(close / delay(close, 1) - 1, 21))`，近月日收益偏度取负（Bali, Engle & Murray 2015；OSAP: ReturnSkew）
- **C46 特质偏度·CAPM**：`neg(过去 1 个月 CAPM 残差的偏度)`，残差序列为程序预计算量（Bali, Engle & Murray 2015；OSAP: ReturnSkewCAPM）
