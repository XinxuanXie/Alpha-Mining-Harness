# check_fundamentals_load.py — 验证 load_wide() 真实加载基本面字段
# 用法（在 AMH 仓库根目录，即 engine.py 所在目录）：
#   python3 check_fundamentals_load.py
# 看“成分内”那列：2009 年各字段约 13-20%，2012 年约 54-70%，2016 年约 63-79%
# （研发约 31%）；2000-2008 年为 0（EDGAR 数据按披露日期从 2009 年中才有）。
# “全部列”是分母为全部 1131 只票的口径，会低很多，只作参考。
# 若某字段成分内全为 0，说明 data/fundamentals.parquet 没加载或掩码有问题。

import engine

wide = engine.load_wide()
print("已加载字段数：", len(wide))
print("基本面字段：", engine.FUND_FIELDS)
in_index = wide["close"].notna()
for f in engine.FUND_FIELDS:
    w = wide[f]
    raw = w.notna().mean(axis=1).groupby(w.index.year).mean()
    cov = ((w.notna() & in_index).sum(axis=1) / in_index.sum(axis=1)).groupby(w.index.year).mean()
    print(f"{f}: 全部列 2009 {raw.get(2009, 0):.3f} / 2012 {raw.get(2012, 0):.3f} / 2016 {raw.get(2016, 0):.3f} | "
          f"成分内 2009 {cov.get(2009, 0):.3f} / 2012 {cov.get(2012, 0):.3f} / 2016 {cov.get(2016, 0):.3f}")
