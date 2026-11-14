# 经典因子库（索引）

共 200 条，按 13 个家族分文件存放。C01–C17 为已入库经典（calc.py）；C18–C66 来源为 Chen & Zimmermann Open Source Asset Pricing 信号文档；C67–C200 来源为 Kakushadze (2015) WorldQuant 101、Qlib Alpha158、经典技术指标与 OHLC 估计量文献。全部条目只使用价格、成交量、市值、市场收益与行业字段及可自算量。
格式：编号 + 名称 + 公式 + 一句构成说明。方向以原论文为准；判定口径与现有系统一致。

- [一、动量](classic_library/01-momentum.md)：过去中期收益的延续效应。构造以跳过最近月的区间收益、距 52 周高点距离与行业累积收益为主。（14 条，C03–C25）
- [二、反转](classic_library/02-reversal.md)：涨跌过度后的均值回归，含短期与长期两型。构造以区间收益取负为主。（4 条，C01–C27）
- [三、季节性](classic_library/03-seasonality.md)：日历规律：历史同月收益在当月重现。构造以过去各年同月收益与非同月收益的对照为主。（10 条，C28–C37）
- [四、波动与风险](classic_library/04-volatility-risk.md)：波动、偏度、贝塔等风险特征与收益的关系，主体为低风险占优。构造以滚动波动、回归贝塔与残差统计为主。（12 条，C08–C46）
- [五、流动性与换手](classic_library/05-liquidity-turnover.md)：交易活跃度与非流动性溢价。构造以成交量均线比、换手率、Amihud 比率与零成交天数为主。（14 条，C06–C57）
- [六、规模与价格水平](classic_library/06-size-price.md)：市值与名义价格的截面效应。构造以 log 市值与 log 价格为主；价格水平条目受本库调整价口径限制，见条目注记。（3 条，C15–C59）
- [七、隔夜与日内](classic_library/07-overnight-intraday.md)：日收益拆为隔夜段与日内段，两段的预测方向相反。构造以开盘/收盘拆分收益的累积为主。（2 条，C13–C14）
- [八、信息扩散与行业领先滞后](classic_library/08-information-diffusion.md)：信息在个股间扩散的速度差异。构造以价格延迟回归与行业内大市值股票的领先收益为主。（4 条，C60–C63）
- [九、公司行为](classic_library/09-corporate-actions.md)：股本变动所反映的公司融资行为。构造以股本增长率为主，股本由市值与价格拆分得到。（3 条，C64–C66）
- [十、WorldQuant 101 公式化 Alpha](classic_library/10-worldquant101.md)：Kakushadze (2015) 的 101 个公式化 Alpha 中按本库字段标准选入的 65 条。多为量价秩与时序算子的复合构造，主体是短周期反转与量价相关形态。（65 条，C67–C131）
- [十一、Alpha158 量价特征](classic_library/11-alpha158.md)：Qlib 内置 Alpha158 特征集中选入的 41 条：K 线形态、当日价格比与滚动统计特征。滚动特征每型一条，窗口以 20 日为代表口径（原特征族含 5/10/20/30/60 五档）。（41 条，C132–C172）
- [十二、技术指标](classic_library/12-technical-indicators.md)：经典技术指标 20 条，涵盖趋势、摆动与量能三类，构造互不相同。（20 条，C173–C192）
- [十三、OHLC 波动与价差估计量](classic_library/13-ohlc-estimators.md)：用开高低收估计波动与有效价差的计量构造 8 条。作为因子使用时方向取负（低波动、低价差、低跳跃占优）。（8 条，C193–C200）
