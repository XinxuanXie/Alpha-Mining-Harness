# 经典因子库（全表）

共 66 条：C01–C17 为已入库经典（calc.py），C18–C66 为扩编候选（来源：Chen & Zimmermann Open Source Asset Pricing 信号文档，逐条核对，清单见 classic_library_candidates.md）。
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

