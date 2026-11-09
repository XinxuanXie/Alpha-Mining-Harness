# 经典因子灵感清单（v1，待 Ethan 拍板）

口径：每条含四项——量（公式）、机制一句话、信息坐标、文献出处。全部条目来源于已发表文献，无自创因子；构造分三类标注：

- **文献原义**：公式即文献度量本身（窗口取本系统常用值）；
- **近似构造**：度量或结论来自文献，单分数合成方式为本系统实现，已注明；
- **待算子**：文献真实存在，但现有算子无法表达，公式缺位。

全部条目只选当前数据（量价、市值、市场收益、行业）可表达者；价值、质量等需财务数据的经典因子不在本清单。未在本系统回测，无成绩数字。

## 反转

**短期反转**（文献原义）
- 量：`-(close / delay(close, 20) - 1)`，即过去 20 日累计收益的相反数
- 机制：短期价格过度反应后向均值回复
- 坐标：收盘价 / 20 日 / 个股自身
- 出处：Jegadeesh (1990), Evidence of Predictable Behavior of Security Returns, Journal of Finance

**长期反转**（文献原义）
- 量：`-(close / delay(close, 756) - 1)`，即过去 3 年累计收益的相反数
- 机制：多年期过度反应在随后数年反转
- 坐标：收盘价 / 756 日 / 个股自身
- 出处：De Bondt & Thaler (1985), Does the Stock Market Overreact?, Journal of Finance

## 动量

**12-2 动量**（文献原义）
- 量：`delay(close, 21) / delay(close, 252) - 1`
- 机制：过去一年的赢家在随后数月继续跑赢，跳过最近一月以避开短期反转
- 坐标：收盘价 / 252 日跳过 21 日 / 个股自身
- 出处：Jegadeesh & Titman (1993), Returns to Buying Winners and Selling Losers, Journal of Finance

**52 周高点**（文献原义）
- 量：`close / ts_max(close, 252)`
- 机制：接近 52 周高点的股票被锚定低估，利好反应不足，继续上行
- 坐标：收盘价 / 252 日 / 个股自身高点
- 出处：George & Hwang (2004), The 52-Week High and Momentum Investing, Journal of Finance

**信息离散度**（近似构造：ID 度量为文献原式，单分数合成为本系统实现）
- 量：`abs(close / delay(close, 252) - 1) * (ts_mean(gt(close / delay(close, 1) - 1, 0), 252) - ts_mean(gt(0, close / delay(close, 1) - 1), 252))`，等价于 |累计收益| ×（上涨天数占比 − 下跌天数占比），即累计收益 ×（−ID）
- 机制：信息以小步连续到达时投资者反应不足，动量更持久；以大跳 discrete 到达时反应迅速，动量弱
- 坐标：日收益符号 / 252 日 / 个股自身路径形态
- 出处：Da, Gurun & Warachka (2014), Frog in the Pan: Continuous Information and Momentum, Review of Financial Studies 27(7)

## 量价

**高成交量溢价**（近似构造：原文以异常成交量事件定义，此处以短长均量比近似）
- 量：`ts_mean(volume, 5) / ts_mean(volume, 60)`
- 机制：异常放量是注意力冲击，提高股票可见性与后续需求，未来一月继续跑赢
- 坐标：成交量 / 5 日对 60 日 / 个股自身常态
- 出处：Gervais, Kaniel & Mingelgrin (2001), The High-Volume Return Premium, Journal of Finance 56(3)

**成交量条件动量**（近似构造：结论来自文献，合成方式为本系统实现）
- 量：12-2 动量 × (1 − 换手率截面排名)，换手率 = `ts_mean(volume * close / mktcap, 60)`
- 机制：高换手赢家的动量反转更快，低换手赢家的动量寿命更长
- 坐标：收盘价与换手 / 252 日 / 个股自身
- 出处：Lee & Swaminathan (2000), Price Momentum and Trading Volume, Journal of Finance

## 波动率

**低波动**（近似构造：原文为特质波动——对因子模型残差的标准差，此处以总波动近似）
- 量：`neg(ts_std(close / delay(close, 1) - 1, 60))`
- 机制：高特质波动股票被彩票偏好与套利限制压价，风险调整后跑输低波动股票
- 坐标：日收益 / 60 日 / 个股自身
- 出处：Ang, Hodrick, Xing & Zhang (2006), The Cross-Section of Volatility and Expected Returns, Journal of Finance

**MAX 效应**（文献原义）
- 量：`neg(ts_max(close / delay(close, 1) - 1, 20))`
- 机制：过去一月出现过极端单日大涨的股票被彩票偏好高估，随后跑输
- 坐标：日收益极值 / 20 日 / 个股自身
- 出处：Bali, Cakici & Whitelaw (2011), Maxing Out: Stocks as Lotteries and the Cross-Section of Expected Returns, Journal of Financial Economics

**低 Beta**（近似构造：Beta 为标准定义，原文另有收缩调整与杠杆组合构造）
- 量：`neg(ts_corr(close / delay(close, 1) - 1, mktret, 252) * ts_std(close / delay(close, 1) - 1, 252) / ts_std(mktret, 252))`
- 机制：受杠杆约束的投资者抢购高 Beta 压低其风险调整收益，低 Beta 被低估
- 坐标：日收益与市场收益 / 252 日 / 相对市场
- 出处：Frazzini & Pedersen (2014), Betting Against Beta, Journal of Financial Economics

## 流动性

**Amihud 非流动性**（文献原义，窗口取 20 日）
- 量：`ts_mean(abs(close / delay(close, 1) - 1) / (close * volume), 20)`
- 机制：单位成交额的价格冲击越大、流动性越差，要求的预期收益越高
- 坐标：日收益与成交额 / 20 日 / 个股自身
- 出处：Amihud (2002), Illiquidity and Stock Returns: Cross-Section and Time-Series Effects, Journal of Financial Markets

**低换手**（文献原义，流通股数由 mktcap / close 折算）
- 量：`neg(ts_mean(volume * close / mktcap, 60))`
- 机制：换手低的股票流动性差且被忽视，未来收益更高
- 坐标：成交量与市值 / 60 日 / 个股自身
- 出处：Datar, Naik & Radcliffe (1998), Liquidity and Stock Returns: An Alternative Test, Journal of Financial Markets 1(2)

## 日内隔夜

**隔夜延续**（文献原义）
- 量：`ts_sum(open / delay(close, 1) - 1, 20)`，即过去 20 日隔夜收益之和
- 机制：隔夜与日内是两类投资者的拉锯，各自时段内的收益延续、跨时段反转；隔夜分量携带持续的信息流
- 坐标：开盘与昨收 / 20 日 / 个股自身
- 出处：Lou, Polk & Skouras (2019), A Tug of War: Overnight versus Intraday Expected Returns, Journal of Financial Economics 134(1)

**日内分量反转**（近似构造：原文为分时段收益互相预测，此处合成到收盘对收盘口径）
- 量：`neg(ts_sum(close / open - 1, 20))`，即过去 20 日日内收益之和的相反数
- 机制：日内涨幅主要由日内客群的追价构成，对随后的隔夜与未来收益形成反向压力
- 坐标：收盘与开盘 / 20 日 / 个股自身
- 出处：Lou, Polk & Skouras (2019), 同上

## 规模

**小市值**（文献原义）
- 量：`neg(log(mktcap))`
- 机制：小市值股票在控制风险后仍有更高平均收益（流动性、忽视与信息风险补偿）
- 坐标：市值 / 当日 / 全截面
- 出处：Banz (1981), The Relationship Between Return and Market Value of Common Stocks, Journal of Financial Economics；另见 Fama & French (1992), Journal of Finance

## 其他

**收益季节性**（近似构造：原文用历年同月收益，此处取去年同期一段）
- 量：`delay(close, 232) / delay(close, 252) - 1`，即一年前同期的 20 日收益
- 机制：个股收益在相同日历月份上跨年重复出现，与定期信息发布的日历节奏有关
- 坐标：收盘价 / 滞后一年 / 个股自身
- 出处：Heston & Sadka (2008), Seasonality in the Cross-Section of Stock Returns, Journal of Financial Economics

**行业动量**（待算子：缺行业均值算子，现有算子无法表达）
- 量：所属行业过去 6 月平均收益（公式缺位）
- 机制：行业层面的信息扩散慢于个股，行业动量可分解并解释相当部分的个股动量
- 坐标：收盘价 / 约 126 日 / 相对所属行业
- 出处：Moskowitz & Grinblatt (1999), Do Industries Explain Momentum?, Journal of Finance
