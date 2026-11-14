# 经典因子库（全表）

共 200 条：C01–C17 为已入库经典（calc.py），C18–C200 为扩编（来源：Chen & Zimmermann Open Source Asset Pricing 信号文档 SignalDoc，逐条核对）。
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

## 十、价值

- **C67 账面市值比**：`log(有形账面权益 / 市值)`，账面权益与市值在财年末匹配（Stattman 1980；OSAP: BM）
- **C68 资产市值比**：`总资产 / 市值`（Fama & French 1992；OSAP: AM）
- **C69 现金流市值比**：`(净利润 + 折旧) / 市值`（Lakonishok, Shleifer & Vishny 1994；OSAP: CF）
- **C70 经营现金流价格比**：`经营现金流 / 市值`（Desai, Rajgopal & Venkatachalam 2004；OSAP: cfp）
- **C71 盈利价格比**：`净利润 / 滞后 6 个月市值`（Basu 1977；OSAP: EP）
- **C72 销售价格比**：`年营收 / 市值`（Barbee, Mukherji & Raines 1996；OSAP: SP）
- **C73 企业成分 BM**：`(账面权益 + 现金 - 总债务 - 递延费用 + 库存股) / 企业价值同口径`，BM 的企业口径分量（Penman, Richardson & Tuna 2007；OSAP: EBM）
- **C74 企业价值倍数**：`(市值 + 长期债务 + 短期债务 + 递延费用 - 现金) / 营业利润`，方向取负（Loughran & Wellman 2011；OSAP: EntMult）
- **C75 预测盈利价格比**：`分析师下一年 EPS 预测中位数 / 股价`（Elgers, Lo & Pfeiffer 2001；OSAP: sfe）
- **C76 分析师内在价值比**：`基于分析师预测的三阶段股利折现估值 / 市值`（Frankel & Lee 1998；OSAP: AnalystValue）
- **C77 效率前沿指数**：`log(BM)` 对规模、杠杆、资本开支比、研发比、广告比、固定资产比、EBIT 比与行业哑变量滚动回归的残差（Nguyen & Swanson 2009；OSAP: Frontier）
- **C78 短期预测股息率**：按分红月份模式预测的下月股息除以股价、离散化为四档（Litzenberger & Ramaswamy 1979；OSAP: DivYieldST）

## 十一、盈利与质量

- **C79 毛利资产比**：`(营收 - 销售成本) / 总资产`（Novy-Marx 2013；OSAP: GP）
- **C80 营业利润权益比**：`(营收 - 销售成本 - 销管费用 - 利息费用) / 账面权益`（Fama & French 2006；OSAP: OperProf）
- **C81 营业利润率（研发还原）**：`(营收 - 销售成本 - (销管费用 - 研发费用)) / 总资产`（Ball et al. 2016；OSAP: OperProfRD）
- **C82 现金制营业利润率**：`(营收 - 销售成本 - 费用 ± 应收、存货、预付、递延收入、应付与应计项目的年度变动) / 总资产`（Ball et al. 2016；OSAP: CBOperProf）
- **C83 权益收益率**：`净利润 / 账面权益`（Haugen & Baker 1996；OSAP: RoE）
- **C84 季度资产收益率**：`季度净利润 / 滞后总资产`（Balakrishnan, Bartov & Faurel 2010；OSAP: roaq）
- **C85 盈利增长一致性**：过去 48 个月 EPS 同比增速的平均，仅取符号始终一致者（Alwathainani 2009；OSAP: EarningsConsistency）

## 十二、综合评分与财务质量

- **C86 Piotroski F 分数**：盈利、杠杆流动性、经营效率九项二值信号之和，仅在高 BM 组内使用（Piotroski 2000；OSAP: PS）
- **C87 Mohanram G 分数**：盈利与现金流三项、盈利稳定性两项、投资三项共八项信号之和，仅在低 BM 成长股内使用（Mohanram 2005；OSAP: MS）
- **C88 养老金缴存状态**：`(养老金计划资产 - 养老金给付义务) / 市值`（Franzoni & Marin 2006；OSAP: FR）
- **C89 真实脏盈余**：`账面权益变动 - 脏盈余调整项 - (净利 - 优先股股息) + 普通股股息 - 股票净发行额`（Landsman et al. 2011；OSAP: RDS）

## 十三、应计与会计质量

- **C90 应计利润**：`(Δ流动资产 - Δ现金 - Δ流动负债 + Δ短期债务 - Δ应付税款 - 折旧) / 平均总资产`，方向取负（Sloan 1996；OSAP: Accruals）
- **C91 异常应计**：总应计对资产倒数、营收变动、固定资产的年度行业截面回归残差，方向取负（Xie 2001；OSAP: AbnormalAccruals）
- **C92 应计占比**：`(净利润 - 经营现金流) / |净利润|`，方向取负（Hafzalla, Lundholm & Van Winkle 2011；OSAP: PctAcc）
- **C93 总应计占比**：`(净利 - 经营 - 投资 - 融资现金流合计 + 股票净交易) / |净利|`，方向取负（Hafzalla, Lundholm & Van Winkle 2011；OSAP: PctTotAcc）
- **C94 订单积压变化**：`订单积压 / 平均总资产` 的年度变化（Baik & Ahn 2007；OSAP: OrderBacklogChg）

## 十四、资产负债表扩张

- **C95 流动经营资产变化**：`Δ(流动资产 - 现金) / 平均总资产`，方向取负（Richardson et al. 2005；OSAP: DelCOA）
- **C96 权益扩张**：`Δ账面权益 / 平均总资产`，方向取负（Richardson et al. 2005；OSAP: DelEqu）
- **C97 金融负债变化**：`Δ(长期债务 + 短期债务 + 优先股) / 平均总资产`，方向取负（Richardson et al. 2005；OSAP: DelFINL）
- **C98 长期投资变化**：`Δ长期投资与垫款 / 平均总资产`，方向取负（Richardson et al. 2005；OSAP: DelLTI）
- **C99 净金融资产变化**：`Δ(短期投资 + 长期投资 - 总债务 - 优先股) / 总资产`（Richardson et al. 2005；OSAP: DelNetFin）
- **C100 总应计（资产负债表口径）**：净营运资本变化 + 净非流动资产变化 + 净金融资产变化，除以滞后总资产，方向取负（Richardson et al. 2005；OSAP: TotalAccruals）

## 十五、投资与增长

- **C101 资产增长**：`总资产年增长率`，方向取负（Cooper, Gulen & Schill 2008；OSAP: AssetGrowth）
- **C102 账面权益增长**：`账面权益 / 去年账面权益`，方向取负（Lockwood & Prombutr 2010；OSAP: ChEQ）
- **C103 净经营资产增长**：`净经营资产 12 个月增量 / 滞后总资产`，方向取负（Hirshleifer, Hou, Teoh & Zhang 2004；OSAP: dNoa）
- **C104 净经营资产**：`(经营资产 - 经营负债) / 滞后总资产`，方向取负（Hirshleifer et al. 2004；OSAP: NOA）
- **C105 投资强度异动**：`(资本开支 / 营收) / 该比值的 36 个月滚动均值`，方向取负（Titman, Wei & Xie 2004；OSAP: Investment）
- **C106 固定资产与存货扩张**：`(Δ固定资产 + Δ存货) / 滞后总资产`，方向取负（Lyandres, Sun & Zhang 2008；OSAP: InvestPPEInv）
- **C107 存货增长**：通胀调整后的存货年增长率，方向取负（Belo & Lin 2012；OSAP: InvGrowth）
- **C108 存货增量**：`Δ存货 / 平均总资产`，方向取负（Thomas & Zhang 2002；OSAP: ChInv）
- **C109 净营运资本变化**：`((流动资产 - 现金) - (流动负债 - 短期债务)) / 总资产` 的 12 个月变化，方向取负（Soliman 2008；OSAP: ChNWC）
- **C110 长期经营资产增长（扣应计）**：净经营资产年增长减去当年应计（Fairfield, Whisenant & Yohn 2003；OSAP: GrLTNOA）

## 十六、资本开支与经营投入

- **C111 资本开支增长·两年**：资本开支相对两年前的增长率，方向取负（Anderson & Garcia-Feijoo 2006；OSAP: grcapx）
- **C112 资本开支增长·行业调整**：资本开支增长率减去同行业平均增长率，方向取负（Abarbanell & Bushee 1998；OSAP: ChInvIA）
- **C113 雇佣增长**：`雇员人数年度变化 / 前后两年平均雇员数`，方向取负（Bazdresch, Belo & Lin 2014；OSAP: hire）
- **C114 广告费增长**：`log(广告费用) - log(去年广告费用)`，方向取负（Lou 2014；OSAP: GrAdExp）

## 十七、研发与无形资产

- **C115 研发市值比**：`研发费用 / 市值`（Chan, Lakonishok & Sougiannis 2001；OSAP: RD）
- **C116 研发资本比**：`(研发_t + 0.8·研发_{t-1} + 0.6·研发_{t-2} + 0.4·研发_{t-3} + 0.2·研发_{t-4}) / 总资产`（Li 2011；OSAP: RDcap）
- **C117 专利研发比**：`当年专利数 / 加权滞后研发费用`（Hirshleifer, Hsu & Li 2013；OSAP: PatentsRD）
- **C118 专利被引研发比**：`过去 5 年专利被引总数 / (t-3 至 t-7 年研发费用之和)`（Hirshleifer, Hsu & Li 2013；OSAP: CitationsRD）
- **C119 研发转化能力**：销售增长率对滞后 1–5 年研发强度（log(1 + 研发/销售））回归系数的均值（Cohen, Diether & Malloy 2013；OSAP: RDAbility）
- **C120 组织资本**：销管费用按 15% 折旧永续盘存得到的组织资本存量，除以总资产（Eisfeldt & Papanikolaou 2013；OSAP: OrgCap）
- **C121 广告市值比**：`广告费用 / 市值`（Chan, Lakonishok & Sougiannis 2001；OSAP: AdExp）
- **C122 研发激增**：研发强度为正且研发额与研发资产比年增均超 5% 时记 1（Eberhart, Maxwell & Siddique 2004；OSAP: SurpriseRD）
- **C123 品牌资本投资**：`广告费用 / 品牌资本存量`，品牌资本按 50% 折旧永续盘存，方向取负（Belo, Lin & Vitorino 2014；OSAP: BrandInvest）
- **C124 无形回报·BM 版**：五年股票收益对五年前 log(BM）与 BM 变动构造变量截面回归的残差，方向取负（Daniel & Titman 2006；OSAP: IntanBM）
- **C125 无形回报·EP 版**：同一构造，估值比换为盈利价格比（Daniel & Titman 2006；OSAP: IntanEP）
- **C126 无形回报·CFP 版**：同一构造，估值比换为现金流价格比（Daniel & Titman 2006；OSAP: IntanCFP）

## 十八、融资与杠杆

- **C127 净外部融资**：`(股票发行 - 分红 - 股票回购 + 长期债务发行 - 长期债务偿还) / 总资产`，方向取负（Bradshaw, Richardson & Sloan 2006；OSAP: XFIN）
- **C128 净债务融资**：`(长期债务发行 - 长期债务偿还 - 短期债务变动) / 平均总资产`，方向取负（Bradshaw, Richardson & Sloan 2006；OSAP: NetDebtFinance）
- **C129 净股权融资**：`(股票出售 - 股票回购) / 平均总资产`，方向取负（Bradshaw, Richardson & Sloan 2006；OSAP: NetEquityFinance）
- **C130 综合债务发行**：`log(长期债务 + 短期债务)` 的五年变化，方向取负（Lyandres, Sun & Zhang 2008；OSAP: CompositeDebtIssuance）
- **C131 债务发行指示**：当年长期债务发行额大于 0 时记 1，方向取负（Spiess & Affleck-Graves 1999；OSAP: DebtIssuance）
- **C132 可转债指示**：存在递延费用或为可转债预留股份时记 1，方向取负（Valta 2016；OSAP: ConvDebt）
- **C133 市场杠杆**：`总负债 / 市值`（Bhandari 1988；OSAP: Leverage）
- **C134 账面杠杆**：`总资产 / (账面权益 + 递延税 + 优先股)`，方向取负（Fama & French 1992；OSAP: BookLeverage）
- **C135 净债务价格比**：`(长期债务 + 短期债务 + 优先股 + 拖欠优先股息 - 库存股 - 现金) / 市值`，方向取负（Penman, Richardson & Tuna 2007；OSAP: NetDebtPrice）

## 十九、股利、回购与上市

- **C136 股息恢复**：过去 24 个月未分红、本月重新分红，近 6 个月内记 1（Michaely, Thaler & Womack 1995；OSAP: DivInit）
- **C137 股息漏派**：稳定分红公司首次漏派，近 2 个月内记 1，方向取负（Michaely, Thaler & Womack 1995；OSAP: DivOmit）
- **C138 股息季节性**：按历史分红月份模式判定当月为预期分红月时记 1（Hartzmark & Solomon 2013；OSAP: DivSeason）
- **C139 股票回购**：现金流量表回购支出大于 0 时记 1（Ikenberry, Lakonishok & Vermaelen 1995；OSAP: ShareRepurchase）
- **C140 总派付率**：`(普通股股息 + 股票回购额) / 滞后 6 个月市值`（Boudoukh et al. 2007；OSAP: PayoutYield）
- **C141 净派付率**：`(股息 + 回购 - 股票发行) / 滞后 6 个月市值`（Boudoukh et al. 2007；OSAP: NetPayoutYield）
- **C142 新股上市**：IPO 后 6–36 个月记 1，方向取负（Ritter 1991；OSAP: IndIPO）

## 二十、分析师与预期

- **C143 预测修正**：`本月 EPS 一致预测均值 / 上月均值`（Hawkins, Chamberlin & Daniel 1984；OSAP: AnalystRevision）
- **C144 评级变化**：分析师推荐分数（6 减评级）的月度变化均值（Jegadeesh et al. 2004；OSAP: ChangeInRecommendation）
- **C145 一致推荐**：一致推荐均值大于 3 的悲观端与不大于 1.5 的乐观端分档，方向取负（Barber et al. 2001；OSAP: ConsRecomm）
- **C146 预测上调**：下季度 EPS 一致预测较上月上调时记 1（Barber et al. 2001；OSAP: UpRecomm）
- **C147 预测修正累积**：过去 6 个月每月 EPS 预测修正（按股价缩放）之和（Chan, Jegadeesh & Lakonishok 1996；OSAP: REV6）
- **C148 长短期预测差**：分析师 5 年长期增长预测减去短期预测隐含的增长率，方向取负（Da & Warachka 2011；OSAP: EarningsForecastDisparity）
- **C149 预测分歧**：`EPS 预测标准差 / 预测均值`，方向取负（Diether, Malloy & Scherbina 2002；OSAP: ForecastDispersion）
- **C150 长期增长预测**：分析师 5 年 EPS 增长率预测，滞后 6 个月取用，方向取负（La Porta 1996；OSAP: fgr5yrLag）
- **C151 覆盖分析师减少**：下季度 EPS 覆盖分析师数较 3 个月前下降时记 1，方向取负（Scherbina 2008；OSAP: ChNAnalyst）
- **C152 信用评级下调**：近 3 个月内信用评级被下调至少一档时记 1，方向取负（Dichev & Piotroski 2001；OSAP: CredRatDG）
- **C153 剔除费用差**：`IBES 未调整实际 EPS - 报表 EPS`，方向取负（Doyle, Lundholm & Soliman 2003；OSAP: ExclExp）

## 二十一、盈余与营收惊喜

- **C154 盈余惊喜**：`(EPS - 去年同期 EPS - 过去两年平均增长) / 该差值的标准差`（Foster, Olsen & Shevlin 1984；OSAP: EarningsSurprise）
- **C155 惊喜连续性**：盈余惊喜与上一期同号时取当期惊喜值（Loh & Warachka 2012；OSAP: EarningsStreak）
- **C156 盈利连增季数**：季度净利润连续同比增长的季数，上限 8（Loh & Warachka 2012；OSAP: NumEarnIncrease）
- **C157 公告期收益**：盈余公告日前 1 日至后 2 日的异常收益之和（Chan, Jegadeesh & Lakonishok 1996；OSAP: AnnouncementReturn）
- **C158 营收惊喜**：每股营收四季变化相对其过去两年均值的偏离，按标准差缩放（Jegadeesh & Livnat 2006；OSAP: RevenueSurprise）
- **C159 销售存货增长差**：营收增长率减去存货增长率（Abarbanell & Bushee 1998；OSAP: GrSaleToGrInv）
- **C160 销售费用增长差**：营收增长率减去销管费用增长率（Abarbanell & Bushee 1998；OSAP: GrSaleToGrOverhead）
- **C161 营收增长排名**：过去 5 年营收增长年度排名的加权平均，权重 5、4、3、2、1（Lakonishok, Shleifer & Vishny 1994；OSAP: MeanRankRevGrowth）
- **C162 资产周转变化**：`(营收 / 总资产)` 的年度变化（Soliman 2008；OSAP: ChAssetTurnover）

## 二十二、期权与知情交易

- **C163 认购认沽波动差**：平值看涨期权隐含波动率减去平值看跌期权隐含波动率（Bali & Hovakimian 2009；OSAP: CPVolSpread）
- **C164 看涨隐波变化**：30 天期平值看涨期权隐含波动率的月度变化（An, Ang, Bali & Cakici 2014；OSAP: dVolCall）
- **C165 看跌隐波变化**：30 天期平值看跌期权隐含波动率的月度变化，方向取负（An, Ang, Bali & Cakici 2014；OSAP: dVolPut）
- **C166 已实现减隐含波动**：过去 30 天已实现波动率减去平值隐含波动率，方向取负（Bali & Hovakimian 2009；OSAP: RIVolSpread）
- **C167 波动微笑斜率**：平值看跌隐含波动率减去平值看涨隐含波动率，方向取负（Yan 2011；OSAP: SmileSlope）
- **C168 波动偏斜（虚值）**：虚值看跌期权隐含波动率减去虚值看涨期权隐含波动率，方向取负（Xing, Zhang & Zhao 2010；OSAP: skew1）
- **C169 期权股票量比**：`期权月成交量 / 股票月成交量`，方向取负（Johnson & So 2012；OSAP: OptionVolume1）
- **C170 知情交易概率**：由买卖订单流估计的 PIN 知情交易概率（Easley, Hvidkjaer & O'Hara 2002；OSAP: ProbInformedTrading）

## 二十三、风险与困境

- **C171 流动性贝塔**：个股月收益对 Pastor-Stambaugh 流动性创新序列的 60 个月滚动回归系数（Pastor & Stambaugh 2003；OSAP: BetaLiquidityPS）
- **C172 系统波动贝塔**：日收益对市场收益与 VIX 日变化回归中 VIX 项的系数，方向取负（Ang et al. 2006；OSAP: betaVIX）
- **C173 O 分数**：Ohlson 破产概率模型九项财务变量的线性组合，方向取负（Dichev 1998；OSAP: OScore）
- **C174 现金流价格比方差**：`(净利润 + 折旧) / 市值` 的 60 个月滚动方差，方向取负（Haugen & Baker 1996；OSAP: VarCF）
- **C175 特质波动·三因子**：FF 三因子回归残差的标准差（近 1 个月日频），方向取负（Ang et al. 2006；OSAP: IdioVol3F）
- **C176 特质偏度·三因子**：FF 三因子回归残差的偏度（近 1 个月日频），方向取负（Bali, Engle & Murray 2015；OSAP: ReturnSkew3F）

## 二十四、机构、所有权与卖空

- **C177 持股广度变化**：持有该股的机构家数季度变化（Chen, Hong & Stein 2002；OSAP: DelBreadth）
- **C178 接管脆弱性**：`24 - 公司治理指数 G`，限机构持股比例最高组（Cremers & Nair 2005；OSAP: Activism1）
- **C179 积极股东持股**：最大机构持股比例超过 5% 且治理条件满足时取该比例（Cremers & Nair 2005；OSAP: Activism2）
- **C180 公司治理指数**：Gompers-Ishii-Metrick 反接管条款计数 G，方向取负（Gompers, Ishii & Metrick 2003；OSAP: Governance）
- **C181 卖空比例**：`卖空股数 / 流通股数`，方向取负（Dechow et al. 2001；OSAP: ShortInterest）
- **C182 高卖空下机构持股**：卖空比例最高 1% 股票中的机构持股比例（Asquith, Pathak & Ritter 2005；OSAP: IO_ShortInterest）
- **C183 残差机构持股·高估值组**：机构持股对规模回归的残差分位，限市净率最高组（Nagel 2005；OSAP: RIO_MB）
- **C184 残差机构持股·高分歧组**：同一残差机构持股分位，限分析师预测分歧最高组（Nagel 2005；OSAP: RIO_Disp）

## 二十五、信息扩散与关联动量

- **C185 客户动量**：主要客户公司股票组合的上期收益（Cohen & Frazzini 2008；OSAP: CustomerMomentum）
- **C186 客户行业动量**：投入产出表关联的客户行业加权平均收益（Menzly & Ozbas 2010；OSAP: iomom_cust）
- **C187 供应商行业动量**：投入产出表关联的供应商行业加权平均收益（Menzly & Ozbas 2010；OSAP: iomom_supp）
- **C188 集团伪组合收益**：多元化公司各业务分部对应的单业公司行业收益，按分部销售加权（Cohen & Lou 2012；OSAP: retConglomerate）
- **C189 残差动量**：FF 三因子残差收益过去 11 个月的均值除以其标准差（Blitz, Huij & Martens 2011；OSAP: ResidualMomentum）

## 二十六、行业结构与公司特征

- **C190 行业集中度·销售**：三位行业代码销售赫芬达尔指数的 3 年平均，方向取负（Hou & Robinson 2006；OSAP: Herf）
- **C191 行业集中度·权益**：同一构造，权重换为账面权益（Hou & Robinson 2006；OSAP: HerfBE）
- **C192 行业集中度·资产**：同一构造，权重换为总资产（Hou & Robinson 2006；OSAP: HerfAsset）
- **C193 现金资产比**：`现金及短期投资 / 总资产`（Palazzo 2012；OSAP: Cash）
- **C194 资产有形性**：`(现金 + 0.715·应收账款 + 0.547·存货 + 0.535·固定资产净额) / 总资产`，限制造业（Hahn & Lee 2009；OSAP: tang）
- **C195 房地产持有**：房地产类固定资产占固定资产总额之比，同行业去均值（Tuzel 2010；OSAP: realestate）
- **C196 应税收入比**：按法定税率折算的应税收入与账面收入之比（Lev & Nissim 2004；OSAP: Tax）
- **C197 税额变化**：所得税费用的四季变化除以滞后总资产（Thomas & Zhang 2011；OSAP: ChTax）
- **C198 经营杠杆**：`(销管费用 + 销售成本) / 总资产`（Novy-Marx 2011；OSAP: OPLeverage）
- **C199 罪恶股**：烟草、酒类、博彩等行业指示变量（Hong & Kacperczyk 2009；OSAP: sinAlgo）
- **C200 分拆上市**：分拆上市后两年内记 1（Cusatis, Miles & Woolridge 1993；OSAP: Spinoff）
