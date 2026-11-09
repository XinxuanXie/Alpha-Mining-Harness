# calc.py — 计算与记录
# 职责：读数据、按表达式算因子值、算判定指标组、读写记录文件。
# 本文件不调用模型。运行顺序自上而下：参数 → 读数据 → 算公式 → 算 IC → 记录 → 自检。

import ast
import json
import os

import numpy as np
import pandas as pd

# ============================================================
# 参数（本文件内部固定值；运行参数在 run.py）
# ============================================================
DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "panel.parquet")
SEC_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "securities.parquet")
MEMB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "membership_intervals.parquet")
BENCH_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "spy_benchmark.parquet")
CLASSIC_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "classic_values.parquet")
TRAIN_END = "2016-12-31"   # 只加载训练段，验证段与测试段不加载
ID_COL = "permno"          # 股票标识列
FIELDS = ["open", "high", "low", "close", "volume", "mktcap", "mktret"]  # 公式可用的字段（mktret 为市场收益，见 load_wide）
MIN_STOCKS = 10            # 当日参与 IC 计算的股票少于此数，当日 IC 记缺失
SECTOR_OF = {}             # permno（int）→ GICS 行业名；load_wide 时填充，供 rank_sector 与分行业 IC 使用

# ============================================================
# 读数据：把行情表按字段拆成宽表（行=交易日，列=股票）
# ============================================================
def load_wide():
    df = pd.read_parquet(DATA_PATH, filters=[("date", "<=", pd.Timestamp(TRAIN_END))])
    df = df.sort_values(["date", ID_COL])
    wide = {}
    for f in FIELDS:
        if f == "mktret":
            continue
        wide[f] = df.pivot(index="date", columns=ID_COL, values=f)
    close = wide["close"]
    # 成分口径：只保留落在 S&P 500 成分区间内的股票-日，区间外一律置缺失，不参与任何计算
    memb = pd.read_parquet(MEMB_PATH)
    by_permno = {int(p): g for p, g in memb.groupby(ID_COL)}
    mask = pd.DataFrame(False, index=close.index, columns=close.columns)
    for col in close.columns:
        g = by_permno.get(int(col))
        if g is None:
            continue
        inside = pd.Series(False, index=close.index)
        for s, e in zip(g["start_date"], g["end_date"]):
            end = pd.Timestamp.max.normalize() if pd.isna(e) else e
            inside |= (close.index >= s) & (close.index <= end)
        mask[col] = inside
    for f in ("open", "high", "low", "close", "volume", "mktcap"):
        wide[f] = wide[f].where(mask)
    # 市场收益：基准表的市值加权市场日收益（vwretd），同一日对全体股票相同，广播成宽表
    bench = pd.read_parquet(BENCH_PATH, filters=[("date", "<=", pd.Timestamp(TRAIN_END))])
    mkt = bench.set_index("date")["vwretd"].reindex(close.index)
    wide["mktret"] = pd.DataFrame(
        np.repeat(mkt.to_numpy()[:, None], len(close.columns), axis=1),
        index=close.index, columns=close.columns)
    # 行业分类：证券表的 GICS 行业名（最新分类，静态），按 permno 记入全局表
    sec = pd.read_parquet(SEC_PATH)
    SECTOR_OF.clear()
    for permno, name in zip(sec[ID_COL], sec["sector_name"]):
        if isinstance(name, str) and name:
            SECTOR_OF[int(permno)] = name
    return wide

# ============================================================
# 算公式：表达式只能用 spec 算子清单中的算子与六个字段
# 求值结果：一张宽表（行=交易日，列=股票），或一个常数
# 缺失规则：任一算子所需位置输入缺失，输出缺失；时序窗口缺一日，输出缺失
# ============================================================
def _rank_cs(x):
    # 截面排名：(名次-1)/(股票数-1)，并列取平均名次，缺失不参与
    # 注意：除以逐日股票数时必须按行对齐（axis=0），否则会对齐到列上得到全空
    n = x.notna().sum(axis=1)
    r = x.rank(axis=1, method="average")
    out = (r - 1).div(n - 1, axis=0)
    return out.where(n >= 2)

def _ts_rank(x, d):
    # 时序排名：当日值在最近 d 日中的名次，(名次-1)/(d-1)，并列按平均名次折算
    # score = 比当日值小的个数 + 并列个数的一半，即 (平均名次 - 1)
    score = pd.DataFrame(0.0, index=x.index, columns=x.columns)
    valid = x.notna().rolling(d, min_periods=d).sum() == d
    for j in range(1, d):
        prev = x.shift(j)
        score = score + (prev < x).astype(float) + 0.5 * (prev == x).astype(float)
    out = score / (d - 1)
    return out.where(valid)

def _ts_corr(x, y, d):
    out = x.rolling(d, min_periods=d).corr(y)
    valid = (x.notna() & y.notna()).rolling(d, min_periods=d).sum() == d
    return out.where(valid)

def _gt(a, b):
    # 比较：a > b 取 1，否则取 0；任一输入缺失则输出缺失（常数视为不缺失）
    out = (a > b) * 1.0
    mask = a.notna() if hasattr(a, "notna") else None
    if hasattr(b, "notna"):
        mask = b.notna() if mask is None else mask & b.notna()
    return out.where(mask) if mask is not None and hasattr(out, "where") else out

def _rank_sector(x):
    # 当日同行业内排名，口径同 rank（(名次-1)/(组内股票数-1)）；无行业分类的股票输出缺失
    if not SECTOR_OF:
        raise ValueError("行业数据不可用，无法使用 rank_sector")
    out = pd.DataFrame(np.nan, index=x.index, columns=x.columns)
    names = {SECTOR_OF.get(int(c)) for c in x.columns} - {None}
    for name in names:
        cols = [c for c in x.columns if SECTOR_OF.get(int(c)) == name]
        out[cols] = _rank_cs(x[cols])
    return out

OPS = {
    "neg": lambda a: -a,
    "abs": lambda a: a.abs() if hasattr(a, "abs") else abs(a),
    "log": lambda a: np.log(a.where(a > 0) if hasattr(a, "where") else a),
    "rank": _rank_cs,
    "rank_sector": _rank_sector,
    "gt": _gt,
    "delay": lambda a, d: a.shift(d),
    "delta": lambda a, d: a - a.shift(d),
    "ts_mean": lambda a, d: a.rolling(d, min_periods=d).mean(),
    "ts_sum": lambda a, d: a.rolling(d, min_periods=d).sum(),
    "ts_std": lambda a, d: a.rolling(d, min_periods=d).std(),
    "ts_min": lambda a, d: a.rolling(d, min_periods=d).min(),
    "ts_max": lambda a, d: a.rolling(d, min_periods=d).max(),
    "ts_rank": _ts_rank,
    "ts_corr": _ts_corr,
}
WINDOW_OPS = {"delay", "delta", "ts_mean", "ts_sum", "ts_std", "ts_min", "ts_max", "ts_rank", "ts_corr"}

def _eval(node, wide):
    if isinstance(node, ast.Expression):
        return _eval(node.body, wide)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return float(node.value)
        raise ValueError(f"不支持的常数：{node.value!r}")
    if isinstance(node, ast.Name):
        if node.id in FIELDS:
            return wide[node.id]
        raise ValueError(f"不允许的字段名：{node.id}")
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_eval(node.operand, wide)
    if isinstance(node, ast.BinOp):
        a = _eval(node.left, wide)
        b = _eval(node.right, wide)
        if isinstance(node.op, ast.Add):
            return a + b
        if isinstance(node.op, ast.Sub):
            return a - b
        if isinstance(node.op, ast.Mult):
            return a * b
        if isinstance(node.op, ast.Div):
            out = a / b
            if hasattr(out, "replace"):
                out = out.replace([np.inf, -np.inf], np.nan)
            return out
        raise ValueError("只允许 + - * / 四种运算")
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in OPS:
            raise ValueError(f"不允许的算子：{ast.dump(node.func)[:40]}")
        name = node.func.id
        arity = {"neg": 1, "abs": 1, "log": 1, "rank": 1, "rank_sector": 1, "ts_corr": 3}.get(name, 2)
        if len(node.args) != arity:
            raise ValueError(f"算子 {name} 需要 {arity} 个参数，给了 {len(node.args)} 个")
        args = [_eval(a, wide) for a in node.args]
        if name in WINDOW_OPS:
            d = args[-1]
            if not isinstance(d, float) or d < 1 or d != int(d):
                raise ValueError(f"算子 {name} 的窗口 d 必须是正整数")
            args[-1] = int(d)
        return OPS[name](*args)
    raise ValueError(f"不支持的表达式结构：{type(node).__name__}")

def eval_formula(expr, wide):
    """把一条表达式字符串算成因子宽表；不合法时抛 ValueError 并说明原因。"""
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as e:
        raise ValueError(f"表达式语法错误：{e.msg}")
    try:
        out = _eval(tree, wide)
    except TypeError as e:
        raise ValueError(f"公式结构错误：{e}")
    if not isinstance(out, pd.DataFrame):
        raise ValueError("公式结果必须是随股票与日期变化的数值，不能是常数")
    return out

# ============================================================
# 算指标：判定数字是一组指标（构成与口径见 spec「判定指标」）
# 基础量为日 IC（截面 Spearman 相关）；标签：close(t+1+h)/close(t+1)-1
# ============================================================
def _label(close, h):
    return close.shift(-(1 + h)) / close.shift(-1) - 1

def _ic_series(factor, label):
    """逐日截面 Spearman 相关，返回去掉缺失日的日 IC 序列。"""
    fr = factor.rank(axis=1, method="average")
    lr = label.rank(axis=1, method="average")
    mask = fr.notna() & lr.notna()
    f = fr.where(mask).fillna(0.0)
    l = lr.where(mask).fillna(0.0)
    n = mask.sum(axis=1).astype(float)
    sx, sy = f.sum(axis=1), l.sum(axis=1)
    sxx, syy = (f * f).sum(axis=1), (l * l).sum(axis=1)
    sxy = (f * l).sum(axis=1)
    cov = sxy - sx * sy / n
    var_x = sxx - sx * sx / n
    var_y = syy - sy * sy / n
    denom = np.sqrt(var_x * var_y)
    daily = (cov / denom).where((n >= MIN_STOCKS) & (var_x > 0) & (var_y > 0))
    return daily.dropna()

def _mean_or_none(series):
    return None if len(series) == 0 else float(series.mean())

def compute_ic_mean(factor, close, h):
    return _mean_or_none(_ic_series(factor, _label(close, h)))

def compute_metrics(factor, wide, h=5, passed_values=(), classic_values=()):
    """一次算出 spec 的全部指标，返回字典；算不出的指标记 None。"""
    close = wide["close"]
    label = _label(close, h)
    daily = _ic_series(factor, label)
    ic_mean = _mean_or_none(daily)
    sd = float(daily.std()) if len(daily) >= 2 else None
    icir = float(ic_mean / sd) if (ic_mean is not None and sd) else None
    t_val = float(ic_mean / (sd / np.sqrt(len(daily)))) if (ic_mean is not None and sd) else None

    by_h = {}
    for hh in (1, 5, 10, 20, 60):
        by_h[str(hh)] = ic_mean if hh == h else _mean_or_none(_ic_series(factor, _label(close, hh)))
    by_year = {str(y): float(v) for y, v in daily.groupby(daily.index.year).mean().items()}

    pct = wide["mktcap"].rank(axis=1, pct=True)
    by_cap = {}
    for name, m in (("小", pct <= 1 / 3), ("中", (pct > 1 / 3) & (pct <= 2 / 3)), ("大", pct > 2 / 3)):
        by_cap[name] = _mean_or_none(_ic_series(factor.where(m), label))

    by_sector = {}
    if SECTOR_OF:
        for name in sorted({SECTOR_OF.get(int(c)) for c in factor.columns} - {None}):
            cols = [c for c in factor.columns if SECTOR_OF.get(int(c)) == name]
            by_sector[name] = _mean_or_none(_ic_series(factor[cols], label[cols]))

    fpct = factor.rank(axis=1, pct=True)
    quintile = []
    for k in range(5):
        m = (fpct > k / 5) & (fpct <= (k + 1) / 5) & factor.notna()
        quintile.append(_mean_or_none(label.where(m).mean(axis=1).dropna()))
    long_short = (quintile[4] - quintile[0]) if (quintile[0] is not None and quintile[4] is not None) else None

    coverage = float((factor.notna() & close.notna()).sum().sum() / close.notna().sum().sum())
    turnover = float((_rank_cs(factor) - _rank_cs(factor).shift(1)).abs().mean(axis=1).mean())

    max_corr = None
    for pv in passed_values:
        c = _mean_or_none(_ic_series(factor, pv))
        if c is not None:
            max_corr = abs(c) if max_corr is None else max(max_corr, abs(c))

    classic_corr = None
    for cv in classic_values:
        c = _mean_or_none(_ic_series(factor, cv))
        if c is not None:
            classic_corr = abs(c) if classic_corr is None else max(classic_corr, abs(c))

    return {
        "IC均值": ic_mean, "ICIR": icir, "t值": t_val,
        "各持有期IC": by_h, "分年IC": by_year, "分市值组IC": by_cap, "分行业IC": by_sector,
        "五分组收益": quintile, "多空收益": long_short,
        "覆盖率": coverage, "换手": turnover,
        "与已通过因子最大相关": max_corr,
        "与经典因子最大相关": classic_corr,
    }

def judge(ic_mean, threshold, icir=None, icir_threshold=None, classic_corr=None, corr_threshold=None):
    """过门判定：Rank IC 均值、ICIR、与经典因子最大相关三道门同时满足才通过；任一缺失或不过记不通过。"""
    if ic_mean is None or ic_mean < threshold:
        return False
    if icir_threshold is not None and (icir is None or icir < icir_threshold):
        return False
    if corr_threshold is not None and classic_corr is not None and classic_corr >= corr_threshold:
        return False
    return True

# ============================================================
# 经典因子值表：16 条经典因子的因子值存成一张长表（date、permno、C01…C16），
# 供相关性判定反复读取，不必每次运行重新计算
# 公式只存于程序一侧（相关性参照），不喂给假设 Agent——喂公式会被照抄（2026-11-09 验收跑实测）
# ============================================================
CLASSIC_FORMULAS = [
    "-(close / delay(close, 20) - 1)",
    "-(close / delay(close, 756) - 1)",
    "delay(close, 21) / delay(close, 252) - 1",
    "close / ts_max(close, 252)",
    "abs(close / delay(close, 252) - 1) * (ts_mean(gt(close / delay(close, 1) - 1, 0), 252) - ts_mean(gt(0, close / delay(close, 1) - 1), 252))",
    "ts_mean(volume, 5) / ts_mean(volume, 60)",
    "(delay(close, 21) / delay(close, 252) - 1) * (1 - rank(ts_mean(volume * close / mktcap, 60)))",
    "neg(ts_std(close / delay(close, 1) - 1, 60))",
    "neg(ts_max(close / delay(close, 1) - 1, 20))",
    "neg(ts_corr(close / delay(close, 1) - 1, mktret, 252) * ts_std(close / delay(close, 1) - 1, 252) / ts_std(mktret, 252))",
    "ts_mean(abs(close / delay(close, 1) - 1) / (close * volume), 20)",
    "neg(ts_mean(volume * close / mktcap, 60))",
    "ts_sum(open / delay(close, 1) - 1, 20)",
    "neg(ts_sum(close / open - 1, 20))",
    "neg(log(mktcap))",
    "delay(close, 232) / delay(close, 252) - 1",
]
def save_classics(frames):
    """把经典因子宽表列表存成长表一张（float32，只存至少一条非缺失的行）。"""
    long = pd.concat({f"C{i + 1:02d}": fr.stack() for i, fr in enumerate(frames)}, axis=1)
    long.index.names = ["date", ID_COL]
    long.astype("float32").reset_index().to_parquet(CLASSIC_PATH)

def load_classics(wide, formulas):
    """返回与 formulas 顺序对应的经典因子宽表列表；值表不存在时按公式算一次并存表。"""
    if not os.path.exists(CLASSIC_PATH):
        frames = [eval_formula(f, wide) for f in formulas]
        save_classics(frames)
        return frames
    t = pd.read_parquet(CLASSIC_PATH).set_index(["date", ID_COL])
    return [t[f"C{i + 1:02d}"].unstack().reindex(index=wide["close"].index,
                                                 columns=wide["close"].columns).astype("float64")
            for i in range(len(formulas))]

# ============================================================
# 记录：JSON Lines，一行一条尝试，五项字段（见 spec 接口）
# ============================================================
def append_record(path, record):
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")

def read_records(path):
    if not os.path.exists(path):
        return []
    out = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out

def tried_hypotheses(records):
    """已试假设清单：记录中全部假设内容，供下一轮去重与避让。"""
    return [r["假设"] for r in records]

# ============================================================
# 自检（块一验收）：直接运行本文件时执行
# ============================================================
if __name__ == "__main__":
    wide = load_wide()
    print("宽表 close 形状:", wide["close"].shape, "| 日期", wide["close"].index.min().date(), "→", wide["close"].index.max().date())

    expr = "-delta(close, 5) / delay(close, 5)"  # 手写示例：5 日反转
    fac = eval_formula(expr, wide)
    ic1 = compute_ic_mean(fac, wide["close"], 5)
    ic2 = compute_ic_mean(eval_formula(expr, wide), wide["close"], 5)
    print("示例公式 IC 均值:", ic1, "| 重跑一致:", ic1 == ic2, "| 过门(0.015):", judge(ic1, 0.015))

    metrics = compute_metrics(fac, wide, 5)
    keys_ok = set(metrics.keys()) == {"IC均值", "ICIR", "t值", "各持有期IC", "分年IC", "分市值组IC", "分行业IC",
                                      "五分组收益", "多空收益", "覆盖率", "换手", "与已通过因子最大相关",
                                      "与经典因子最大相关"}
    print("指标组构成齐全:", keys_ok, "| 指标组 IC 均值与单算一致:", metrics["IC均值"] == ic1,
          "| ICIR:", metrics["ICIR"], "| 无已通过因子时最大相关为缺失:", metrics["与已通过因子最大相关"] is None)

    test_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "records_selftest.jsonl")
    if os.path.exists(test_path):
        os.remove(test_path)
    append_record(test_path, {"轮次": 0, "假设": "自检假设", "公式": expr, "判定数字": metrics, "结论": "通过" if judge(ic1, 0.015) else "不通过"})
    recs = read_records(test_path)
    print("记录读回:", len(recs) == 1 and set(recs[0].keys()) == {"轮次", "假设", "公式", "判定数字", "结论"}, recs)
    os.remove(test_path)

    for bad in ["foo(close)", "close + bogus_field", "ts_mean(close, 0)"]:
        try:
            eval_formula(bad, wide)
            print("非法公式未被拒绝（错误）:", bad)
        except ValueError as e:
            print("非法公式已拒绝:", bad, "→", e)

    # rank 小样本对算：三只股票当日值 30、10、20，截面排名应为 1.0、0.0、0.5
    tiny_wide = {f: pd.DataFrame([[30.0, 10.0, 20.0]],
                                 index=pd.to_datetime(["2020-01-01"]), columns=[1, 2, 3])
                 for f in FIELDS}
    rk = eval_formula("rank(close)", tiny_wide)
    print("rank 对算:", list(rk.iloc[0]) == [1.0, 0.0, 0.5], list(rk.iloc[0]))
