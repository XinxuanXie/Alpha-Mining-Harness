# 七、隔夜与日内

日收益拆为隔夜段与日内段，两段的预测方向相反。构造以开盘/收盘拆分收益与开盘相对前日价格的位置为主。

- **C13 隔夜累积**：`ts_sum(open / delay(close, 1) - 1, 20)`，20 日隔夜收益之和
- **C14 日内累积取负**：`neg(ts_sum(close / open - 1, 20))`，20 日日内收益之和取负
- **C83 WQ#20 开盘对前日三价差**：`(-1 * rank(open - delay(high, 1))) * rank(open - delay(close, 1)) * rank(open - delay(low, 1))`
- **C131 WQ#101 日内收益归一**：`(close - open) / (high - low + 0.001)`，当日涨跌幅占日内振幅之比
