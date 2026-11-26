# 第 5 轮启动 prompt（基本面方向）

> 用法：粘贴到 opencode 主会话（Supervisor）。本轮按 SKILL.md 正常流程走，方向是基本面。

## 方向

第 5 轮，基本面方向。10 个 EDGAR 基本面字段已进引擎（`data/fundamentals.parquet`，20 个字段全加载），IS 2010–2016（基本面有效窗口从 2009 年中开始，2000–2009 年对基本面因子是空的）。

## Step 0 检查（先做，不跳过）

按 SKILL.md Step 0，对每个候选方向核查 20 日横截面全文锚点与证据—评价匹配。特别注意：**基本面经典文献多为月频证据**，需判断月频证据是否支撑 20 日评价；过不了就换方向，不硬上。

## 候选机制线（2–3 条，每条 1 篇文献，Supervisor 定）

1. **价值**：账面市值比 `book_equity / mktcap`（Fama & French 1992/1993）。
2. **盈利**：ROE `net_income / book_equity` 或 ROA `net_income / total_assets`（Fama & French 2015 RMW；Novy-Marx 2013 毛利能力需 COGS，本数据无 COGS，改用净利口径）。
3. **投资**：资产增速 `delta(log(total_assets))`（Cooper, Gulen & Schill 2008；Fama & French 2015 CMA）。
4. **备选：研发强度** `rnd / revenue` 或 `rnd / total_assets`（Chan, Lakonishok & Sougiannis 2001）。注意 rnd 约 13% 的季度是全年总数（见 SKILL.md 字段口径），作季度流量用时慎用。

生成器按机制—公式合同写最终公式；每线 ≤4 对。

## 数据口径（按 SKILL.md 字段定义）

- 有效窗口 2009 年中起；429 只未映射票的基本面全为 NaN；op_income 口径问题（XOM 为 0）暂不修；basis 清单未进 parquet，rnd 警告以 SKILL.md 为准。
- 基线已是 v3（C21/C82/C30/C169/C47/C58/C14/C95/C66/C79/C158/C81/C106），零分布是新窗口（IS 2010–2016）重算的；C01 新窗口基准：20 日 IC 0.0026、全库百分位 48.7%。

## 流程

按 SKILL.md Step 1–7 正常走：文献 corpus-first 分配、初筛、辩论（≤2 轮）、仲裁、回测（IS 2010–2016）、复盘。round_summaries 与 status.md 按输出优化补丁的要求更新。
