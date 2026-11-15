# 因子挖掘系统

假设驱动的单因子挖掘系统，以 LangGraph 实现。模型只负责提出假设与修改公式；回测、判定与落盘全部由程序执行。

现行规格：《因子挖掘系统方案（2026-11-15）》（`factor-system-plan-2026-11-15.md`）。本文件与该规格不一致时，以规格为准。

## 流程

一条因子对应一个 thread，状态装在单一状态对象（FactorState）中，依次经过七个节点：

1. draw_materials（程序）：随机抽 3 个经典因子家族，取全部条目原文与相关经验卡。
2. propose（Agent）：结合条目想机制，产出名称、假设、公式。假设须机制先行，写清谁付钱。
3. validate（程序）：白名单、复杂度（上限 20）、切片试算三项检查；不合格回来源节点重写，上限 2 次，满轮次直接结案。
4. backtest（程序）：训练段回测，产出 15 项成绩单，按两门判定——20 日 Rank IC ≥ 0.02、ICIR ≥ 0.2。相关门暂不启用。
5. modify（Agent）：未过门且未满 3 轮时触发。先按成绩单特征选家族，再以家族经典量 × 十种专业方法谱系产出候选，一家族一条，先审判型后增益型。候选追加队列逐条处理，总轮次上限 3（含首版），单 thread 回测总上限 13 次。
6. test_verdict（程序）：过门后自动测测试段一次，只裁决、不回改、不反号。以 run_id＋公式哈希做幂等键，重复触发返回已有裁决。
7. write_card（Agent）：因子终结时写经验卡（名称、公式、死因分类、结论），死因分类限七类。

检查点由 SqliteSaver 落盘，进程中断后按 thread_id 恢复，结果与不中断一致。

## 文件

| 文件 | 职责 |
|---|---|
| `calc.py` | 计算层：数据加载（只加载训练段）、公式求值、指标计算、白名单与复杂度检查。不调用模型。自系统建立以来未改动。 |
| `agents.py` | 模型调用层：propose、select_modify_families、modify、write_card 四个调用，统一经 call_model 走替身或保险库。 |
| `graph.py` | 状态图：FactorState、七个节点、条件边、账本读写、成绩单组装、测试段裁决。 |
| `run.py` | 入口：`--new` 新开一条因子，`--resume RUN_ID` 按检查点恢复。 |
| `test_graph_fake.py` | 替身验收：假模型＋假回测，覆盖重写回边、候选队列、过门裁决、满轮写卡、测试段幂等、检查点读回、路由上限。 |
| `classic_library.md`、`classic_library/` | 经典因子库索引与 13 个家族文件，共 200 条（C01–C200）。 |
| `records.jsonl` | 账本（程序只追加）：全部事件的唯一事实源头，成绩单与状态皆为其投影。本机文件，不入仓库。 |
| `experience_cards.jsonl` | 经验卡（程序只追加）。本机文件，不入仓库。 |
| `checkpoints.sqlite` | LangGraph 检查点。本机文件，不入仓库。 |
| `data/` | panel、securities、membership_intervals、spy_benchmark、precomp_fields、classic_values。本机文件，不入仓库。 |

## 运行

模型经保险库 DeepSeek 连接器调用，密钥不落文件。启动器在本机 `hidden_files/run_graph_with_vault.py`（不入仓库）：

```
python run_graph_with_vault.py --new              # 新开一条因子
python run_graph_with_vault.py --resume RUN_ID    # 恢复中断的 thread
```

直接运行 `run.py` 需自行保证 `agents.call_model` 可用（真实 API 或替身）。

## 数据纪律

- 训练段 2000–2016：生成、修改、回测唯一可用数据。
- 测试段 2017–2019：仅过门因子由裁决节点加载，每条因子至多测一次。
- 验证段 2020–2026：封存，任何环节不加载。
- 价格为拆股调整后价格，禁止按价格水平直接排序。
- 判定门由程序写死，Agent 无权修改；账本只追加，更正靠追加更正记录。

## 验收

```
python test_graph_fake.py
```

全绿后方可真跑。2026-11-15 已完成：替身验收全过；真跑两条因子全程（各 5 次、13 次尝试，均未过门，测试段未触发）；中断恢复实测通过（杀进程后按 thread_id 恢复，两次恢复后完整跑完）。
