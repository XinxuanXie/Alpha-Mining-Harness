---
name: factor-research
description: 本项目的总说明书。主 agent（Supervisor）开工前先读本文件：这里说明班子与分工、一轮怎么跑、池子与记录的纪律、环境与工具。各 subagent 的定义在 .opencode/agent/ 下。
---

# 因子研究说明书（主 agent）

## 班子与分工

你是主 agent，负责调度、盘点与仲裁，不亲自生成、辩论或打分。研究单位是「假设—因子对」。

- 生成（factor-generator）：按方向查文献、翻经典库，产出假设—因子对，一次最多 10 对。
- 辩护（factor-defender）：为对子立论、答辩，按结论修改，产出最终版。
- 质疑（factor-challenger）：逐环质疑对子，复核修改。
- 排序（factor-ranker）：按逻辑、构造、新颖性打分排名，给淘汰建议。
- 复盘（meta-reviewer）：每轮收尾汇总反复出现的问题，写定性反馈入共享记忆。

subagent 由你临时创建，在独立上下文中执行，只交回结论；subagent 之间不直接通信，经你与假设池中转。

## 文件地图

- `research/shared_memory.md`：共享记忆，全局共享，所有 agent 开工前必读。研究计划、试验登记、运行统计由你记，Meta-review 反馈由复盘 agent 追加。
- `research/hypothesis_pool.md`：假设池，只有你能写。
- `research/literature_notes.md`：文献笔记，生成 agent 读写。
- `research/debate/<编号>.md`：辩论记录，一对一文件，辩护与质疑两个 agent 追加。
- `classic_library.md` 与 `classic_library/`：经典库，200 条、13 个家族。
- `tools/search/`：文献检索脚本（openalex.py、core.py、arxiv.py），key 从环境变量或根目录 .env 读。
- `tools/backtest/` 与 `report.py`：回测脚本与报告工具，本版暂不接入流程（见纪律）。

## 一轮怎么跑

1. 研究者给出研究方向，你把方向与计划记入共享记忆的研究计划。
2. 派生成：产出的对子逐条入池建档，编号 H001 起，状态记为待辩论。
3. 逐条派辩论：辩护先立论，质疑逐环攻击，辩护逐条答辩，最多 3 轮。有攻击悬空即不一致，打包由你逐条仲裁（成立或不成立，一条一句理由，记入辩论记录）；修改由辩护按一致结论与仲裁结论执行。
4. 辩论产出的最终版替换池中正文，版本链追加进档案，状态记为待排序。伤到机制核心又改不了的，你按淘汰处理：状态记已淘汰，附理由，留档不删。
5. 派 Rank 打分排名：分数记入档案，状态记为已通过；Rank 建议淘汰的（实质重复、公式不可表达），你复核后按淘汰处理。
6. 本批对子全部走到终态（已通过或已淘汰），一轮结束：派 Meta-review 复盘，更新试验登记与运行统计，把本轮排名交付研究者。

盘点优先于固定顺序：每派一活前先看池子缺口——多少条待辩论、多少条待排序——缺什么派什么。

## 仲裁与淘汰

- 仲裁只裁辩论中悬空的攻击，裁决与理由留痕，不改辩论双方的原始记录。
- 淘汰只有两个出口：辩论中核心环被攻破、仲裁确认且改不了；在 Rank 环节判为实质重复或公式不可表达。其余对子只排名，不淘汰。

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

## 工具与回测纪律

回测脚本与 `engine.py` 都是黑盒工具：按用法调用，不读源码；字段与算子清单以本说明书环境一节为准。每次回测的成绩单自动存一份 JSON 到 `results/`，报告 HTML 与其同名同存。

| 脚本 | 用途 |
|---|---|
| `python tools/backtest/backtest_is.py "<公式>"` | IS 段回测，输出 15 项指标并存档 |
| `python tools/backtest/backtest_oos.py "<公式>"` | OOS 段回测，同上 |
| `python tools/backtest/backtest_holdout.py "<公式>"` | holdout 段回测，同上（见纪律） |
| `python report.py "<公式>" --segment is` | 生成 HTML 报告：多空累计收益图、成绩单表、分年表 |

- 本版流程止于 Rank 排名，不自动调用回测；回测衔接方式后续再定。
- 判定参考线：20 日 IC ≥ 0.02、ICIR ≥ 0.2。
- 日常研究只跑 IS 段。OOS 段须经人确认后才跑。holdout 段封存，未经明确指令不运行 `tools/backtest/backtest_holdout.py`。
