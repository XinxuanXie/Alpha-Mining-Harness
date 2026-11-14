# 五、流动性与换手

交易活跃度与非流动性溢价。构造以成交量均线比、换手率、Amihud 比率、零成交天数与量能累积指标为主。

- **C06 放量**：`ts_mean(volume, 5) / ts_mean(volume, 60)`，短长均量比
- **C11 Amihud 非流动性**：`ts_mean(abs(close / delay(close, 1) - 1) / (close * volume), 20)`
- **C12 低换手**：`neg(ts_mean(volume * close / mktcap, 60))`
- **C47 成交额水平**：`neg(log(ts_mean(delay(close * volume, 42), 21)))`，滞后 2 个月的月均成交额取对数取负（Brennan, Chordia & Subrahmanyam 1998；OSAP: DolVol）
- **C48 换手率门槛**：`gt(ts_mean(volume / (mktcap / close), 63), 0.1)`，近 3 个月换手率均值高于 10% 记 1、低于 5% 记 0、中间记缺失（Datar, Naik & Radcliffe 1998；OSAP: ShareVol）
- **C49 量市值比**：`neg(ts_sum(volume / (mktcap / close), 252))`，过去 12 个月换手率之和取负（Haugen & Baker 1996；OSAP: VolMkt）
- **C50 成交量趋势**：`ts_slope(月成交量, 60) / ts_mean(月成交量, 60)`，月成交量对时间趋势回归的斜率按均量缩放（月频，程序自算）（Haugen & Baker 1996；OSAP: VolumeTrend）
- **C51 成交量波动**：`neg(过去 36 个月月成交量的标准差)`（月频，程序自算）（Chordia, Subrahmanyam & Anshuman 2001；OSAP: VolSD）
- **C52 换手率波动**：`neg(过去 36 个月换手率的标准差)`（月频，程序自算）（Chordia, Subrahmanyam & Anshuman 2001；OSAP: std_turn）
- **C53 换手率变异系数**：`neg(过去 36 个月换手率标准差 / 均值)`（月频，程序自算）（Chordia, Subrahmanyam & Anshuman 2001）
- **C54 买卖价差（高低价估计）**：`2 * (exp(α) - 1) / (1 + exp(α))`，其中 α 由连续两日高低价比的函数 β、γ 按 Corwin-Schultz 法合成（程序实现）（Amihud & Mendelson 1986；OSAP: BidAskSpread）
- **C55 零成交天数·1 月**：`ts_sum(where(gt(volume, 0), 0, 1), 21)`，近 1 个月零成交量天数（Liu 2006；OSAP: zerotrade1M）
- **C56 零成交天数·6 月**：`ts_mean(where(gt(volume, 0), 0, 1), 126)`，近 6 个月零成交天数均值（Liu 2006；OSAP: zerotrade6M）
- **C57 零成交天数·12 月**：`ts_mean(where(gt(volume, 0), 0, 1), 252)`，近 12 个月零成交天数均值（Liu 2006；OSAP: zerotrade12M）
- **C90 WQ#30 涨跌符号和×量比**：`(1 - rank(sign(close - delay(close, 1)) + sign(delay(close, 1) - delay(close, 2)) + sign(delay(close, 2) - delay(close, 3)))) * ts_sum(volume, 5) / ts_sum(volume, 20)`
- **C94 WQ#35 量秩×区间秩×收益秩**：`ts_rank(volume, 32) * (1 - ts_rank(close + high - low, 16)) * (1 - ts_rank(returns, 32))`
- **C167 量均线比 VMA**：`ts_mean(volume, 20) / volume`，均量相对当日量
- **C168 量离散 VSTD**：`ts_std(volume, 20) / volume`，成交量标准差按当日量归一
- **C170 放量占比 VSUMP**：`ts_sum(max(delta(volume, 1), 0), 20) / ts_sum(abs(delta(volume, 1)), 20)`，量增部分占量总变动之比
- **C171 缩量占比 VSUMN**：`ts_sum(max(-delta(volume, 1), 0), 20) / ts_sum(abs(delta(volume, 1)), 20)`，量减部分占量总变动之比
- **C172 净量变占比 VSUMD**：`(ts_sum(max(delta(volume, 1), 0), 20) - ts_sum(max(-delta(volume, 1), 0), 20)) / ts_sum(abs(delta(volume, 1)), 20)`，量增与量减之差占量总变动之比
- **C178 能量潮斜率 OBV**：`(OBV - delay(OBV, 20)) / ts_sum(volume, 20)`，其中 OBV = ts_cumsum(sign(delta(close, 1)) * volume) 为涨日加量、跌日减量的累积量（Granville 1963；OBV 为程序自算）
- **C184 蔡金资金流**：`ts_sum(((close - low) - (high - close)) / (high - low) * volume, 20) / ts_sum(volume, 20)`（Chaikin 1985），收盘位置加权的量占比
- **C186 强力指数**：`(close - delay(close, 1)) * volume` 的 13 日指数平滑（Elder 1993；程序自算）
