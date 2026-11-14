# 经典因子库（全表）

共 200 条：C01–C17 为已入库经典（calc.py），C18–C66 为扩编候选（来源：Chen & Zimmermann Open Source Asset Pricing 信号文档，逐条核对，清单见 classic_library_candidates.md）；C67–C200 为量价公式化扩编（来源：Kakushadze 2015 WorldQuant 101 公式化 Alpha、Qlib Alpha158 特征、经典技术指标与 OHLC 估计量文献），全部条目只使用价格、成交量、市值、市场收益与行业字段及可自算量。
格式：编号 + 名称 + 公式 + 一句构成说明。月度口径按 21 个交易日/月、252 个交易日/年换算为日频公式；标注「程序自算」者为公式语言内不能直接表达、实现时由程序预计算的量。
方向以原论文为准；判定口径与现有系统一致。

## 一、动量

- **C03 中期动量**：`delay(close, 21) / delay(close, 252) - 1`，跳过最近 1 个月的过去一年收益
- **C04 接近 52 周高点**：`close / ts_max(close, 252)`
- **C05 趋势方向一致性**：`abs(close / delay(close, 252) - 1) * (ts_mean(gt(close / delay(close, 1) - 1, 0), 252) - ts_mean(gt(0, close / delay(close, 1) - 1), 252))`，年收益绝对值乘以上涨日占比与下跌日占比之差
- **C07 动量×低换手**：`(delay(close, 21) / delay(close, 252) - 1) * (1 - rank(ts_mean(volume * close / mktcap, 60)))`
- **C16 远端单月动量**：`delay(close, 232) / delay(close, 252) - 1`，约 11 个月前那一个月的收益
- **C17 行业动量**：`ts_sum(sector_mean(close / delay(close, 1) - 1), 126)`，所属行业半年累积收益
- **C18 3 月动量**：`delay(close, 21) / delay(close, 84) - 1`，形成期 3 个月、跳过最近 1 个月（Jegadeesh & Titman 1993）
- **C19 6 月动量**：`delay(close, 21) / delay(close, 147) - 1`，形成期 6 个月、跳过最近 1 个月（Jegadeesh & Titman 1993；OSAP: Mom6m）
- **C20 9 月动量**：`delay(close, 21) / delay(close, 210) - 1`，形成期 9 个月、跳过最近 1 个月（Jegadeesh & Titman 1993）
- **C21 中期动量（后半段）**：`delay(close, 147) / delay(close, 252) - 1`，只取形成期后半段 t-12 至 t-6 个月（Novy-Marx 2012；OSAP: IntMom）
- **C22 趋势因子**：多窗口均线比的组合（短/长均线比在多个尺度上同向才计分），原论文定义见 Han, Zhou & Zhu (2016)；OSAP: TrendFactor
- **C23 高量动量**：`(delay(close, 21) / delay(close, 147) - 1) * gt(rank(ts_mean(volume * close / mktcap, 60)), 0.67)`，6 月动量只在换手率最高组内赋值（Lee & Swaminathan 2000；OSAP: MomVol）
- **C24 动量×长期反转组合**：`gt(rank(delay(close, 21) / delay(close, 147) - 1), 0.8) * gt(rank(-(close / delay(close, 756) - 1)), 0.8) - gt(rank(-(delay(close, 21) / delay(close, 147) - 1)), 0.8) * gt(rank(close / delay(close, 756) - 1), 0.8)`，短期赢家且长期输家记 1、反之记 -1（Chan & Ko 2006；OSAP: MomRev）
- **C25 年轻股动量**：6 月动量（式同 C19），只在上市时长最短五分位股票内取值，上市时长为程序自算量（Zhang 2006；OSAP: FirmAgeMom）

## 二、反转

- **C01 短期反转**：`-(close / delay(close, 20) - 1)`，近 1 个月涨跌取负
- **C02 长期反转**：`-(close / delay(close, 756) - 1)`，近 3 年涨跌取负
- **C26 长期反转（剔除近一年）**：`-(delay(close, 252) / delay(close, 756) - 1)`，取 t-36 至 t-13 个月收益取负（De Bondt & Thaler 1985；OSAP: LRreversal）
- **C27 中期反转**：`-(delay(close, 273) / delay(close, 378) - 1)`，取 t-18 至 t-13 个月收益取负（De Bondt & Thaler 1985；OSAP: MRreversal）

## 三、季节性

- **C28 去年同月收益**：`delay(close, 252) / delay(close, 273) - 1`（Heston & Sadka 2008；OSAP: MomSeasonShort）
- **C29 同月收益·2–5 年**：`(delay(close, 504) / delay(close, 525) - 1 + delay(close, 756) / delay(close, 777) - 1 + delay(close, 1008) / delay(close, 1029) - 1 + delay(close, 1260) / delay(close, 1281) - 1) / 4`，过去第 2–5 年各同月收益的平均（Heston & Sadka 2008；OSAP: MomSeason）
- **C30 同月收益·6–10 年**：过去第 6–10 年各同月收益的平均，构造同 C29、年份平移（Heston & Sadka 2008；OSAP: MomSeason06YrPlus）
- **C31 同月收益·11–15 年**：过去第 11–15 年各同月收益的平均，构造同 C29、年份平移（Heston & Sadka 2008；OSAP: MomSeason11YrPlus）
- **C32 同月收益·16–20 年**：过去第 16–20 年各同月收益的平均，构造同 C29、年份平移（Heston & Sadka 2008；OSAP: MomSeason16YrPlus）
- **C33 非同月动量·近 1 年**：过去 1 年中非同月月份的平均月收益（月收益序列口径，程序自算）（Heston & Sadka 2008；OSAP: Mom12mOffSeason）
- **C34 非同月反转·2–5 年**：过去第 2–5 年非同月月份平均月收益取负（月收益序列口径，程序自算）（Heston & Sadka 2008；OSAP: MomOffSeason）
- **C35 非同月反转·6–10 年**：过去第 6–10 年非同月月份平均月收益取负，构造同 C34、年份平移（Heston & Sadka 2008；OSAP: MomOffSeason06YrPlus）
- **C36 非同月反转·11–15 年**：过去第 11–15 年非同月月份平均月收益取负，构造同 C34、年份平移（Heston & Sadka 2008；OSAP: MomOffSeason11YrPlus）
- **C37 非同月反转·16–20 年**：过去第 16–20 年非同月月份平均月收益取负，构造同 C34、年份平移（Heston & Sadka 2008；OSAP: MomOffSeason16YrPlus）

## 四、波动与风险

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

## 五、流动性与换手

- **C06 放量**：`ts_mean(volume, 5) / ts_mean(volume, 60)`，短长均量比
- **C11 Amihud 非流动性**：`ts_mean(abs(close / delay(close, 1) - 1) / (close * volume), 20)`
- **C12 低换手**：`neg(ts_mean(volume * close / mktcap, 60))`
- **C47 成交额水平**：`neg(log(ts_mean(delay(close * volume, 42), 21)))`，滞后 2 个月的月均成交额取对数取负（Brennan, Chordia & Subrahmanyam 1998；OSAP: DolVol）
- **C48 换手率门槛**：`gt(ts_mean(volume / (mktcap / close), 63), 0.1)`，近 3 个月换手率均值高于 10% 记 1、低于 5% 记 0、中间记缺失（Datar, Naik & Radcliffe 1998；OSAP: ShareVol）
- **C49 量市值比**：`neg(ts_sum(volume / (mktcap / close), 252))`，过去 12 个月换手率之和取负（Haugen & Baker 1996；OSAP: VolMkt）
- **C50 成交量趋势**：过去 60 个月成交量对时间趋势回归的斜率、按均量缩放（月频，程序自算）（Haugen & Baker 1996；OSAP: VolumeTrend）
- **C51 成交量波动**：`neg(过去 36 个月月成交量的标准差)`（月频，程序自算）（Chordia, Subrahmanyam & Anshuman 2001；OSAP: VolSD）
- **C52 换手率波动**：`neg(过去 36 个月换手率的标准差)`（月频，程序自算）（Chordia, Subrahmanyam & Anshuman 2001；OSAP: std_turn）
- **C53 换手率变异系数**：`neg(过去 36 个月换手率标准差 / 均值)`（月频，程序自算）（Chordia, Subrahmanyam & Anshuman 2001）
- **C54 买卖价差（高低价估计）**：由连续两日高低价按 Corwin-Schultz 法反推的有效价差（程序实现）（Amihud & Mendelson 1986；OSAP: BidAskSpread）
- **C55 零成交天数·1 月**：`ts_sum(where(gt(volume, 0), 0, 1), 21)`，近 1 个月零成交量天数（Liu 2006；OSAP: zerotrade1M）
- **C56 零成交天数·6 月**：`ts_mean(where(gt(volume, 0), 0, 1), 126)`，近 6 个月零成交天数均值（Liu 2006；OSAP: zerotrade6M）
- **C57 零成交天数·12 月**：`ts_mean(where(gt(volume, 0), 0, 1), 252)`，近 12 个月零成交天数均值（Liu 2006；OSAP: zerotrade12M）

## 六、规模与价格水平

- **C15 规模**：`neg(log(mktcap))`
- **C58 价格水平**：`neg(log(close))`。数据口径注：本库 close 为拆股调整后价格，名义价格不可得，此条在当前数据下不可用（Blume & Husic 1973；OSAP: Price）
- **C59 上市时长**：`neg(个股在面板中首次出现以来的月数)`，月数为程序自算量（Barry & Brown 1984；OSAP: FirmAge）

## 七、隔夜与日内

- **C13 隔夜累积**：`ts_sum(open / delay(close, 1) - 1, 20)`，20 日隔夜收益之和
- **C14 日内累积取负**：`neg(ts_sum(close / open - 1, 20))`，20 日日内收益之和取负

## 八、信息扩散与行业领先滞后

- **C60 价格延迟·R²版**：个股收益对市场收益当期及滞后 4 期回归，延迟度 = 1 − 受限模型 R²/完整模型 R²，回归为程序预计算量（Hou & Moskowitz 2005；OSAP: PriceDelayRsq）
- **C61 价格延迟·系数版**：同一回归中滞后 1–4 期系数按期数加权占比（Hou & Moskowitz 2005；OSAP: PriceDelaySlope）
- **C62 价格延迟·显著性版**：同一回归中以各期系数 t 值加权的滞后占比（Hou & Moskowitz 2005；OSAP: PriceDelayTstat）
- **C63 行业大票收益**：同行业市值最大 30% 股票的上期平均收益，赋给行业内其余股票（程序自算）（Hou 2007；OSAP: IndRetBig）

## 九、公司行为

- **C64 一年净增发**：`neg(winsorize(delta(log(mktcap / close), 250)))`，股本的约 12 个月增长率取负（Pontiff & Woodgate 2008；OSAP: ShareIss1Y）
- **C65 五年净增发**：`neg(delta(log(mktcap / close), 1260))`，股本的 5 年增长率取负（Daniel & Titman 2006；OSAP: ShareIss5Y）
- **C66 综合权益发行**：`neg(delta(log(mktcap), 1260) - delta(log(close), 1260))`，5 年市值增长率减去 5 年股价涨幅（Daniel & Titman 2006；OSAP: CompEquIss）


## 十、WorldQuant 101 公式化 Alpha

符号约定：returns 为日收益率，adv{d} 为 d 日平均成交量，cap 为 mktcap，vw = (high + low + close) / 3（原文 vwap 在本库的落地口径，本库无 vwap 字段），IndNeutralize 为行业内去均值，非整数窗口向下取整。公式按 Kakushadze (2015) 原文记号。

- **C67 WQ#1 条件波动峰值时点**：`rank(ts_argmax(signed_power(where(returns < 0, ts_std(returns, 20), close), 2), 5)) - 0.5`，下跌时取波动、上涨时取价格，平方后取 5 日内峰值时点排序
- **C68 WQ#2 量价背离**：`-1 * ts_corr(rank(delta(log(volume), 2)), rank((close - open) / open), 6)`，量变化与日内收益的 6 日秩相关取负
- **C69 WQ#3 开盘价量相关**：`-1 * ts_corr(rank(open), rank(volume), 10)`
- **C70 WQ#4 低价时序秩**：`-1 * ts_rank(rank(low), 9)`
- **C71 WQ#6 开盘价量相关（原值）**：`-1 * ts_corr(open, volume, 10)`
- **C72 WQ#7 放量急跌反转**：`where(adv20 < volume, -1 * ts_rank(abs(delta(close, 7)), 60) * sign(delta(close, 7)), -1)`，放量时 7 日涨跌的时序秩取负
- **C73 WQ#8 开盘收益乘积动量**：`-1 * rank((ts_sum(open, 5) * ts_sum(returns, 5)) - delay(ts_sum(open, 5) * ts_sum(returns, 5), 10))`
- **C74 WQ#9 趋势顺势**：`where(0 < ts_min(delta(close, 1), 5), delta(close, 1), where(ts_max(delta(close, 1), 5) < 0, delta(close, 1), -1 * delta(close, 1)))`，5 日同向时顺势、混合时反向
- **C75 WQ#12 量变价反**：`sign(delta(volume, 1)) * (-1 * delta(close, 1))`
- **C76 WQ#13 价量秩协方差**：`-1 * rank(ts_cov(rank(close), rank(volume), 5))`
- **C77 WQ#14 跌幅与价量相关**：`(-1 * rank(delta(returns, 3))) * ts_corr(open, volume, 10)`
- **C78 WQ#15 高价量秩相关累积**：`-1 * ts_sum(rank(ts_corr(rank(high), rank(volume), 3)), 3)`
- **C79 WQ#16 高价量协方差**：`-1 * rank(ts_cov(rank(high), rank(volume), 5))`
- **C80 WQ#17 价格秩×加速度×量比**：`(-1 * rank(ts_rank(close, 10))) * rank(delta(delta(close, 1), 1)) * rank(ts_rank(volume / adv20, 5))`
- **C81 WQ#18 价差与开收相关**：`-1 * rank(ts_std(abs(close - open), 5) + (close - open) + ts_corr(close, open, 10))`
- **C82 WQ#19 周反转×年动量**：`(-1 * sign((close - delay(close, 7)) + delta(close, 7))) * (1 + rank(1 + ts_sum(returns, 250)))`
- **C83 WQ#20 开盘对前日三价差**：`(-1 * rank(open - delay(high, 1))) * rank(open - delay(close, 1)) * rank(open - delay(low, 1))`
- **C84 WQ#21 均线带状态**：短均线（2 日）相对长均线（8 日）±1 倍标准差带的位置状态，结合量比记 ±1（原文条件式）
- **C85 WQ#22 高价量相关变化**：`-1 * (delta(ts_corr(high, volume, 5), 5) * rank(ts_std(close, 20)))`
- **C86 WQ#23 高位回落**：`where(ts_mean(high, 20) < high, -1 * delta(high, 2), 0)`，创 20 日均值上方新高时取负
- **C87 WQ#24 长趋势未动则反转**：100 日均线变化率小于 5% 时取 `-(close - ts_min(close, 100))`，否则取 `-delta(close, 3)`（原文条件式）
- **C88 WQ#26 量价时序秩相关峰值**：`-1 * ts_max(ts_corr(ts_rank(volume, 5), ts_rank(high, 5), 5), 3)`
- **C89 WQ#28 量价低点校准**：`scale(ts_corr(adv20, low, 5) + ((high + low) / 2) - close)`，scale 为截面归一化（原文式）
- **C90 WQ#30 涨跌符号和×量比**：`(1 - rank(sign(close - delay(close, 1)) + sign(delay(close, 1) - delay(close, 2)) + sign(delay(close, 2) - delay(close, 3)))) * ts_sum(volume, 5) / ts_sum(volume, 20)`
- **C91 WQ#31 衰减反转组合**：`rank(rank(rank(decay_linear(-1 * rank(rank(delta(close, 10))), 10)))) + rank(-1 * delta(close, 3)) + sign(scale(ts_corr(adv20, low, 12)))`
- **C92 WQ#33 开收倒数差**：`rank(-1 * (1 - open / close))`，日内涨幅排序取负
- **C93 WQ#34 波动比×日跌**：`rank((1 - rank(ts_std(returns, 2) / ts_std(returns, 5))) + (1 - rank(delta(close, 1))))`
- **C94 WQ#35 量秩×区间秩×收益秩**：`ts_rank(volume, 32) * (1 - ts_rank(close + high - low, 16)) * (1 - ts_rank(returns, 32))`
- **C95 WQ#37 隔夜日内相关＋日内**：`rank(ts_corr(delay(open - close, 1), close, 200)) + rank(open - close)`
- **C96 WQ#38 价格秩×开收比**：`(-1 * rank(ts_rank(close, 10))) * rank(close / open)`
- **C97 WQ#40 高价波动×量价相关**：`(-1 * rank(ts_std(high, 10))) * ts_corr(high, volume, 10)`
- **C98 WQ#43 量比秩×周跌秩**：`ts_rank(volume / adv20, 20) * ts_rank(-1 * delta(close, 7), 8)`
- **C99 WQ#44 高价量秩相关**：`-1 * ts_corr(high, rank(volume), 5)`
- **C100 WQ#45 均价×价量相关衰减**：`-1 * (rank(ts_mean(delay(close, 5), 20)) * ts_corr(close, volume, 2) * rank(ts_corr(ts_sum(close, 5), ts_sum(close, 20), 2)))`

- **C101 WQ#46 价格路径曲率**：前后两段 10 日斜率之差大于 0.25 时记 -1、小于 0 时记 1、其余取 `-delta(close, 1)`（原文条件式）
- **C102 WQ#49 路径曲率·严阈值**：构造同 C101，第二段阈值改为 -0.1（原文 Alpha#49）
- **C103 WQ#52 低点抬升×长动量×量秩**：`((-1 * ts_min(low, 5)) + delay(ts_min(low, 5), 5)) * rank((ts_sum(returns, 240) - ts_sum(returns, 20)) / 220) * ts_rank(volume, 5)`
- **C104 WQ#53 收盘位置变化**：`-1 * delta(((close - low) - (high - close)) / (close - low), 9)`，收盘在日内区间位置的 9 日变化取负
- **C105 WQ#54 日内力量比**：`(-1 * ((low - close) * open^5)) / ((low - high) * close^5)`（原文式）
- **C106 WQ#55 随机位置与量相关**：`-1 * ts_corr(rank((close - ts_min(low, 12)) / (ts_max(high, 12) - ts_min(low, 12))), rank(volume), 6)`
- **C107 WQ#57 距峰值衰减**：`-1 * ((close - vw) / decay_linear(rank(ts_argmax(close, 30)), 2))`，收盘偏离典型价、按距 30 日高点时点的衰减权重缩放
- **C108 WQ#60 区间位置量加权×峰值时点**：`-(2 * scale(rank(((close - low) - (high - close)) / (high - low) * volume)) - scale(rank(ts_argmax(close, 10))))`（原文式）
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
- **C119 WQ#84 典型价距高点幂变换**：`signed_power(ts_rank(vw - ts_max(vw, 15), 21), delta(close, 5))`（原文式）
- **C120 WQ#85 混合收盘量相关幂**：`rank(ts_corr(high * 0.877 + close * 0.123, adv30, 10))^rank(ts_corr(ts_rank((high + low) / 2, 4), ts_rank(volume, 10), 7))`（原文式）
- **C121 WQ#86 收盘量相关 vs 典型价偏离**：`(ts_rank(ts_corr(close, ts_sum(adv20, 15), 6), 20) < rank((open + close) - (vw + open))) ? -1 : 0`（原文式）
- **C122 WQ#88 四价秩差与量相关取小**：`min(rank(decay_linear((rank(open) + rank(low)) - (rank(high) + rank(close)), 8)), ts_rank(decay_linear(ts_corr(ts_rank(close, 8), ts_rank(adv60, 21), 8), 7), 3))`（原文式）
- **C123 WQ#90 距高点×行业量低相关**：`(rank(close - ts_max(close, 5))^ts_rank(ts_corr(IndNeutralize(adv40, subindustry), low, 5), 3)) * -1`（原文式）
- **C124 WQ#92 均线形态与低价量相关取小**：`min(ts_rank(decay_linear(where((high + low) / 2 + close < low + open, 1, 0), 15), 19), ts_rank(decay_linear(ts_corr(rank(low), rank(adv30), 8), 7), 7))`（原文式）
- **C125 WQ#94 典型价距低点幂**：`(rank(vw - ts_min(vw, 12))^ts_rank(ts_corr(ts_rank(vw, 20), ts_rank(adv60, 4), 18), 3)) * -1`（原文式）
- **C126 WQ#95 开盘距低点 vs 中价量相关幂**：`(rank(open - ts_min(open, 12)) < ts_rank(rank(ts_corr(ts_sum((high + low) / 2, 19), ts_sum(adv40, 19), 13))^5, 12)) ? 1 : 0`（原文式）
- **C127 WQ#96 量价秩相关与收盘量峰值相关取大**：`max(ts_rank(decay_linear(ts_corr(rank(vw), rank(volume), 4), 4), 8), ts_rank(decay_linear(ts_argmax(ts_corr(ts_rank(close, 7), ts_rank(adv60, 4), 4), 13), 14), 13)) * -1`（原文式）
- **C128 WQ#98 典型价量相关衰减差**：`rank(decay_linear(ts_corr(vw, ts_sum(adv5, 26), 5), 7)) - rank(decay_linear(ts_rank(ts_argmin(ts_corr(rank(open), rank(adv15), 21), 9), 7), 8))`（原文式）
- **C129 WQ#99 中价量和相关 vs 低价量相关**：`(rank(ts_corr(ts_sum((high + low) / 2, 20), ts_sum(adv60, 20), 9)) < rank(ts_corr(low, volume, 6))) ? -1 : 0`（原文式）
- **C130 WQ#100 区间位置行业中性×量比**：行业中性化后的收盘区间位置量加权值，减去价量相关与距低点时点的组合，整体乘以 volume / adv20（原文 Alpha#100，子行业双重中性）
- **C131 WQ#101 日内收益归一**：`(close - open) / (high - low + 0.001)`，当日涨跌幅占日内振幅之比

## 十一、Alpha158 量价特征

来源：Qlib Alpha158（微软 Qlib 内置特征集，构造参考国泰君安研报）。K 线形态为当日特征；滚动特征每型一条，窗口以 20 日为代表口径（原特征族含 5/10/20/30/60 五档）。

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
- **C144 变化率 ROC**：`delay(close, 20) / close`，20 日前价格与现价之比（Qlib 原定义）
- **C145 均线比 MA**：`ts_mean(close, 20) / close`，均线相对现价
- **C146 价格离散 STD**：`ts_std(close, 20) / close`，价格标准差按现价归一
- **C147 趋势斜率 BETA**：`ts_slope(close, 20) / close`，价格对时间线性回归斜率（程序自算）
- **C148 趋势拟合 RSQR**：价格对时间线性回归的 R²（20 日，程序自算），趋势线性程度
- **C149 趋势残差 RESI**：价格对时间线性回归的当期残差除以现价（程序自算），偏离趋势的程度
- **C150 最高比 MAX**：`ts_max(high, 20) / close`，窗口最高价相对现价
- **C151 最低比 MIN**：`ts_min(low, 20) / close`，窗口最低价相对现价
- **C152 上分位 QTLU**：`ts_quantile(close, 20, 0.8) / close`，价格 80% 分位相对现价（程序自算）
- **C153 下分位 QTLD**：`ts_quantile(close, 20, 0.2) / close`，价格 20% 分位相对现价（程序自算）
- **C154 时序分位 RANK**：`ts_rank(close, 20)`，现价在过去 20 日中的分位
- **C155 随机值 RSV**：`(close - ts_min(low, 20)) / (ts_max(high, 20) - ts_min(low, 20))`，收盘在窗口高低区间的位置
- **C156 距高点天数 IMAX**：`ts_argmax(high, 20) / 20`，距窗口最高价出现的天数占比
- **C157 距低点天数 IMIN**：`ts_argmin(low, 20) / 20`，距窗口最低价出现的天数占比
- **C158 高低点时差 IMXD**：`(ts_argmax(high, 20) - ts_argmin(low, 20)) / 20`，最高与最低出现时点之差
- **C159 价量相关 CORR**：`ts_corr(close, log(volume + 1), 20)`，价格与对数成交量相关
- **C160 价量变化相关 CORD**：`ts_corr(close / delay(close, 1), log(volume / delay(volume, 1) + 1), 20)`，收益率与量变化率相关
- **C161 上涨日占比 CNTP**：`ts_mean(gt(close, delay(close, 1)), 20)`，窗口内上涨日比例
- **C162 下跌日占比 CNTN**：`ts_mean(gt(delay(close, 1), close), 20)`，窗口内下跌日比例
- **C163 涨跌日差 CNTD**：上涨日占比减去下跌日占比（构造同 C161、C162）
- **C164 上涨幅度占比 SUMP**：`ts_sum(max(delta(close, 1), 0), 20) / ts_sum(abs(delta(close, 1)), 20)`，涨幅占总变动之比
- **C165 下跌幅度占比 SUMN**：`ts_sum(max(-delta(close, 1), 0), 20) / ts_sum(abs(delta(close, 1)), 20)`，跌幅占总变动之比
- **C166 净变动占比 SUMD**：上涨幅度占比减去下跌幅度占比（构造同 C164、C165）
- **C167 量均线比 VMA**：`ts_mean(volume, 20) / volume`，均量相对当日量
- **C168 量离散 VSTD**：`ts_std(volume, 20) / volume`，成交量标准差按当日量归一
- **C169 量加权波动比 WVMA**：`ts_std(abs(returns) * volume, 20) / ts_mean(abs(returns) * volume, 20)`，量加权涨跌幅的变异系数
- **C170 放量占比 VSUMP**：`ts_sum(max(delta(volume, 1), 0), 20) / ts_sum(abs(delta(volume, 1)), 20)`，量增部分占量总变动之比
- **C171 缩量占比 VSUMN**：`ts_sum(max(-delta(volume, 1), 0), 20) / ts_sum(abs(delta(volume, 1)), 20)`，量减部分占量总变动之比
- **C172 净量变占比 VSUMD**：放量占比减去缩量占比（构造同 C170、C171）

## 十二、技术指标

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

## 十三、OHLC 波动与价差估计量

本族为用 OHLC 构造的估计量，作为因子使用时方向取负（低波动、低价差、低跳跃占优）。

- **C193 Parkinson 波动**：`sqrt(ts_mean(power(log(high / low), 2), 20) / (4 * log(2)))`，仅用日内高低极值估计波动（Parkinson 1980）
- **C194 Garman-Klass 波动**：`sqrt(ts_mean(0.5 * power(log(high / low), 2) - (2 * log(2) - 1) * power(log(close / open), 2), 20))`，高低极值与开收结合（Garman & Klass 1980）
- **C195 Rogers-Satchell 波动**：`sqrt(ts_mean(log(high / close) * log(high / open) + log(low / close) * log(low / open), 20))`，允许漂移的极值估计（Rogers & Satchell 1991）
- **C196 Yang-Zhang 波动**：隔夜方差、开收方差与 Rogers-Satchell 方差按最优权重组合（Yang & Zhang 2000；程序自算）
- **C197 Roll 隐含价差**：`2 * sqrt(max(-ts_cov(returns, delay(returns, 1), 60), 0))`，由收益负自协方差反推有效价差（Roll 1984；程序自算）
- **C198 下行半方差占比**：`ts_sum(power(min(returns, 0), 2), 20) / ts_sum(power(returns, 2), 20)`，下行波动占总波动之比（程序自算）
- **C199 跳跃方差占比**：`(已实现方差 - 双幂变差) / 已实现方差`，20 日口径（Barndorff-Nielsen & Shephard 2004；双幂变差为程序自算）
- **C200 隔夜方差占比**：`ts_sum(power(open / delay(close, 1) - 1, 2), 20) / ts_sum(power(close / delay(close, 1) - 1, 2), 20)`，隔夜波动占全日波动之比（程序自算）
