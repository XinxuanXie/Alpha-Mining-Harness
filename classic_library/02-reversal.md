# 二、反转

涨跌过度后的均值回归，含短期与长期两型。构造以区间收益取负为主。

- **C01 短期反转**：`-(close / delay(close, 20) - 1)`，近 1 个月涨跌取负
- **C02 长期反转**：`-(close / delay(close, 756) - 1)`，近 3 年涨跌取负
- **C26 长期反转（剔除近一年）**：`-(delay(close, 252) / delay(close, 756) - 1)`，取 t-36 至 t-13 个月收益取负（De Bondt & Thaler 1985；OSAP: LRreversal）
- **C27 中期反转**：`-(delay(close, 273) / delay(close, 378) - 1)`，取 t-18 至 t-13 个月收益取负（De Bondt & Thaler 1985；OSAP: MRreversal）
