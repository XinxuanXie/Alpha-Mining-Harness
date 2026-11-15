"""验证段回测：输入一条因子公式，输出 15 项成绩单。只有数字，不做判定。
用法：python backtest_verify.py "neg(close / delay(close, 20) - 1)"
三个回测脚本结构相同，只有数据段不同；计算全部由 calc.py 完成。成绩单除打印外，还存一份 JSON 到 results/ 目录。"""

import json
import os
import sys
from datetime import datetime

import calc

# ============================================================
# 数据段（三个回测脚本唯一不同的地方）
# ============================================================
LOAD_END = "2026-09-30"                          # 数据加载到哪天为止（面板末日）
SEG_START, SEG_END = "2020-01-01", "2026-09-30"  # 成绩单统计哪一段的因子值
SEGMENT = "verify"                                  # 本脚本的数据段名

# ============================================================
# 主流程：公式（文字）→ 检查 → 求值 → 切段 → 成绩单（数字）
# ============================================================
def main():
    if len(sys.argv) != 2:
        print('用法：python backtest_verify.py "<公式>"')
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
        card = calc.scorecard(fac, wide)
        print(calc.scorecard_text(card))
        os.makedirs("results", exist_ok=True)
        path = f"results/{SEGMENT}_{datetime.now():%Y%m%d_%H%M%S}.json"
        record = {"公式": formula, "数据段": SEGMENT, "统计区间": [SEG_START, SEG_END],
                  "生成时间": datetime.now().isoformat(timespec="seconds"), "成绩单": card}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2, default=float)
        print(f"成绩单已存：{path}")
    except Exception as e:
        print(f"计算失败：{e}")
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
