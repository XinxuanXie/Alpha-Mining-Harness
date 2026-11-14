# 一、动量

过去中期收益的延续效应。构造以跳过最近月的区间收益、距 52 周高点距离、行业累积收益与价格在自身历史中的位置为主。

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
- **C22 趋势因子**：`mean over 窗口对 (s, l) of sign(ts_mean(close, s) / ts_mean(close, l) - 1) * (close / delay(close, l) - 1)`，多组长短均线比的趋势信号合成（Han, Zhou & Zhu 2016；OSAP: TrendFactor）
- **C23 高量动量**：`(delay(close, 21) / delay(close, 147) - 1) * gt(rank(ts_mean(volume * close / mktcap, 60)), 0.67)`，6 月动量只在换手率最高组内赋值（Lee & Swaminathan 2000；OSAP: MomVol）
- **C24 动量×长期反转组合**：`gt(rank(delay(close, 21) / delay(close, 147) - 1), 0.8) * gt(rank(-(close / delay(close, 756) - 1)), 0.8) - gt(rank(-(delay(close, 21) / delay(close, 147) - 1)), 0.8) * gt(rank(close / delay(close, 756) - 1), 0.8)`，短期赢家且长期输家记 1、反之记 -1（Chan & Ko 2006；OSAP: MomRev）
- **C25 年轻股动量**：`where(上市月数处于截面最短五分位, delay(close, 21) / delay(close, 147) - 1, 缺失)`，6 月动量只在上市时长最短五分位内取值，上市月数为个股在面板中首次出现以来的月数（程序自算）（Zhang 2006；OSAP: FirmAgeMom）
- **C73 WQ#8 开盘收益乘积动量**：`-1 * rank((ts_sum(open, 5) * ts_sum(returns, 5)) - delay(ts_sum(open, 5) * ts_sum(returns, 5), 10))`
- **C103 WQ#52 低点抬升×长动量×量秩**：`((-1 * ts_min(low, 5)) + delay(ts_min(low, 5), 5)) * rank((ts_sum(returns, 240) - ts_sum(returns, 20)) / 220) * ts_rank(volume, 5)`
- **C144 变化率 ROC**：`delay(close, 20) / close`，20 日前价格与现价之比（Qlib 原定义）
- **C150 最高比 MAX**：`ts_max(high, 20) / close`，窗口最高价相对现价
- **C151 最低比 MIN**：`ts_min(low, 20) / close`，窗口最低价相对现价
- **C152 上分位 QTLU**：`ts_quantile(close, 20, 0.8) / close`，价格 80% 分位相对现价（程序自算）
- **C153 下分位 QTLD**：`ts_quantile(close, 20, 0.2) / close`，价格 20% 分位相对现价（程序自算）
- **C154 时序分位 RANK**：`ts_rank(close, 20)`，现价在过去 20 日中的分位
- **C161 上涨日占比 CNTP**：`ts_mean(gt(close, delay(close, 1)), 20)`，窗口内上涨日比例
- **C162 下跌日占比 CNTN**：`ts_mean(gt(delay(close, 1), close), 20)`，窗口内下跌日比例
- **C163 涨跌日差 CNTD**：`ts_mean(gt(close, delay(close, 1)), 20) - ts_mean(gt(delay(close, 1), close), 20)`，上涨日占比减去下跌日占比
