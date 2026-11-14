# 三、季节性

日历规律：历史同月收益在当月重现。构造以过去各年同月收益与非同月收益的对照为主。

- **C28 去年同月收益**：`delay(close, 252) / delay(close, 273) - 1`（Heston & Sadka 2008；OSAP: MomSeasonShort）
- **C29 同月收益·2–5 年**：`(delay(close, 504) / delay(close, 525) - 1 + delay(close, 756) / delay(close, 777) - 1 + delay(close, 1008) / delay(close, 1029) - 1 + delay(close, 1260) / delay(close, 1281) - 1) / 4`，过去第 2–5 年各同月收益的平均（Heston & Sadka 2008；OSAP: MomSeason）
- **C30 同月收益·6–10 年**：过去第 6–10 年各同月收益的平均，构造同 C29、年份平移（Heston & Sadka 2008；OSAP: MomSeason06YrPlus）
- **C31 同月收益·11–15 年**：过去第 11–15 年各同月收益的平均，构造同 C29、年份平移（Heston & Sadka 2008；OSAP: MomSeason11YrPlus）
- **C32 同月收益·16–20 年**：过去第 16–20 年各同月收益的平均，构造同 C29、年份平移（Heston & Sadka 2008；OSAP: MomSeason16YrPlus）
- **C33 非同月动量·近 1 年**：过去 1 年中非同月月份的平均月收益（月收益序列口径，程序自算）（Heston & Sadka 2008；OSAP: Mom12mOffSeason）
- **C34 非同月反转·2–5 年**：过去第 2–5 年非同月月份平均月收益取负（月收益序列口径，程序自算）（Heston & Sadka 2008；OSAP: MomOffSeason）
- **C35 非同月反转·6–10 年**：过去第 6–10 年非同月月份平均月收益取负，构造同 C34、年份平移（Heston & Sadka 2008；OSAP: MomOffSeason06YrPlus）
- **C36 非同月反转·11–15 年**：过去第 11–15 年非同月月份平均月收益取负，构造同 C34、年份平移（Heston & Sadka 2008；OSAP: MomOffSeason11YrPlus）
- **C37 非同月反转·16–20 年**：过去第 16–20 年非同月月份平均月收益取负，构造同 C34、年份平移（Heston & Sadka 2008；OSAP: MomOffSeason16YrPlus）
