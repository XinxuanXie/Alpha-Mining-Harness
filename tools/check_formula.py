"""公式校验：输入一条因子公式，检查结构、字段、算子与复杂度，不接触数据。
用法：python tools/check_formula.py "neg(close / delay(close, 20) - 1)"
检查口径与 engine.py 的求值规则一致：只允许四则运算与清单内算子，
算子调用总数上限 14（经典库最大值）。输出只有检查结果，不做判定之外的事。"""

import ast
import sys
from collections import Counter

# ============================================================
# 清单：与主说明书环境一节一致
# ============================================================
FIELDS = {"open", "high", "low", "close", "volume", "mktcap", "mktret", "ivol20", "resid_ret"}

OPS_1 = {"neg", "abs", "log", "sign", "sqrt", "inverse",
         "rank", "rank_sector", "sector_mean", "zscore", "winsorize"}          # 一元算子
OPS_3 = {"where", "ts_corr", "ts_beta"}                                        # 三元算子
OPS_2 = {"delay", "delta", "ts_mean", "ts_sum", "ts_std", "ts_min", "ts_max", "ts_rank",
         "ts_median", "ts_skew", "ts_kurt", "ts_decay", "ts_count", "ts_argmax", "ts_argmin",
         "gt", "resid", "power", "signed_power"}                               # 二元算子（其余默认二元）
WINDOW_OPS = {"delay", "delta", "ts_mean", "ts_sum", "ts_std", "ts_min", "ts_max", "ts_rank",
              "ts_corr", "ts_median", "ts_skew", "ts_kurt", "ts_decay", "ts_count",
              "ts_argmax", "ts_argmin", "ts_beta"}                             # 末位参数是窗口 d

MAX_OPS = 14


def arity(name):
    if name in OPS_1:
        return 1
    if name in OPS_3:
        return 3
    return 2


# ============================================================
# 检查：遍历语法树，收集问题与算子计数
# ============================================================
def check(expr):
    problems = []
    counts = Counter()
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as e:
        return [f"语法错误：{e.msg}"], counts

    func_nodes = {id(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call)}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                problems.append("存在非简单调用（属性调用等）")
                continue
            name = node.func.id
            if name not in OPS_1 | OPS_2 | OPS_3:
                problems.append(f"算子不在清单内：{name}")
                continue
            counts[name] += 1
            if node.keywords:
                problems.append(f"算子 {name} 用了关键字参数，不支持")
            if len(node.args) != arity(name):
                problems.append(f"算子 {name} 需要 {arity(name)} 个参数，给了 {len(node.args)} 个")
            elif name in WINDOW_OPS:
                last = node.args[-1]
                ok = (isinstance(last, ast.Constant) and isinstance(last.value, (int, float))
                      and not isinstance(last.value, bool)
                      and float(last.value) >= 1 and float(last.value) == int(float(last.value)))
                if not ok:
                    problems.append(f"算子 {name} 的窗口参数必须是正整数常量")
        elif isinstance(node, ast.Name):
            if id(node) not in func_nodes and node.id not in FIELDS:
                problems.append(f"字段不在清单内：{node.id}")
        elif isinstance(node, ast.Constant):
            if not isinstance(node.value, (int, float)) or isinstance(node.value, bool):
                problems.append(f"不支持的常数：{node.value!r}")
        elif isinstance(node, ast.BinOp):
            if not isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
                problems.append("只允许 + - * / 四种运算")
        elif isinstance(node, ast.UnaryOp):
            if not isinstance(node.op, ast.USub):
                problems.append("只允许一元负号")
        elif isinstance(node, (ast.Expression, ast.Load,
                               ast.Add, ast.Sub, ast.Mult, ast.Div, ast.USub)):
            pass  # 结构节点与运算符节点本身，已在父节点处校验
        else:
            problems.append(f"不支持的表达式结构：{type(node).__name__}")
    return problems, counts


# ============================================================
# 主程序：打印结果
# ============================================================
if __name__ == "__main__":
    if len(sys.argv) != 2:
        print('用法：python tools/check_formula.py "<公式>"')
        sys.exit(2)
    expr = sys.argv[1]
    problems, counts = check(expr)
    total = sum(counts.values())
    print(f"算子调用总数：{total}（上限 {MAX_OPS}）")
    if counts:
        print("各算子计数：" + "，".join(f"{k}×{v}" for k, v in sorted(counts.items())))
    if total > MAX_OPS:
        problems.append(f"算子调用超限：{total} > {MAX_OPS}")
    if problems:
        print("问题：")
        for p in problems:
            print(f"- {p}")
        print("结论：不合格")
        sys.exit(1)
    print("结论：合格")
