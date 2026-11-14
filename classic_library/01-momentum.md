# 一、动量

过去中期收益的延续效应。构造以跳过最近月的区间收益、距 52 周高点距离与行业累积收益为主。

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
