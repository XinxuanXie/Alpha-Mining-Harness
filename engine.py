# engine.py — 计算引擎
# 职责：读数据、备好宽表，按公式算因子值，做公式检查。只算不判，不算指标。
# 本文件不调用模型。运行顺序自上而下：参数 → 读数据 → 算公式 → 检查 → 自检。

import ast
import os

import numpy as np
import pandas as pd

# ============================================================
# 参数（本文件内部固定值）
# ============================================================
BASE = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE, "data", "panel.parquet")
SEC_PATH = os.path.join(BASE, "data", "securities.parquet")
MEMB_PATH = os.path.join(BASE, "data", "membership_intervals.parquet")
BENCH_PATH = os.path.join(BASE, "data", "spy_benchmark.parquet")
PRECOMP_PATH = os.path.join(BASE, "data", "precomp_fields.parquet")
LOAD_END = "2016-12-31"   # 数据加载截止日（回测脚本按数据段改这个值）
ID_COL = "permno"          # 股票标识列
FIELDS = ["open", "high", "low", "close", "volume", "mktcap", "mktret",
          "ivol20", "resid_ret"]  # 公式可用字段（mktret 为市场收益；ivol20、resid_ret 为程序预计算的市场模型残差类字段，窗口固定 20 日）
MIN_STOCKS = 10            # 当日参与 IC 计算的股票少于此数，当日 IC 记缺失
SECTOR_OF = {}             # permno（int）→ GICS 行业名；load_wide 时填充

# ============================================================
# 读数据：把行情表按字段拆成宽表（行=交易日，列=股票）
# 成分口径：只保留落在 S&P 500 成分区间内的股票-日，区间外置缺失
# ============================================================
def load_wide():
    df = pd.read_parquet(DATA_PATH, filters=[("date", "<=", pd.Timestamp(LOAD_END))])
    df = df.sort_values(["date", ID_COL])
    wide = {}
    for f in ("open", "high", "low", "close", "volume", "mktcap"):
        wide[f] = df.pivot(index="date", columns=ID_COL, values=f)
    close = wide["close"]
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
            inside |= (close.index >= s) & (close.index <= e)
        mask[col] = inside
    for f in ("open", "high", "low", "close", "volume", "mktcap"):
        wide[f] = wide[f].where(mask)
    bench = pd.read_parquet(BENCH_PATH, filters=[("date", "<=", pd.Timestamp(LOAD_END))])
    mkt = bench.set_index("date")["vwretd"].reindex(close.index)
    wide["mktret"] = pd.DataFrame(
        np.repeat(mkt.to_numpy()[:, None], len(close.columns), axis=1),
        index=close.index, columns=close.columns)
    sec = pd.read_parquet(SEC_PATH)
    SECTOR_OF.clear()
    for permno, name in zip(sec[ID_COL], sec["sector_name"]):
        if isinstance(name, str) and name:
            SECTOR_OF[int(permno)] = name
    ivol, resid = _precomp_fields(close, wide["mktret"])
    wide["ivol20"] = ivol.where(mask)
    wide["resid_ret"] = resid.where(mask)
    return wide

def _precomp_fields(close, mktret):
    """预计算市场模型残差类字段（窗口固定 20 日，只用当日及以前数据）：
    ivol20 = 个股日收益对市场收益滚动回归的残差标准差（特质波动）；
    resid_ret = 当日残差收益（个股收益减窗口内拟合值）。
    结果缓存到 data/precomp_fields.parquet，缓存存在时直接读。"""
    if os.path.exists(PRECOMP_PATH):
        cached = pd.read_parquet(PRECOMP_PATH)
        ivol = cached.pivot(index="date", columns=ID_COL, values="ivol20")
        resid = cached.pivot(index="date", columns=ID_COL, values="resid_ret")
        return (ivol.reindex(index=close.index, columns=close.columns),
                resid.reindex(index=close.index, columns=close.columns))
    r = close / close.shift(1) - 1
    w = 20
    mean_r = r.rolling(w, min_periods=w).mean()
    mean_m = mktret.rolling(w, min_periods=w).mean()
    var_r = r.rolling(w, min_periods=w).var()
    var_m = mktret.rolling(w, min_periods=w).var()
    cov = r.rolling(w, min_periods=w).cov(mktret)
    beta = cov / var_m
    alpha = mean_r - beta * mean_m
    resid_var = (var_r - beta ** 2 * var_m).clip(lower=0)
    ivol = np.sqrt(resid_var)
    resid = r - (alpha + beta * mktret)
    try:
        long = pd.DataFrame({
            "date": np.repeat(close.index.to_numpy(), len(close.columns)),
            ID_COL: np.tile(close.columns.to_numpy(), len(close.index)),
            "ivol20": ivol.to_numpy().ravel(),
            "resid_ret": resid.to_numpy().ravel()})
        long.to_parquet(PRECOMP_PATH, index=False)
    except Exception:
        pass
    return ivol, resid

# ============================================================
# 算公式：表达式只能用算子清单中的算子与九个字段
# 缺失规则：任一算子所需位置输入缺失，输出缺失；时序窗口缺一日，输出缺失
# ============================================================
def _rank_cs(x):
    # 截面排名：(名次-1)/(股票数-1)，并列取平均名次，缺失不参与
    n = x.notna().sum(axis=1)
    r = x.rank(axis=1, method="average")
    out = (r - 1).div(n - 1, axis=0)
    return out.where(n >= 2)

def _ts_rank(x, d):
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
    out = (a > b) * 1.0
    mask = a.notna() if hasattr(a, "notna") else None
    if hasattr(b, "notna"):
        mask = b.notna() if mask is None else mask & b.notna()
    return out.where(mask) if mask is not None and hasattr(out, "where") else out

def _rank_sector(x):
    if not SECTOR_OF:
        raise ValueError("行业数据不可用，无法使用 rank_sector")
    out = pd.DataFrame(np.nan, index=x.index, columns=x.columns)
    names = {SECTOR_OF.get(int(c)) for c in x.columns} - {None}
    for name in names:
        cols = [c for c in x.columns if SECTOR_OF.get(int(c)) == name]
        out[cols] = _rank_cs(x[cols])
    return out

def _sector_mean(x):
    if not SECTOR_OF:
        raise ValueError("行业数据不可用，无法使用 sector_mean")
    out = pd.DataFrame(np.nan, index=x.index, columns=x.columns)
    names = {SECTOR_OF.get(int(c)) for c in x.columns} - {None}
    for name in names:
        cols = [c for c in x.columns if SECTOR_OF.get(int(c)) == name]
        m = x[cols].mean(axis=1).to_numpy()
        out[cols] = np.repeat(m[:, None], len(cols), axis=1)
    return out

def _sign(a):
    if hasattr(a, "sub"):
        return (a > 0) * 1.0 - (a < 0) * 1.0
    return float(np.sign(a))

def _sqrt(a):
    if hasattr(a, "where"):
        return np.sqrt(a.where(a >= 0))
    return float(np.sqrt(a)) if a >= 0 else float("nan")

def _inverse(a):
    if hasattr(a, "replace"):
        return (1.0 / a).replace([np.inf, -np.inf], np.nan)
    return 1.0 / a if a else float("nan")

def _power(a, p):
    with np.errstate(invalid="ignore", divide="ignore", over="ignore"):
        if hasattr(a, "pow"):
            return a.pow(p)
        return float(np.power(a, p))

def _signed_power(a, p):
    if hasattr(a, "abs"):
        return _sign(a) * a.abs().pow(p)
    return float(np.sign(a) * (abs(a) ** p))

def _zscore(x):
    m = x.mean(axis=1)
    s = x.std(axis=1)
    out = x.sub(m, axis=0).div(s, axis=0)
    return out.where((s > 0) & (x.notna().sum(axis=1) >= 2))

def _winsorize(x):
    lo = x.quantile(0.01, axis=1)
    hi = x.quantile(0.99, axis=1)
    return x.clip(lower=lo, upper=hi, axis=0)

def _resid_cs(a, b):
    # 逐日截面一元回归 a ~ b 取残差；任一缺失记缺失，有效股票不足或 b 无方差记缺失
    mask = a.notna() & b.notna()
    af = a.where(mask).fillna(0.0)
    bf = b.where(mask).fillna(0.0)
    n = mask.sum(axis=1).astype(float)
    ma = af.sum(axis=1) / n
    mb = bf.sum(axis=1) / n
    da = (af - ma.values[:, None]).where(mask, 0.0)
    db = (bf - mb.values[:, None]).where(mask, 0.0)
    var = (db * db).sum(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        beta = (da * db).sum(axis=1) / var
    out = da - beta.values[:, None] * db
    ok = (n >= MIN_STOCKS) & (var > 0)
    return out.where(mask & ok.values[:, None])

def _where(c, a, b):
    cond = c > 0
    if hasattr(cond, "values"):
        # c 是 DataFrame：逐格选择，a、b 可为 DataFrame 或标量
        av = a.values if hasattr(a, "values") else a
        bv = b.values if hasattr(b, "values") else b
        return pd.DataFrame(np.where(cond.values, av, bv),
                            index=c.index, columns=c.columns)
    return a if cond else b

def _ts_arg_extreme(x, d, want_max):
    # 距窗口内极值出现位置的天数（0 表示就在当日）；窗口含缺失记缺失
    def f(w):
        if np.isnan(w).any():
            return np.nan
        idx = int(np.argmax(w)) if want_max else int(np.argmin(w))
        return float(len(w) - 1 - idx)
    return x.rolling(d, min_periods=d).apply(f, raw=True)

def _ts_beta(a, b, d):
    cov = a.rolling(d, min_periods=d).cov(b)
    var = b.rolling(d, min_periods=d).var()
    out = cov / var
    valid = (a.notna() & b.notna()).rolling(d, min_periods=d).sum() == d
    return out.where(valid & (var > 0))

OPS = {
    "neg": lambda a: -a,
    "abs": lambda a: a.abs() if hasattr(a, "abs") else abs(a),
    "log": lambda a: np.log(a.where(a > 0) if hasattr(a, "where") else a),
    "rank": _rank_cs,
    "rank_sector": _rank_sector,
    "sector_mean": _sector_mean,
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
    "sign": _sign,
    "sqrt": _sqrt,
    "inverse": _inverse,
    "power": _power,
    "signed_power": _signed_power,
    "zscore": _zscore,
    "winsorize": _winsorize,
    "resid": _resid_cs,
    "where": _where,
    "ts_median": lambda a, d: a.rolling(d, min_periods=d).median(),
    "ts_skew": lambda a, d: a.rolling(d, min_periods=d).skew(),
    "ts_kurt": lambda a, d: a.rolling(d, min_periods=d).kurt(),
    "ts_decay": lambda a, d: a.ewm(halflife=d, min_periods=d).mean(),
    "ts_count": lambda a, d: a.rolling(d, min_periods=d).sum(),
    "ts_argmax": lambda a, d: _ts_arg_extreme(a, d, True),
    "ts_argmin": lambda a, d: _ts_arg_extreme(a, d, False),
    "ts_beta": _ts_beta,
}
WINDOW_OPS = {"delay", "delta", "ts_mean", "ts_sum", "ts_std", "ts_min", "ts_max", "ts_rank", "ts_corr",
              "ts_median", "ts_skew", "ts_kurt", "ts_decay", "ts_count", "ts_argmax", "ts_argmin", "ts_beta"}

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
        arity = {"neg": 1, "abs": 1, "log": 1, "rank": 1, "rank_sector": 1, "sector_mean": 1, "ts_corr": 3,
                 "sign": 1, "sqrt": 1, "inverse": 1, "zscore": 1, "winsorize": 1, "where": 3, "ts_beta": 3}.get(name, 2)
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
# 程序检查：白名单
# ============================================================
def check_whitelist(expr):
    """公式用到的算子与字段必须全部在清单内。返回 (是否通过, 超清单的名单)。"""
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as e:
        return False, [f"语法错误：{e.msg}"]
    bad = []
    func_ids = {id(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call)}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                bad.append("非简单调用")
            elif node.func.id not in OPS:
                bad.append(f"算子 {node.func.id}")
        elif isinstance(node, ast.Name) and id(node) not in func_ids:
            if node.id not in FIELDS:
                bad.append(f"字段 {node.id}")
    return (len(bad) == 0), bad

# ============================================================
# 自检：直接运行本文件时执行（重复运行、截断、白名单）
# ============================================================
if __name__ == "__main__":
    wide = load_wide()
    print("宽表 close 形状:", wide["close"].shape, "| 日期", wide["close"].index.min().date(), "→", wide["close"].index.max().date())
    expr = "-(close / delay(close, 5) - 1)"  # 手写示例：5 日反转
    fac = eval_formula(expr, wide)
    fac2 = eval_formula(expr, wide)
    print("重复运行一致:", fac.equals(fac2))
    cut = {f: w[w.index <= "2010-12-31"] for f, w in wide.items()}
    fac_cut = eval_formula(expr, cut)
    print("截断检验（无未来数据）:", fac_cut.equals(fac[fac.index <= "2010-12-31"]))
    print("白名单通过:", check_whitelist(expr)[0])
    print("白名单拒绝:", check_whitelist("foo(close) + bogus")[0] is False)
