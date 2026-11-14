# 五、流动性与换手

交易活跃度与非流动性溢价。构造以成交量均线比、换手率、Amihud 比率与零成交天数为主。

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
