# test_fake.py — 替身端到端测试
# 用假模型回复跑通完整流程，验收三件事：
# 1) 一条假设走完实现→回测→对抗→讲评，公式写错量时被一致性检查拦下并重写成功；
# 2) 讲评数字写错时被打回，重写正确后归档；始终写错时记“核对失败”；
# 3) 预算规则：命中率未达线的方向不发放第 2 次，达上限的方向封存。
# 本测试只用训练段数据，不调用真实模型。运行：python test_fake.py

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import calc
import agents
import run

BASE = os.path.dirname(os.path.abspath(__file__))
run.RECORDS_PATH = os.path.join(BASE, "records_test.jsonl")
run.EXP_PATH = os.path.join(BASE, "experience_test.jsonl")
for p in (run.RECORDS_PATH, run.EXP_PATH):
    if os.path.exists(p):
        os.remove(p)

HYP = {
    "direction": "超跌反弹", "category": "过度反应",
    "hypothesis": "过去 5 日跌幅越大的股票，未来收益越高",
    "measure": "过去 5 日累计涨跌幅取负",
    "baseline_formula": "-(close / delay(close, 5) - 1)",
    "mechanism": "恐慌抛售过度，赚抛售者急于离场让出的价格",
    "predictions": [
        {"dim": "市值组", "a": "小", "b": "大", "key": True},
        {"dim": "持有期", "a": "20", "b": "5", "key": False},
    ],
    "falsify": "小市值组 IC 不高于大市值组则不成立",
    "exp_refs": [], "diff_from_rejected": "",
}

state = {"formula_calls": 0, "review_calls": 0, "review_mode": "先错后对"}

def fake(role, payload):
    if role == "expand":
        return {"hypotheses": [HYP]}
    if role == "formula":
        state["formula_calls"] += 1
        if state["formula_calls"] == 1:
            # 第一次故意写错量（成交量比），应被一致性检查拦下
            return {"formula": "ts_mean(volume, 5) / ts_mean(volume, 60)"}
        return {"formula": HYP["baseline_formula"]}
    if role == "review":
        state["review_calls"] += 1
        m = payload["metrics"]
        wrong = state["review_mode"] == "始终错" or state["review_calls"] == 1
        ic = (m["IC均值"] or 0) + (0.5 if wrong else 0)
        return {"measures": "测度短期价格反转", "findings": "见数字", "avoid": "无",
                "borrow": "无", "speculation": "",
                "numbers": {"ic": ic, "icir": m["ICIR"], "max_corr": m["与经典因子最大相关"]}}
    raise ValueError(role)

agents.set_fake(fake)

print("加载数据与经典因子值表……")
wide = calc.load_wide()
classics = calc.load_classics(wide)
cap = calc.classic_complexity_cap()

# ---- 验收 1+2：完整流程，公式先错后对、讲评先错后对 ----
result = run.process_hypothesis(dict(HYP), wide, classics, cap)
assert isinstance(result, tuple), "流程应在回测后返回完整结果"
rec, review, status, _ = result
print("结论:", rec["结论"], "| 失效层:", rec["失效层"], "| 经验状态:", status)
print("一致性相关:", rec.get("一致性相关"), "| 讲评核对:", rec["讲评核对"])
assert rec["公式"] == HYP["baseline_formula"], "公式应为重写后的正确公式"
assert rec["一致性相关"] >= 0.99, "一致性相关应不低于 0.99"
assert state["formula_calls"] == 2, "公式应恰好写两次（一次写错被拦，一次正确）"
assert rec["讲评核对"] == "通过", "讲评应在第二次核对通过"
assert state["review_calls"] == 2, "讲评应恰好写两次（一次数字错被打回，一次正确）"
run.append_jsonl(run.RECORDS_PATH, rec)
entry = run.save_experience(rec, review, status)
assert entry["讲评"]["findings"] == "见数字", "经验条目应存入核对通过的讲评"
print("验收 1、2（前半）通过：写错量被拦、讲评数字错被打回")

# ---- 验收 2（后半）：讲评始终写错 → 核对失败，经验只存数字 ----
state["review_mode"] = "始终错"
state["formula_calls"] = 99  # 跳过写错环节，直接给对公式
result2 = run.process_hypothesis(dict(HYP), wide, classics, cap)
rec2, review2, status2, _ = result2
assert rec2["讲评核对"] == "核对失败", f"应记核对失败，实际 {rec2['讲评核对']}"
entry2 = run.save_experience(rec2, review2, status2)
assert entry2["讲评"]["findings"] == "", "核对失败时经验讲评应为空"
print("验收 2（后半）通过：讲评始终写错记核对失败")

# ---- 验收 3：预算发放规则（合成记录，不依赖市场结果） ----
def mkrec(direction, preds):
    return {"方向": direction, "机制类别": "过度反应", "假设": "x", "结论": "否决",
            "预测核对": [{"key": k, "兑现": v} for k, v in preds]}
recs = [mkrec("方向甲", [(True, False), (False, False)])]           # 命中率 0
ok, why = run.can_issue(recs, "方向甲")
assert not ok, f"命中率 0 应停止发放，实际发放：{why}"
recs = [mkrec("方向乙", [(True, True), (False, True)])]            # 命中率 1
ok, _ = run.can_issue(recs, "方向乙")
assert ok, "命中率 1 应发放第 2 次"
recs = [mkrec("方向丙", [(True, True)]) for _ in range(3)]          # 已用满 3 次
ok, _ = run.can_issue(recs, "方向丙")
assert not ok, "已用满 3 次应封存"
print("验收 3 通过：预算按命中率发放、上限封存")

print("\n全部替身验收通过")
