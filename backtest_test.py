"""测试段回测：输入一条因子公式，输出 15 项成绩单。只有数字，不做判定。
用法：python backtest_test.py "neg(close / delay(close, 20) - 1)"
三个回测脚本结构相同，只有数据段不同；计算全部由 calc.py 完成。"""

import sys

import calc

# ============================================================
# 数据段（三个回测脚本唯一不同的地方）
# 加载须越过段尾：标签要用到段尾之后 21 天的价格，故加载到 2020-04-30
# ============================================================
LOAD_END = "2020-04-30"                          # 数据加载到哪天为止
SEG_START, SEG_END = "2017-01-01", "2019-12-31"  # 成绩单统计哪一段的因子值
WITH_CLASSICS = False                            # 经典值表只覆盖训练段，本脚本不算最大相关

# ============================================================
# 主流程：公式（文字）→ 检查 → 求值 → 切段 → 成绩单（数字）
# ============================================================
def main():
    if len(sys.argv) != 2:
        print('用法：python backtest_test.py "<公式>"')
        return 1
    formula = sys.argv[1]
    ok, bad = calc.check_whitelist(formula)
    if not ok:
        print("公式错误：" + "、".join(bad) + " 不在清单内")
        return 1
    calc.TRAIN_END = LOAD_END
    wide = calc.load_wide()
    try:
        fac = calc.eval_formula(formula, wide)
        fac = fac[(fac.index >= SEG_START) & (fac.index <= SEG_END)]
        classics = calc.load_classics(wide) if WITH_CLASSICS else []
        print(calc.scorecard_text(calc.scorecard(fac, wide, classics)))
    except Exception as e:
        print(f"计算失败：{e}")
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
