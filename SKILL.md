---
name: factor-research
description: 本项目的总说明书。进入项目开始因子研究工作前先读本文件：这里说明任务、环境（数据、算子、经典库）、工具与纪律；具体的生成与修改流程在 skills/ 下的两个 skill 里。
---

# 因子研究说明书

## 任务

在本项目中协助做单因子研究：根据指令生成因子、修改因子、运行回测、解读成绩单并给出建议。生成因子按 `skills/generate-factor/SKILL.md` 执行，修改因子按 `skills/modify-factor/SKILL.md` 执行，OOS 段验证按 `skills/oos-factor/SKILL.md` 执行（仅在用户明确要求时）。

开始工作前先读 `alpha_research_memory.md`（研究记忆），了解此前研究过的因子与留下的经验，避免重复已走过的路。

## 环境

### 数据

- 行情面板 `data/panel.parquet`：1,195 只标普 500 历史成分股，2000-01-03 至 2026-09-30，日频。每只股票每天有开、高、低、收、成交量、总市值。价格为拆股调整后价格。
- 股票档案 `data/securities.parquet`：每只股票的 GICS 行业分类，供行业内排名与行业均值使用。
- 成分区间 `data/membership_intervals.parquet`：每只股票进出标普 500 的起止日期。加载时按它过滤，股票只在成分期内有值。
- 市场基准 `data/spy_benchmark.parquet`：每日市场收益，公式中的 mktret 来自这里。
- 程序自算字段：ivol20（20 日特质波动）、resid_ret（当日残差收益），加载时由 engine.py 算出。

公式可用的字段共 9 个：open、high、low、close、volume、mktcap、mktret、ivol20、resid_ret。

数据分三段：IS 段 2000–2016、OOS 段 2017–2019、holdout 段 2020–2026。

### 算子

共 33 个，另有四则运算。公式只能用下面列出的算子与上面的 9 个字段。

- 时序（17）：delay、delta、ts_mean、ts_sum、ts_std、ts_min、ts_max、ts_rank、ts_median、ts_skew、ts_kurt、ts_decay、ts_count、ts_argmax、ts_argmin、ts_corr、ts_beta
- 截面（6）：rank、rank_sector、sector_mean、zscore、winsorize、resid
- 变换（8）：neg、abs、log、sign、sqrt、inverse、power、signed_power
- 条件（2）：gt、where

### 经典库

200 条经典因子，13 个家族。索引在 `classic_library.md`，条目原文在 `classic_library/` 下，一家族一文件。

### 回测存档

每次回测的成绩单自动存一份 JSON 到 `results/` 目录，文件名含数据段与时间，内容为公式与 15 项成绩单数字。查阅历史结果、做新旧对比时从那里取。报告 HTML 与其成绩单 JSON 同名、同存 `results/` 目录（同公式同段有多份时对应最新一份）。

### 研究记忆

`alpha_research_memory.md` 是本项目的研究记忆：一轮生成或修改结束后，只记本轮挑中的一条，一张卡三项（假设由来、因子公式、经验）。记卡的动作写在生成与修改两个 skill 的收尾步骤里。只记 IS 段的结果与认识，OOS 段与 holdout 段不记。


## 工具

| 脚本 | 用途 |
|---|---|
| `python tools/backtest/backtest_is.py "<公式>"` | IS 段回测，输出 15 项指标并存档 |
| `python tools/backtest/backtest_oos.py "<公式>"` | OOS 段回测，同上 |
| `python tools/backtest/backtest_holdout.py "<公式>"` | holdout 段回测，同上（见纪律） |
| `python report.py "<公式>" --segment is` | 生成 HTML 报告：多空累计收益图、成绩单表、分年表 |

以上脚本与 `engine.py` 都是黑盒工具：按表中用法调用即可，不读它们的源码；字段与算子清单以本说明书环境一节为准。

## 纪律

- 判定参考线：20 日 IC ≥ 0.02、ICIR ≥ 0.2。
- 日常研究只跑 IS 段。OOS 段须经人确认后才跑。holdout 段封存，未经明确指令不运行 `tools/backtest/backtest_holdout.py`。
