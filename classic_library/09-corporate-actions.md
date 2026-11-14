# 九、公司行为

股本变动所反映的公司融资行为。构造以股本增长率为主，股本由市值与价格拆分得到。

- **C64 一年净增发**：`neg(winsorize(delta(log(mktcap / close), 250)))`，股本的约 12 个月增长率取负（Pontiff & Woodgate 2008；OSAP: ShareIss1Y）
- **C65 五年净增发**：`neg(delta(log(mktcap / close), 1260))`，股本的 5 年增长率取负（Daniel & Titman 2006；OSAP: ShareIss5Y）
- **C66 综合权益发行**：`neg(delta(log(mktcap), 1260) - delta(log(close), 1260))`，5 年市值增长率减去 5 年股价涨幅（Daniel & Titman 2006；OSAP: CompEquIss）
