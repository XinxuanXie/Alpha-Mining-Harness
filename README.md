# Alpha-Mining-Harness — 单因子研究

一套给通用 Agent 用的因子研究环境：说明书（SKILL）＋两个 skill（生成因子、修改因子）＋回测工具，在标普 500 历史成分股的日频价量数据上做单因子研究。Agent 负责提出假设、写公式、解读成绩单；脚本只负责计算，不做判定。


## Install with opencode (recommended)

opencode 本体不在本仓库内，需先安装：有 Node.js 的环境（Windows / macOS / Linux 通用）运行 `npm install -g opencode-ai`；也可以用各系统的包管理器（Windows 的 scoop / choco、macOS 的 brew）。装好并连上模型（如 DeepSeek）后，把下面整段粘贴给它：

```
You are installing the Alpha-Mining-Harness factor research skill.

Do the following, then print a checklist table (OK / FAIL):
1) Ensure git and python (>=3.10) exist. Install the Python packages:
   pip install -r requirements.txt
2) Clone or update the repo into the working folder:
   git clone https://github.com/sun97956/Alpha-Mining-Harness.git
   (if it already exists, git pull instead)
3) Arrange the files for opencode:
   - Copy SKILL.md to AGENTS.md in the project root (always-on instructions).
   - Copy skills/generate-factor and skills/modify-factor into .opencode/skills/
     so each sits at .opencode/skills/<name>/SKILL.md.
4) Data is NOT in the git repo. Download the four parquet files from the repo's
   Release (tag: data) into data/: panel.parquet, securities.parquet,
   membership_intervals.parquet, spy_benchmark.parquet. See the Data section below.
5) Quick check (training segment only):
   python backtest_train.py "-(close / delay(close, 20) - 1)"
   Expected: 20日IC 0.0115, ICIR 0.075, and a JSON saved under results/.

Print versions and pass/fail for each step. Stop after the checklist.
```

Manual fallback: clone the repo, run `pip install -r requirements.txt`, do step 3 and 4 by hand, run the quick check in step 5.

## Data

数据文件不进 git 仓库，以 Release 附件分发：到仓库的 Releases 页下载 tag `data` 的四个文件，放进项目根目录的 `data/` 文件夹。

| 文件 | 内容与用途 |
|---|---|
| `panel.parquet` | 行情主表：1,195 只标普 500 历史成分股，2000-01-03 至 2026-09-30，日频开、高、低、收、成交量、总市值。engine.py 读入后按字段拆成宽表，是全部计算的原料 |
| `securities.parquet` | 每只股票的 GICS 行业分类，供行业内排名与行业均值使用 |
| `membership_intervals.parquet` | 每只股票进出标普 500 的起止日期。加载时按它过滤，股票只在成分期内有值 |
| `spy_benchmark.parquet` | 每日市场收益，公式中的 mktret 来自这里 |

口径与生成物：

- 价格为拆股调整后价格。
- `data/precomp_fields.parquet` 是程序自动生成的缓存（ivol20、resid_ret 两个自算字段），首次运行时生成，不用下载；删掉后会自动重建。

## Discipline

- 日常研究只跑训练段（`backtest_train.py`）。
- 测试段（`backtest_test.py`）须经人确认后才跑。
- 验证段封存：未经明确指令，不运行 `backtest_verify.py`。
- 判定参考线：20 日 IC ≥ 0.02、ICIR ≥ 0.2。

## Files

| File | Role |
|---|---|
| `SKILL.md` | 总说明书：任务、环境、工具、纪律 |
| `skills/generate-factor/SKILL.md` | 生成因子：读资料 → 假设 → 公式 → 回测 → 建议 |
| `skills/modify-factor/SKILL.md` | 修改因子：诊断 → 选一种方法 → 改一条 → 新旧对比 |
| `engine.py` | 计算引擎：读数据、公式求值（33 个算子）、白名单检查 |
| `backtest_train.py` / `backtest_test.py` / `backtest_verify.py` | 三个回测脚本，各管一段，指标在脚本内计算，结果存入 `results/` |
| `report.py` | 单文件 HTML 报告：多空累计收益图、指标表、分年表 |
| `requirements.txt` | Python 依赖清单（pandas、numpy、pyarrow），`pip install -r requirements.txt` 安装 |
| `classic_library.md` + `classic_library/` | 经典因子库索引与原文：200 条，13 个家族 |
| `data/` | 数据文件（见上 Data 一节，从 Release 下载，不在仓库内） |
