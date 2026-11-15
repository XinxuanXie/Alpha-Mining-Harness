# Alpha-Mining-Harness — 单因子研究

一套给通用 Agent 用的因子研究环境：说明书（SKILL）＋两个 skill（生成因子、修改因子）＋回测工具，在标普 500 历史成分股的日频价量数据上做单因子研究。Agent 负责提出假设、写公式、解读成绩单；脚本只负责计算，不做判定。

**Repo:** https://github.com/sun97956/Alpha-Mining-Harness

## Install with opencode (recommended)

After `opencode` works with DeepSeek, paste this whole prompt:

```
You are installing the Alpha-Mining-Harness factor research skill.

Do the following, then print a checklist table (OK / FAIL):
1) Ensure git and python (>=3.10) exist, with pandas, numpy, pyarrow installed.
2) Clone or update the repo into the working folder:
   git clone https://github.com/sun97956/Alpha-Mining-Harness.git
   (if it already exists, git pull instead)
3) Arrange the files for opencode:
   - Copy SKILL.md to AGENTS.md in the project root (always-on instructions).
   - Copy skills/generate-factor and skills/modify-factor into .opencode/skills/
     so each sits at .opencode/skills/<name>/SKILL.md.
4) Data is NOT in the repo. Ensure data/ contains panel.parquet, securities.parquet,
   membership_intervals.parquet, spy_benchmark.parquet (ask the user where they are
   if missing; do not download data from the internet).
5) Quick check (training segment only):
   python backtest_train.py "-(close / delay(close, 20) - 1)"
   Expected: 20日IC 0.0115, ICIR 0.075, and a JSON saved under results/.

Print versions and pass/fail for each step. Stop after the checklist.
```

Manual fallback: clone the repo, do step 3 and 4 by hand, run the quick check in step 5.

## Discipline

- 日常研究只跑训练段（`backtest_train.py`）。
- 测试段（`backtest_test.py`）须经人确认后才跑。
- 验证段封存：未经明确指令，不运行 `backtest_verify.py`。
- 判定参考线：20 日 IC ≥ 0.02、ICIR ≥ 0.2。

## Files

| File | Role |
|---|---|
| `SKILL.md` | 总说明书：任务、环境、工具、纪律（接入时复制为 `AGENTS.md`） |
| `skills/generate-factor/SKILL.md` | 生成因子：读资料 → 假设 → 公式 → 回测 → 建议 |
| `skills/modify-factor/SKILL.md` | 修改因子：诊断 → 选一种方法 → 改一条 → 新旧对比 |
| `calc.py` | 计算引擎：公式求值（33 个算子）与 15 项成绩单 |
| `backtest_train.py` / `backtest_test.py` / `backtest_verify.py` | 三段回测，结构相同，成绩单存入 `results/` |
| `report.py` | 单文件 HTML 报告：多空累计收益图、成绩单表、分年表 |
| `classic_library.md` + `classic_library/` | 经典因子库索引与原文：200 条，13 个家族 |
| `data/` | 行情面板、股票档案、成分区间、市场基准（不在仓库内） |
