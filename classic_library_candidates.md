# 经典因子库扩编候选清单（供圈选）

编制日期：2026-11-14
目标：为现有 17 个经典因子扩编，目标 100 条候选。
**实际编制结果：49 条**（另附弱证据条目 3 条，不计入）。凑不满 100 的原因见文末「缺口说明」——在「只收录 OSAP/HXZ 可查证出处 + 只用价量与市值可算 + 不与已有 17 条重复」三条硬约束下，真实可用的信号就这么多；再往上凑只能靠编造参数组合或把已有因子换名重列，本清单不做。

## 来源与口径

- 主要来源：Chen & Zimmermann, *Open Source Cross-Sectional Asset Pricing* (Critical Finance Review, 2022) 的 SignalDoc（信号文档，含每个信号的原论文、构造定义、数据类别）。本清单逐条核对了 SignalDoc 中 Cat.Data = Price / Trading 的全部条目，以及少数 Cat.Data 标为 Accounting 但构造实际只用市值与收益的条目（已逐条注明）。
- 交叉核对：Hou, Xue & Zhang 复现清单（global-q.org）；Harvey, Liu & Zhu (2016) 因子清单。
- 数据约束：只用 open / high / low / close / volume / mktcap 六个字段，外加可自算的个股收益、市场收益、股本（= mktcap / close）、换手率（= volume × close / mktcap）、行业（GICS）归属与上市时长（面板内首次出现起算）。凡需要账面价值、盈利、营收、分析师预期、期权隐含波动率、融券余额、逐笔成交分类、外部指数序列（如 VIX）的信号，一律排除（文末列举）。
- 已有 17 条不重复计入：短期反转(1月)、长期反转(3年)、中期动量(12-1)、52周高点、趋势一致性(近似)、量能比(5/60)、动量×低换手(近似)、低波动(60日)、MAX彩票效应、特质波动(近似)、Amihud非流动性、低换手(60日)、隔夜收益累积、日内收益累积取负、规模、动量分段(近月)、行业动量。个别候选与已有条目同族但构造/窗口为文献中不同的已发表变体，已在构造要点中注明区别。
- 经济解释为一句大白话；方向（多空）以原论文为准，入库实现时按本系统口径统一测。

## 家族分布

| 家族 | 条数 |
|---|---|
| 动量 | 8 |
| 反转 | 2 |
| 季节性（动量/反转的季节变体） | 10 |
| 波动与风险 | 9 |
| 流动性与换手 | 11 |
| 规模与价格水平 | 2 |
| 信息扩散与行业领先滞后 | 4 |
| 公司行为（增发） | 3 |
| **合计** | **49** |

---

## 一、动量（Momentum）

| # | 因子名 | 家族 | 经济解释 | 所需字段 | 构造要点 | 出处 |
|---|---|---|---|---|---|---|
| 1 | Momentum 3M（3月动量） | 动量 | 过去涨过的股票短期还会接着涨，趋势有惯性 | close | 形成期 3 个月、跳过最近 1 个月；Jegadeesh-Titman 原始参数网格（3/6/9/12 月）中的一格，OSAP 实现了其中 6 与 12 | Jegadeesh & Titman (1993)；OSAP 信号 Mom6m/Mom12m 同源 |
| 2 | Momentum 6M（6月动量，Mom6m） | 动量 | 同上，半年尺度的趋势惯性 | close | 形成期 6 个月、跳过最近 1 个月 | Jegadeesh & Titman (1993)；OSAP: Mom6m |
| 3 | Momentum 9M（9月动量） | 动量 | 同上，9 个月尺度的趋势惯性 | close | 形成期 9 个月、跳过最近 1 个月；JT 原始参数网格的一格 | Jegadeesh & Titman (1993)；OSAP 同源 |
| 4 | Intermediate Momentum（中期动量，IntMom） | 动量 | 真正能持续的是较早那段趋势，最近半年的涨幅反而含反转成分 | close | 取 t-12 到 t-6 个月的累计收益（只要后半段形成期） | Novy-Marx (2012)；OSAP: IntMom |
| 5 | Trend Factor（趋势因子） | 动量 | 多个时间尺度的均线趋势同向时，趋势信号最可信 | close | 多窗口移动平均信号的组合（原论文 2.1–2.2 节定义），非单一形成期收益 | Han, Zhou & Zhu (2016)；OSAP: TrendFactor |
| 6 | Momentum in High Volume Stocks（高量动量，MomVol） | 动量 | 放量上涨的趋势有真实买盘支撑，比缩量上涨更能持续 | close, volume, mktcap | 6 月动量 × 高换手组：只在换手率最高组内按动量赋值（双重排序） | Lee & Swaminathan (2000)；OSAP: MomVol |
| 7 | Momentum and LT Reversal（动量×长期反转组合，MomRev） | 动量 | 短期是赢家、长期是输家的股票，是两类效应叠加的最强组合 | close | 二值信号：6 月动量最高五分位且 36 月收益最低五分位记 1，反之记 0 | Chan and Ko (2006)；OSAP: MomRev |
| 8 | Firm Age–Momentum（年轻股动量，FirmAgeMom） | 动量 | 年轻公司信息不透明、定价慢，动量在年轻股里更强 | close（+上市时长自算） | 6 月动量，只在上市时长最短五分位股票内取值 | Zhang (2006)；OSAP: FirmAgeMom |

## 二、反转（Reversal）

| # | 因子名 | 家族 | 经济解释 | 所需字段 | 构造要点 | 出处 |
|---|---|---|---|---|---|---|
| 9 | Long-Run Reversal（长期反转·剔除近一年，LRreversal） | 反转 | 三到五年前涨太多的股票长期会跌回来，市场对旧消息过度反应 | close | 取 t-36 到 t-13 个月收益取负；与已有「长期反转(3年)」的区别是剔除了最近 12 个月 | De Bondt & Thaler (1985)；OSAP: LRreversal |
| 10 | Medium-Run Reversal（中期反转，MRreversal） | 反转 | 一年半以前那段涨幅同样存在过度反应后的回落 | close | 取 t-18 到 t-13 个月收益取负 | De Bondt & Thaler (1985)；OSAP: MRreversal |

## 三、季节性（Seasonality，Heston & Sadka 2008 的完整变体组）

| # | 因子名 | 家族 | 经济解释 | 所需字段 | 构造要点 | 出处 |
|---|---|---|---|---|---|---|
| 11 | Return Seasonality Last Year（去年同月收益，MomSeasonShort） | 季节性 | 股票有「日历习惯」：去年同一个月份涨过的，今年同月容易再涨 | close | 去年同月的单月收益 | Heston & Sadka (2008)；OSAP: MomSeasonShort |
| 12 | Return Seasonality Years 2–5（同月收益·2–5年，MomSeason） | 季节性 | 同月效应在往前数 2 到 5 年的同月最稳定 | close | 过去第 2–5 年各同月收益的平均 | Heston & Sadka (2008)；OSAP: MomSeason |
| 13 | Return Seasonality Years 6–10（同月收益·6–10年） | 季节性 | 同月习惯可以追溯到十年前的同月 | close | 过去第 6–10 年各同月收益的平均；本系统面板 2000 年起，此条与下两条早年样本不足 | Heston & Sadka (2008)；OSAP: MomSeason06YrPlus |
| 14 | Return Seasonality Years 11–15（同月收益·11–15年） | 季节性 | 更久远的同月记录仍有微弱的季节记忆 | close | 过去第 11–15 年各同月收益的平均 | Heston & Sadka (2008)；OSAP: MomSeason11YrPlus |
| 15 | Return Seasonality Years 16–20（同月收益·16–20年） | 季节性 | 季节记忆的极限距离，效应最弱、样本要求最高 | close | 过去第 16–20 年各同月收益的平均；本系统 2000–2026 面板仅尾部年份可用 | Heston & Sadka (2008)；OSAP: MomSeason16YrPlus |
| 16 | Momentum Off-Season 1Y（非同月动量·近1年，Mom12mOffSeason） | 季节性 | 把同月那部分剔掉后，剩下的近期收益仍有动量 | close | 过去 1 年中「非同月」月份的平均收益 | Heston & Sadka (2008)；OSAP: Mom12mOffSeason |
| 17 | Off-Season Reversal Years 2–5（非同月反转·2–5年，MomOffSeason） | 季节性 | 非同月的旧收益不带季节加成，表现为长期反转 | close | 过去第 2–5 年非同月月份平均收益，取负向 | Heston & Sadka (2008)；OSAP: MomOffSeason |
| 18 | Off-Season Reversal Years 6–10（非同月反转·6–10年） | 季节性 | 更久远的非同月收益同样以反转为主 | close | 过去第 6–10 年非同月月份平均收益，取负向 | Heston & Sadka (2008)；OSAP: MomOffSeason06YrPlus |
| 19 | Off-Season Reversal Years 11–15（非同月反转·11–15年） | 季节性 | 十年以上非同月旧收益的反转残余 | close | 过去第 11–15 年非同月月份平均收益，取负向 | Heston & Sadka (2008)；OSAP: MomOffSeason11YrPlus |
| 20 | Off-Season Reversal Years 16–20（非同月反转·16–20年） | 季节性 | 非同月反转的极限距离版本 | close | 过去第 16–20 年非同月月份平均收益，取负向；样本约束同 #15 | Heston & Sadka (2008)；OSAP: MomOffSeason16YrPlus |

## 四、波动与风险（Volatility & Risk）

| # | 因子名 | 家族 | 经济解释 | 所需字段 | 构造要点 | 出处 |
|---|---|---|---|---|---|---|
| 21 | CAPM Beta（市场贝塔，Beta） | 波动与风险 | 对大盘越敏感的股票承担越多系统性风险，但实证里高贝塔并不带来高收益（低贝塔占优） | close（+市场收益自算） | 过去 60 个月月收益对市场收益的滚动回归斜率 | Fama & MacBeth (1973)；OSAP: Beta |
| 22 | Frazzini-Pedersen Beta（FP 贝塔，BetaFP） | 波动与风险 | 用重叠三日收益算贝塔能对付不常交易股票的失真，是「押注低贝塔」策略的原料 | close（+市场收益自算） | 过去 5 年日频、三日重叠收益回归，贝塔 = 相关 × 个股波动/市场波动 | Frazzini & Pedersen (2014)；OSAP: BetaFP |
| 23 | Tail Risk Beta（尾部风险贝塔，BetaTailRisk） | 波动与风险 | 在全市场最惨的日子里跌得越狠的股票，平时要给更高回报作补偿 | close（需全截面收益分布自算） | 先算截面 5% 分位以下的尾部冲击序列，再做 120 个月滚动回归取其系数 | Kelly & Jiang (2014)；OSAP: BetaTailRisk |
| 24 | Idiosyncratic Volatility AHT（特质波动·一年CAPM版，IdioVolAHT） | 波动与风险 | 撇开大盘后自己乱跳的股票被散户当彩票炒贵，之后跑输 | close（+市场收益自算） | 过去 1 年日收益对市场做 CAPM 回归，取残差标准差；与已有「特质波动(近似)」的区别是窗口为一年且为单因子市场模型 | Ali, Hwang & Trombley (2003)；OSAP: IdioVolAHT |
| 25 | Realized Volatility 1M（已实现总波动·1月，RealizedVol） | 波动与风险 | 最近一个月总波动大的股票整体跑输，不只是特质部分 | close | 过去 1 个月日收益标准差；与已有「低波动(60日)」同族、窗口更短（注：OSAP 该条详细定义用 CAPM 残差，实现时取总波动口径以区别于 #24） | Ang et al. (2006)；OSAP: RealizedVol |
| 26 | Coskewness（协偏度·月频，Coskewness） | 波动与风险 | 大盘暴涨时跟着冲得最猛的股票像彩票，投资者愿意为此少要回报 | close（+市场收益自算） | 过去 60 个月月频：E[r̃ᵢ·r̃ₘ²] 标准化，即个股收益与市场收益平方的协动 | Harvey & Siddique (2000)；OSAP: Coskewness |
| 27 | Coskewness ACX（协偏度·日频，CoskewACX） | 波动与风险 | 同上，用日频数据估得更细 | close（+市场收益自算） | 过去 1 年日频计算同一协偏度公式（去均值口径） | Ang, Chen & Xing (2006)；OSAP: CoskewACX |
| 28 | Return Skewness（收益偏度，ReturnSkew） | 波动与风险 | 最近收益分布越右偏（偶尔暴涨）的股票越像彩票，被高估后跑输 | close | 过去 1 个月日收益的三阶矩偏度 | Bali, Engle & Murray (2015)；OSAP: ReturnSkew |
| 29 | Idiosyncratic Skewness CAPM（特质偏度·CAPM版，ReturnSkewCAPM） | 波动与风险 | 撇开大盘成分后，个股自己的收益越右偏越被高估 | close（+市场收益自算） | 过去 1 个月日收益对市场回归取残差，再算残差偏度；原论文用三因子版，此为 HXZ 的 CAPM 变体，只用市场收益可算 | Bali, Engle & Murray (2015)；OSAP: ReturnSkewCAPM（HXZ 变体） |

## 五、流动性与换手（Liquidity & Turnover）

| # | 因子名 | 家族 | 经济解释 | 所需字段 | 构造要点 | 出处 |
|---|---|---|---|---|---|---|
| 30 | Dollar Volume（成交额水平，DolVol） | 流动性与换手 | 过去成交额大的股票关注度高、流动性好，之后回报偏低 | close, volume | 滞后 2 个月的成交额（价格×成交量）取对数；是「水平」而非已有量能比的「比值」 | Brennan, Chordia & Subrahmanyam (1998)；OSAP: DolVol |
| 31 | Share Volume（换手率门槛，ShareVol） | 流动性与换手 | 换手率冲过高位门槛说明筹码剧烈换手、意见分歧大，之后跑输 | close, volume, mktcap | 近 3 个月换手率（成交量/股本，股本=mktcap/close）均值，>10% 记 1、<5% 记 0 的二值信号 | Datar, Naik & Radcliffe (1998)；OSAP: ShareVol |
| 32 | Volume to Market Equity（量市值比，VolMkt） | 流动性与换手 | 一年成交额相对市值越高，交易越拥挤，预期回报越低 | close, volume, mktcap | 过去 12 个月月均成交额 ÷ 市值（即年化换手口径） | Haugen & Baker (1996)；OSAP: VolMkt |
| 33 | Volume Trend（成交量趋势，VolumeTrend） | 流动性与换手 | 成交量在持续放大的股票是关注度正在升温的股票，升温之后回报转弱 | volume | 过去 60 个月成交量对时间趋势回归的斜率，按均量缩放 | Haugen & Baker (1996)；OSAP: VolumeTrend |
| 34 | Volume Variance（成交量波动，VolSD） | 流动性与换手 | 成交量忽大忽小的股票交易不稳定，流动性风险更高、回报更低 | volume | 过去 36 个月月成交量的标准差 | Chordia, Subrahmanyam & Anshuman (2001)；OSAP: VolSD |
| 35 | Turnover Volatility（换手率波动，std_turn） | 流动性与换手 | 换手率本身越不稳定，说明持股人群越不稳定，之后跑输 | close, volume, mktcap | 过去 36 个月换手率（成交量/股本）的标准差 | Chordia, Subrahmanyam & Anshuman (2001)；OSAP: std_turn |
| 36 | Turnover CV（换手率变异系数） | 流动性与换手 | 同上，但按自身平均换手缩放，跨股票更可比 | close, volume, mktcap | 过去 36 个月换手率标准差 ÷ 均值；原论文中与 #35 并列的 CVTURN 变量 | Chordia, Subrahmanyam & Anshuman (2001)；OSAP: std_turn 条目注 |
| 37 | Bid-Ask Spread（买卖价差·高低价估计，BidAskSpread） | 流动性与换手 | 买卖价差越宽，交易成本越高，持有人要求更高回报补偿 | high, low | 原论文用报价价差；OSAP 复现用 Corwin-Schultz 法从两日高低价反推有效价差，只用 high/low 可算 | Amihud & Mendelson (1986)；OSAP: BidAskSpread（Corwin-Schultz 实现） |
| 38 | Zero Trades 1M（零成交天数·1月，zerotrade1M） | 流动性与换手 | 一个月里没成交的天数越多，股票越被冷落、流动性越差 | volume | 近 1 个月零成交量天数（加换手微调项，刘氏流动性度量 LM1） | Liu (2006)；OSAP: zerotrade1M |
| 39 | Zero Trades 6M（零成交天数·6月，zerotrade6M） | 流动性与换手 | 半年尺度的冷落程度更稳定地刻画流动性差 | volume | 近 6 个月零成交天数均值（LM6） | Liu (2006)；OSAP: zerotrade6M |
| 40 | Zero Trades 12M（零成交天数·12月，zerotrade12M） | 流动性与换手 | 一年尺度的零成交是结构性的无人问津，与慢速回报预测匹配 | volume | 近 12 个月零成交天数均值（LM12） | Liu (2006)；OSAP: zerotrade12M |

## 六、规模与价格水平（Size & Price Level）

| # | 因子名 | 家族 | 经济解释 | 所需字段 | 构造要点 | 出处 |
|---|---|---|---|---|---|---|
| 41 | Price（价格水平，Price） | 规模与价格水平 | 名义股价低的股票散户多、被忽视，长期有溢价；股价本身是一个独立于市值的维度 | close | 股价取对数取负向；注意与已有「规模」的区别：量的是每股价格不是总市值 | Blume & Husic (1973)；OSAP: Price |
| 42 | Firm Age（上市时长，FirmAge） | 规模与价格水平 | 上市越久的公司信息越透明、风险溢价越低；年轻公司带信息不透明溢价 | （面板自算：首次出现月份至今） | 个股在面板中首次出现以来的月数，取负向 | Barry & Brown (1984)；OSAP: FirmAge |

## 七、信息扩散与行业领先滞后（Lead-Lag）

| # | 因子名 | 家族 | 经济解释 | 所需字段 | 构造要点 | 出处 |
|---|---|---|---|---|---|---|
| 43 | Price Delay R²（价格延迟·R²版，PriceDelayRsq） | 信息扩散与行业领先滞后 | 股价对市场消息反应越迟钝的股票，信息扩散越慢，之后会补涨补跌 | close（+市场收益自算） | 过去 1 年日收益对市场收益当期及滞后 4 期回归，延迟度 = 1 − 受限模型R²/完整模型R²（D1） | Hou & Moskowitz (2005)；OSAP: PriceDelayRsq |
| 44 | Price Delay Slope（价格延迟·系数版，PriceDelaySlope） | 信息扩散与行业领先滞后 | 同上，用滞后系数的加权占比直接量「反应有多慢」 | close（+市场收益自算） | 同一回归中滞后 1–4 期系数按期数加权 ÷ 全部系数之和（D2） | Hou & Moskowitz (2005)；OSAP: PriceDelaySlope |
| 45 | Price Delay T-stat（价格延迟·显著性版，PriceDelayTstat） | 信息扩散与行业领先滞后 | 同上，用 t 值加权对估计噪声更稳健 | close（+市场收益自算） | 以各期系数的 t 值代替系数本身重复 D2 的加权（D3） | Hou & Moskowitz (2005)；OSAP: PriceDelayTstat |
| 46 | Industry Return of Big Firms（行业大票收益，IndRetBig） | 信息扩散与行业领先滞后 | 行业里的大公司先得到信息、先涨，小公司跟着慢慢反应 | close, mktcap（+行业自算） | 同行业市值最大 30% 股票的上期平均收益，赋给行业内其余股票（大票自身剔除） | Hou (2007)；OSAP: IndRetBig |

## 八、公司行为（Corporate Actions：增发）

| # | 因子名 | 家族 | 经济解释 | 所需字段 | 构造要点 | 出处 |
|---|---|---|---|---|---|---|
| 47 | Share Issuance 1Y（一年净增发，ShareIss1Y） | 公司行为 | 一年里大量发新股的公司多在股价高估时融资摊薄，之后跑输 | close, mktcap | 股本（= mktcap / close，拆股调整后）的 12 个月增长率，取负向 | Pontiff & Woodgate (2008)；OSAP: ShareIss1Y |
| 48 | Share Issuance 5Y（五年净增发，ShareIss5Y） | 公司行为 | 五年尺度的持续增发是更强的「管理层觉得股价贵」信号 | close, mktcap | 股本的 5 年增长率，取负向 | Daniel & Titman (2006)；OSAP: ShareIss5Y |
| 49 | Composite Equity Issuance（综合权益发行，CompEquIss） | 公司行为 | 市值涨幅里超过股价涨幅的那部分就是净发股，量得比单看股本更全 | close, mktcap | 5 年市值增长率减去 5 年股价涨幅；OSAP 将其归类 Accounting，但构造只用市值与收益，本系统可算 | Daniel & Titman (2006)；OSAP: CompEquIss |

---

## 附一：弱证据条目（已查证出处，但不计入 49 条，供参考）

| 因子名 | 家族 | 说明 | 出处 |
|---|---|---|---|
| Downside Beta（下行贝塔，DownsideBeta） | 波动与风险 | 只在市场下跌日估的贝塔。构造可算（日收益+市场收益，252 日窗口），但 OSAP 将其列为 Placebo——原论文表 8 中以历史贝塔构造时不显著 | Ang, Chen & Xing (2006)；OSAP: DownsideBeta |
| Dimson Beta（丁森贝塔，BetaDimson） | 波动与风险 | 用市场收益的领先/滞后项修正不常交易造成的贝塔低估。OSAP 列为 Placebo：原论文只证明它能预测未来贝塔，未证明预测收益 | Dimson (1979)；OSAP: BetaDimson |
| Consistently Positive / Negative Returns（持续同向收益，ConsPosRet / ConsNegRet） | 动量 | 连续 6 个月同号收益的二值信号。出处在 SignalDoc 内，但 OSAP 标注为 Drop（未收入正式数据集，亦不在 HXZ/MP 清单前列） | Watkins (2003)；OSAP: ConsPosRet / ConsNegRet |

另：Idiosyncratic Volatility CAPM（Ang et al. 2006，OSAP 的 IdioVolCAPM / RealizedVol 残差口径）与已有「特质波动(近似)」口径接近，未计入，避免换名重复；若圈选 #24 时可一并核对两者关系。

## 附二：被排除的著名因子举例（有经典出处，但本系统数据算不出来）

| 因子 | 出处 | 排除原因 |
|---|---|---|
| Book-to-Market（账面市值比） | Fama & French (1992)；OSAP: BM | 需要账面权益（财报） |
| Earnings-to-Price（盈利价格比） | Basu (1977)；OSAP: EP | 需要净利润（财报） |
| Asset Growth（资产增长） | Cooper, Gulen & Schill (2008)；OSAP: AssetGrowth | 需要总资产（财报） |
| Gross Profitability（毛利资产比） | Novy-Marx (2013)；OSAP: GP | 需要营收与成本（财报） |
| Accruals（应计利润） | Sloan (1996)；OSAP: Accruals | 需要资产负债表与现金流（财报） |
| Net Payout Yield（净支付率） | Boudoukh et al. (2007)；OSAP: NetPayoutYield | 需要分红与回购金额（财报/分配数据） |
| Analyst Revision（分析师修正） | Hawkins, Chamberlin & Daniel (1984)；OSAP: AnalystRevision | 需要 IBES 分析师预期 |
| Forecast Dispersion（预期分歧） | Diether, Malloy & Scherbina (2002)；OSAP: ForecastDispersion | 需要 IBES 分析师预期 |
| Option Vol Spread / Smirk（期权波动率类） | Bali & Hovakimian (2009)；Yan (2011)；OSAP: CPVolSpread 等 | 需要 OptionMetrics 期权隐含波动率 |
| Short Interest（融券余额） | Dechow et al. (2001)；OSAP: ShortInterest | 需要融券余额数据 |
| PIN（知情交易概率） | Easley, Hvidkjaer & O'Hara (2002)；OSAP: ProbInformedTrading | 需要逐笔买卖方向分类（盘中数据） |
| Pastor-Stambaugh Liquidity Beta | Pastor & Stambaugh (2003)；OSAP: BetaLiquidityPS | 需要 Pastor 发布的全市场流动性创新外部序列，非本系统字段可自算 |
| Systematic Volatility Beta（betaVIX） | Ang et al. (2006)；OSAP: betaVIX | 需要 VIX 外部序列 |
| Residual Momentum（残差动量） | Blitz, Huij & Martens (2011)；OSAP: ResidualMomentum | 需要 SMB、HML 因子收益（本系统只有市场收益；BM 又需财报） |
| Idiosyncratic Volatility 3F / Return Skew 3F | Ang et al. (2006)；Bali, Engle & Murray (2015)；OSAP 对应条目 | 需要三因子收益；本清单已收其 CAPM 变体（#24、#29） |
| Customer Momentum（客户动量） | Cohen & Frazzini (2008)；OSAP: CustomerMomentum | 需要 Compustat 客户分部数据 |
| Industry Concentration（行业集中度 Herf） | Hou & Robinson (2006)；OSAP: Herf / HerfBE / HerfAsset | 原信号基于营收/账面权益/总资产；用市值替代即非原信号，不收 |
| IPO Indicator（IndIPO） | Ritter (1991)；OSAP: IndIPO | 需要 Ritter 的 IPO 日期库；上市时长（#42）是另一信号，不能冒充 |
| Earnings Announcement Return | Chan, Jegadeesh & Lakonishok (1996)；OSAP: AnnouncementReturn | 需要 IBES 财报公告日期 |

## 附三：缺口说明（为什么是 49 条而不是 100 条）

OSAP 共 212 个正式信号（SignalDoc 全表 332 行，含 placebo 与 HXZ 变体）。按 Cat.Data 分：Accounting 约占一半，Analyst、Options、13F、Event、Other（专利、投入产出表等）又占去大部分；Price 与 Trading 两类合计约 60 个。其中再扣掉：① 已有 17 条的本体或近似口径（Mom12m、High52、STreversal、Size、Illiquidity、MaxRet、IndMom、IdioVol 类等）；② 名义价量但实际需要外部序列或盘中数据的（BetaLiquidityPS、betaVIX、PIN、ShortInterest 等）；③ 需要 FF 三因子/Q 因子的（ResidualMomentum、IdioVol3F、ReturnSkew3F 等），剩下的就是这 49 条（含同族的已发表多参数变体：Jegadeesh-Titman 参数网格、Heston-Sadka 季节变体组、Liu 零成交三窗口、Hou-Moskowitz 延迟三口径等）。隔夜/日内家族在 OSAP 中没有专门信号（Lou, Polk & Skouras 的隔夜收益研究不在 OSAP 信号库内），且已有库中已有隔夜、日内两条，故本清单该家族为 0。区间与路径形态家族（如 Parkinson/Garman-Klass 波动估计）在 OSAP/HXZ 中是估计量而非成文的截面预测信号，无出处可引，未收。若要扩到 100 条，只能放宽三条硬约束之一（引入外部数据、接受与已有因子高度重复的换名版本、或收录无文献出处的自创参数组合），本清单按约定不做。

## 信息来源

- Open Source Asset Pricing 官网与数据页：https://www.openassetpricing.com/data/
- SignalDoc（逐条核对的信号文档）：https://github.com/OpenSourceAP/CrossSection/blob/master/SignalDoc.csv
- Chen & Zimmermann (2022) 论文（FEDS 版）：https://doi.org/10.17016/FEDS.2021.037
- Hou, Xue & Zhang 复现数据（交叉核对）：https://global-q.org/
- Harvey, Liu & Zhu (2016), "…and the Cross-Section of Expected Returns", Review of Financial Studies（因子清单交叉核对）
