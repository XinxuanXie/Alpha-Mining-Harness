# 八、信息扩散与行业领先滞后

信息在个股间扩散的速度差异。构造以价格延迟回归、滞后相关与行业内大市值股票的领先收益为主。

- **C60 价格延迟·R²版**：`1 - R²(受限模型) / R²(完整模型)`，完整模型为个股收益对市场收益当期及滞后 1–4 期回归、受限模型只含当期项（程序预计算）（Hou & Moskowitz 2005；OSAP: PriceDelayRsq）
- **C61 价格延迟·系数版**：`(1*|β1| + 2*|β2| + 3*|β3| + 4*|β4|) / (|β0| + |β1| + |β2| + |β3| + |β4|)`，β 为 C60 完整模型各期系数（程序预计算）（Hou & Moskowitz 2005；OSAP: PriceDelaySlope）
- **C62 价格延迟·显著性版**：`(1*|t1| + 2*|t2| + 3*|t3| + 4*|t4|) / (|t0| + |t1| + |t2| + |t3| + |t4|)`，t 为 C60 完整模型各期系数的 t 值（程序预计算）（Hou & Moskowitz 2005；OSAP: PriceDelayTstat）
- **C63 行业大票收益**：`赋给行业内其余股票的同业市值前 30% 股票上期平均收益 = sector_big_mean(delay(returns, 1))`（程序自算）（Hou 2007；OSAP: IndRetBig）
- **C95 WQ#37 隔夜日内相关＋日内**：`rank(ts_corr(delay(open - close, 1), close, 200)) + rank(open - close)`
