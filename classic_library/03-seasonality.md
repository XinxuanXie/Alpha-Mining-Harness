# 三、季节性

日历规律：历史同月收益在当月重现。构造以过去各年同月收益与非同月收益的对照为主。

- **C28 去年同月收益**：`delay(close, 252) / delay(close, 273) - 1`（Heston & Sadka 2008；OSAP: MomSeasonShort）
- **C29 同月收益·2–5 年**：`(delay(close, 504) / delay(close, 525) - 1 + delay(close, 756) / delay(close, 777) - 1 + delay(close, 1008) / delay(close, 1029) - 1 + delay(close, 1260) / delay(close, 1281) - 1) / 4`，过去第 2–5 年各同月收益的平均（Heston & Sadka 2008；OSAP: MomSeason）
- **C30 同月收益·6–10 年**：`(delay(close, 1512) / delay(close, 1533) - 1 + delay(close, 1764) / delay(close, 1785) - 1 + delay(close, 2016) / delay(close, 2037) - 1 + delay(close, 2268) / delay(close, 2289) - 1 + delay(close, 2520) / delay(close, 2541) - 1) / 5`，过去第 6–10 年各同月收益的平均（Heston & Sadka 2008；OSAP: MomSeason06YrPlus）
- **C31 同月收益·11–15 年**：`(delay(close, 2772) / delay(close, 2793) - 1 + delay(close, 3024) / delay(close, 3045) - 1 + delay(close, 3276) / delay(close, 3297) - 1 + delay(close, 3528) / delay(close, 3549) - 1 + delay(close, 3780) / delay(close, 3801) - 1) / 5`，过去第 11–15 年各同月收益的平均（Heston & Sadka 2008；OSAP: MomSeason11YrPlus）
- **C32 同月收益·16–20 年**：`(delay(close, 4032) / delay(close, 4053) - 1 + delay(close, 4284) / delay(close, 4305) - 1 + delay(close, 4536) / delay(close, 4557) - 1 + delay(close, 4788) / delay(close, 4809) - 1 + delay(close, 5040) / delay(close, 5061) - 1) / 5`，过去第 16–20 年各同月收益的平均（Heston & Sadka 2008；OSAP: MomSeason16YrPlus）
- **C33 非同月动量·近 1 年**：`(ts_sum(月收益, 12) - 去年同月月收益) / 11`，过去 1 年月收益剔除同历月项后的平均（月频口径，程序自算）（Heston & Sadka 2008；OSAP: Mom12mOffSeason）
- **C34 非同月反转·2–5 年**：`-mean(月收益, 过去第 2–5 年的非同月月份)`，第 2–5 年非同月月份的平均月收益取负（月频口径，程序自算）（Heston & Sadka 2008；OSAP: MomOffSeason）
- **C35 非同月反转·6–10 年**：`-mean(月收益, 过去第 6–10 年的非同月月份)`，构造同 C34、年份平移（月频口径，程序自算）（Heston & Sadka 2008；OSAP: MomOffSeason06YrPlus）
- **C36 非同月反转·11–15 年**：`-mean(月收益, 过去第 11–15 年的非同月月份)`，构造同 C34、年份平移（月频口径，程序自算）（Heston & Sadka 2008；OSAP: MomOffSeason11YrPlus）
- **C37 非同月反转·16–20 年**：`-mean(月收益, 过去第 16–20 年的非同月月份)`，构造同 C34、年份平移（月频口径，程序自算）（Heston & Sadka 2008；OSAP: MomOffSeason16YrPlus）
