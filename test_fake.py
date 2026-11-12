# test_fake.py — 替身端到端测试
# 用假模型回复跑通完整流程，验收三件事：
# 1) 一条假设走完实现→回测→对抗→讲评，公式写错量时被一致性检查拦下并重写成功；
# 2) 讲评数字写错时被打回，重写正确后归档；始终写错时记“核对失败”；
# 3) 预算规则：命中率未达线的方向不发放第 2 次，达上限的方向封存；
# 4) 过程轨迹 trace.jsonl 逐条落盘（只写不读，供实验结束后分析）；
# 5) 两处模型对抗审查被调用并留痕、进经验，但不改变程序结论；对抗摘要随已否决摘要回流；
# 6) 预测取值校验（行业 a 须为真实行业名、市值组/持有期取值在固定集合内）与线索自提校验；
# 7) 主循环：无线索时自提→登记→处理→达总上限停止（打桩，不重复加载数据）。
# 本测试只用训练段数据，不调用真实模型。运行：python test_fake.py

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import calc
import agents
import run
import search

BASE = os.path.dirname(os.path.abspath(__file__))
run.RECORDS_PATH = os.path.join(BASE, "records_test.jsonl")
run.EXP_PATH = os.path.join(BASE, "experience_test.jsonl")
run.TRACE_PATH = os.path.join(BASE, "trace_test.jsonl")
for p in (run.RECORDS_PATH, run.EXP_PATH, run.TRACE_PATH):
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

state = {"formula_calls": 0, "review_calls": 0, "review_mode": "先错后对", "propose_calls": 0,
         "refine_mode": "采纳"}

def fake(role, payload):
    if role == "expand":
        return {"hypotheses": [HYP]}
    if role == "formula":
        state["formula_calls"] += 1
        if state["formula_calls"] == 1:
            # 第一次故意写错量（成交量比），应被一致性检查拦下
            return {"formula": "ts_mean(volume, 5) / ts_mean(volume, 60)"}
        return {"formula": HYP["baseline_formula"]}
    if role == "propose":
        state["propose_calls"] += 1
        names = ["量缩反弹", "循环测试方向二", "循环测试方向三"]
        d = names[min(state["propose_calls"] - 1, len(names) - 1)]
        return {"clues": [{"direction": d, "phenomenon": "某种现象", "source": "某种收益来源",
                           "category": "流动性"}]}
    if role == "refine":
        if state["refine_mode"] == "不采纳":
            # 优化稿只剩一条预测，过不了登记校验，应保留初稿
            return {"measure": HYP["measure"], "baseline_formula": HYP["baseline_formula"],
                    "mechanism": HYP["mechanism"],
                    "predictions": [{"dim": "市值组", "a": "小", "b": "大", "key": True}],
                    "falsify": "x", "lit_refs": [], "changes": "删减预测"}
        return {"measure": HYP["measure"], "baseline_formula": HYP["baseline_formula"],
                "mechanism": HYP["mechanism"] + "（据 L1 补充流动性条件）",
                "predictions": HYP["predictions"],
                "falsify": "（优化）" + HYP["falsify"],
                "lit_refs": ["L1"], "changes": "依据 L1 收紧否定条件"}
    if role == "attack_reg":
        return {"最像的经典": "C01", "相似点": "同为短期价格反转",
                "换皮判断": "与经典反转同源，区别未成立",
                "预测问题": "无", "机制问题": "无"}
    if role == "attack_res":
        return {"失效解释": "信号强度不足，IC 未达门槛", "未覆盖的失效方式": "未按波动状态分组",
                "备注": ""}
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

# ---- 验收 4：过程轨迹落盘 ----
# ---- 验收 5：模型对抗审查留痕、进经验、不改变程序结论，并随已否决摘要回流 ----
assert rec["判定数字"]["最大相关经典"] and rec["判定数字"]["最大相关经典"].startswith("C"), \
    "判定数字应记录最大相关经典的编号，供换皮交叉核对"
assert rec["生成侧对抗"]["最像的经典"].startswith("C01"), "生成侧对抗应已留痕"
assert rec["检验侧对抗"]["失效解释"].startswith("信号强度不足"), "检验侧对抗应已留痕"
assert rec["结论"] in ("通过", "条件成立", "否决"), "结论仍由程序规则给出"
assert entry["对抗备忘录"]["未覆盖的失效方式"] == "未按波动状态分组", "对抗备忘录应进经验条目"
assert entry["生成侧对抗"]["换皮判断"].startswith("与经典反转同源"), "生成侧对抗应进经验条目"
assert rec["换皮交叉"] in ("一致", "不一致", "无法比对"), "换皮交叉应由程序比对并写入账本"
assert entry["换皮交叉"] == rec["换皮交叉"], "换皮交叉应进经验条目"
assert run.cross_check({"最像的经典": "C03"}, {"最大相关经典": "C03"}) == "一致"
assert run.cross_check({"最像的经典": "C01"}, {"最大相关经典": "C03"}) == "不一致"
assert run.cross_check({"最像的经典": "无"}, {"最大相关经典": "C03"}) == "无法比对"
assert run.cross_check(None, {"最大相关经典": "C03"}) == "无法比对"
sums = run.rejected_summaries("过度反应", run.read_jsonl(run.RECORDS_PATH))
assert sums and "死因：信号强度不足" in sums[0]["对抗摘要"], "对抗摘要应随已否决摘要回流"
print("验收 5 通过：对抗审查留痕进经验、结论仍归程序、对抗意见回流展开输入")

events = [e["事件"] for e in run.read_jsonl(run.TRACE_PATH)]
for need in ("生成对抗", "公式检查", "回测", "对抗与核对", "检验对抗", "讲评打回", "结论"):
    assert need in events, f"轨迹缺少事件：{need}"
checks = [e for e in run.read_jsonl(run.TRACE_PATH) if e["事件"] == "公式检查"]
assert any(c["结果"].startswith("未通过") for c in checks), "轨迹应记下第一次写错量的拦截"
assert any(c["结果"] == "通过" for c in checks), "轨迹应记下重写后的通过"
print(f"验收 4 通过：轨迹共 {len(events)} 条事件，关键节点齐全")

# ---- 验收 6：预测取值校验 + 线索自提校验 ----
sectors = set(calc.SECTOR_OF.values())
assert sectors, "行业集合应已随数据加载"
bad_hyp = dict(HYP)
bad_hyp["predictions"] = [{"dim": "行业", "a": "整体", "b": "整体", "key": True},
                          {"dim": "市值组", "a": "微", "b": "大", "key": False}]
errs = run.validate_registration(bad_hyp, [], [], sectors=sectors)
assert any("真实行业名" in e for e in errs), f"行业 a=整体 应被拒登：{errs}"
assert any("小/中/大" in e for e in errs), f"市值组取值越界应被拒登：{errs}"
good_hyp = dict(HYP)
good_hyp["predictions"] = [{"dim": "行业", "a": sorted(sectors)[0], "b": "整体", "key": True},
                           {"dim": "市值组", "a": "小", "b": "大", "key": False}]
assert run.validate_registration(good_hyp, [], [], sectors=sectors) == [], "合法预测应通过校验"
new_clues = agents.propose_clues(["超跌反弹"], [], [])
assert new_clues and new_clues[0]["direction"] == "量缩反弹", "线索自提应返回候选"
assert run.validate_clue(new_clues[0], {"超跌反弹"}) == [], "自提线索应通过校验"
assert run.validate_clue(new_clues[0], {"量缩反弹"}) != [], "与已有方向重名应被拒"
assert run.validate_clue({"direction": "x", "phenomenon": "y", "source": "z", "category": "不存在的类"}, set()) != [], \
    "类别不在词表应被拒"
print("验收 6 通过：预测取值校验拦下无效登记，线索自提与校验可用")

# ---- 验收 7：主循环（自提→登记→处理→达上限停止），打桩不加载数据 ----
loop_clues = os.path.join(BASE, "clues_loop_test.jsonl")
if os.path.exists(loop_clues):
    os.remove(loop_clues)
saved = (run.CLUES_PATH, run.MAX_TOTAL_ATTEMPTS, run.run_direction,
         calc.load_wide, calc.load_classics, calc.classic_complexity_cap)
run.CLUES_PATH = loop_clues
run.MAX_TOTAL_ATTEMPTS = 2
state["propose_calls"] = 0
calc.load_wide = lambda: {}
calc.load_classics = lambda wide: []
calc.classic_complexity_cap = lambda: 14
def stub_direction(clue, wide, classics, cap, sectors, stats):
    stats["done"] += 1
run.run_direction = stub_direction
gen_before = sum(1 for e in run.read_jsonl(run.TRACE_PATH) if e["事件"] == "线索生成")
run.main()
calc.load_wide, calc.load_classics, calc.classic_complexity_cap = saved[3], saved[4], saved[5]
run.CLUES_PATH, run.MAX_TOTAL_ATTEMPTS, run.run_direction = saved[0], saved[1], saved[2]
loop_rows = run.read_jsonl(loop_clues)
assert [r["direction"] for r in loop_rows] == ["量缩反弹", "循环测试方向二"], \
    f"主循环应自提并登记两个方向后达上限停止：{loop_rows}"
assert all("agent 自提" in r["source"] for r in loop_rows), "自提线索应标注来源"
gen_after = sum(1 for e in run.read_jsonl(run.TRACE_PATH) if e["事件"] == "线索生成")
assert gen_after - gen_before == 2, "主循环应触发两次线索生成"
os.remove(loop_clues)
print("验收 7 通过：主循环自提登记、逐方向处理、达总上限停止")

# ---- 验收 8：文献检索与假设优化（检索打桩，不联网） ----
search.search = lambda query, limit=5: [
    {"标题": "Short-Term Reversal and Liquidity", "年份": 2010, "来源": "替身",
     "摘要": "reversal profits are related to liquidity provision"}]
hyp8 = dict(HYP)
hyp8["search_queries"] = ["short-term reversal liquidity"]
rec8, _, _, _ = run.process_hypothesis(hyp8, wide, classics, cap)
assert rec8["登记"]["否定条件"] == "（优化）" + HYP["falsify"], "合格的优化稿应被采用并锁定"
assert rec8["登记"]["文献引用"] == ["L1"], "登记应记录文献引用"
assert "L1" in rec8["登记"]["优化说明"], "登记应记录优化说明"
state["refine_mode"] = "不采纳"
rec8b, _, _, _ = run.process_hypothesis(dict(hyp8), wide, classics, cap)
assert rec8b["登记"]["否定条件"] == HYP["falsify"], "优化稿不合格时应保留初稿"
assert rec8b["登记"]["文献引用"] == [], "未采纳时不应记录文献引用"
tr8 = run.read_jsonl(run.TRACE_PATH)
assert any(e["事件"] == "文献检索" for e in tr8), "轨迹应记录文献检索"
assert any(e["事件"] == "假设优化" and e["采纳"] for e in tr8), "轨迹应记录优化采纳"
assert any(e["事件"] == "假设优化" and not e["采纳"] for e in tr8), "轨迹应记录优化未采纳"
print("验收 8 通过：检索后优化定稿、校验把关、不合格保留初稿")

print("\n全部替身验收通过")
