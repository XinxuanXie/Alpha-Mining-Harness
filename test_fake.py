# test_fake.py — 替身端到端测试
# 用假模型回复跑通完整流程，验收三件事：
# 1) 一条假设走完实现→回测→对抗→讲评，公式写错量时被一致性检查拦下并重写成功；
# 2) 讲评数字写错时被打回，重写正确后归档；始终写错时记“核对失败”；
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
         "refine_mode": "采纳", "attack_reg_payload": None,
         "refine_calls": 0, "refine_payload": None, "pick_payload": None,
         "expand_payload": None, "expand_hyps": None,
         "expand_seq": None, "expand_payloads": [], "formula_mode": None,
         "formula_seq": None, "formula_payloads": [], "post_attack_calls": 0,
         "revise_formula": "neg(ts_mean(close / delay(close, 1) - 1, 20))"}

def fake(role, payload):
    if role == "expand":
        state["expand_payload"] = payload
        state["expand_payloads"].append(payload)
        if state["expand_seq"]:
            return {"hypotheses": state["expand_seq"].pop(0)}
        if state["expand_hyps"] is not None:
            return {"hypotheses": state["expand_hyps"]}
        return {"hypotheses": [HYP]}
    if role == "formula":
        state["formula_calls"] += 1
        state["formula_payloads"].append(payload)
        if state["formula_seq"]:
            return {"formula": state["formula_seq"].pop(0)}
        if payload.get("revision"):
            # 因子修订轮次：按程序修改要求给出与基准不同的公式
            return {"formula": state["revise_formula"]}
        if state["formula_mode"] == "回登记基准":
            return {"formula": payload["hyp"]["baseline_formula"]}
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
    if role == "pick":
        state["pick_payload"] = payload
        return {"picks": ["L1"], "reason": "L1 与机制最相关"}
    if role == "refine":
        state["refine_calls"] += 1
        state["refine_payload"] = payload
        if state["refine_mode"] == "不采纳":
            # 优化稿只剩一条预测，过不了登记校验，应保留初稿
            return {"measure": HYP["measure"], "baseline_formula": HYP["baseline_formula"],
                    "mechanism": HYP["mechanism"],
                    "predictions": [{"dim": "市值组", "a": "小", "b": "大", "key": True}],
                    "falsify": "x", "lit_refs": [], "changes": "删减预测"}
        if state["refine_mode"] == "空转":
            # 零引用零修改（changes 为空）却改了登记内容：假优化，应被硬校验判失败
            return {"measure": HYP["measure"], "baseline_formula": HYP["baseline_formula"],
                    "mechanism": HYP["mechanism"], "predictions": HYP["predictions"],
                    "falsify": "（优化）" + HYP["falsify"],
                    "lit_refs": [], "changes": ""}
        if state["refine_mode"] == "空转无修改":
            # 零引用、changes 只写“无修改”却改了登记内容：同样是假优化，应判失败
            return {"measure": HYP["measure"], "baseline_formula": HYP["baseline_formula"],
                    "mechanism": HYP["mechanism"], "predictions": HYP["predictions"],
                    "falsify": "（优化）" + HYP["falsify"],
                    "lit_refs": [], "changes": "无修改"}
        return {"measure": HYP["measure"], "baseline_formula": HYP["baseline_formula"],
                "mechanism": HYP["mechanism"] + "（据 L1 补充流动性条件）",
                "predictions": HYP["predictions"],
                "falsify": "（优化）" + HYP["falsify"],
                "lit_refs": ["L1"], "changes": "依据 L1 收紧否定条件"}
    if role == "attack_reg":
        state["attack_reg_payload"] = payload
        return {"最像的经典": "C01", "相似点": "同为短期价格反转",
                "换皮判断": "与经典反转同源，区别未成立",
                "预测问题": "无", "机制问题": "无", "引用问题": "无"}
    if role == "attack_res":
        return {"失效解释": "信号强度不足，IC 未达门槛", "未覆盖的失效方式": "未按波动状态分组",
                "备注": ""}
    if role == "revise_after_attack":
        state["post_attack_calls"] += 1
        return {"measure": HYP["measure"], "baseline_formula": HYP["baseline_formula"],
                "mechanism": HYP["mechanism"] + "（据对抗意见补明付钱方）",
                "predictions": HYP["predictions"],
                "falsify": "（对抗后修订）" + HYP["falsify"],
                "changes": "依据对抗意见收紧否定条件并补明机制"}
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

# ---- 验收 3：（原预算发放规则验收已随该模式删除，编号保留不复用） ----

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
saved = (run.CLUES_PATH, run.MAX_TOTAL_ATTEMPTS, run.run_fresh_loop,
         calc.load_wide, calc.load_classics, calc.classic_complexity_cap)
run.CLUES_PATH = loop_clues
run.MAX_TOTAL_ATTEMPTS = 2
state["propose_calls"] = 0
calc.load_wide = lambda: {}
calc.load_classics = lambda wide: []
calc.classic_complexity_cap = lambda: 14
def stub_direction(clue, wide, classics, cap, sectors, stats):
    stats["done"] += 1
run.run_fresh_loop = stub_direction
gen_before = sum(1 for e in run.read_jsonl(run.TRACE_PATH) if e["事件"] == "线索生成")
run.main()
calc.load_wide, calc.load_classics, calc.classic_complexity_cap = saved[3], saved[4], saved[5]
run.CLUES_PATH, run.MAX_TOTAL_ATTEMPTS, run.run_fresh_loop = saved[0], saved[1], saved[2]
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
hyp8, lit8 = run.apply_literature(hyp8)
assert hyp8["falsify"] == "（优化）" + HYP["falsify"], "合格的优化稿应被采用并锁定"
assert hyp8["lit_refs"] == ["L1"], "登记应记录文献引用"
assert "L1" in hyp8["优化说明"], "登记应记录优化说明"
rec8, _, _, _ = run.process_hypothesis(hyp8, wide, classics, cap, lit=lit8)
assert state["attack_reg_payload"]["lit"], "生成侧对抗应收到检索材料"
assert state["attack_reg_payload"]["lit"][0]["编号"] == "L1", "对抗收到的材料应带编号"
assert "引用问题" in rec8["生成侧对抗"], "生成侧对抗输出应含引用问题字段"
assert rec8["登记"]["否定条件"] == "（优化）" + HYP["falsify"], "锁定后的登记应进入账本"
state["refine_mode"] = "不采纳"
hyp8b_src = dict(HYP)
hyp8b_src["search_queries"] = ["short-term reversal liquidity"]
hyp8b, _ = run.apply_literature(hyp8b_src)
assert hyp8b["falsify"] == HYP["falsify"], "优化稿不合格时应保留初稿"
assert not hyp8b.get("lit_refs"), "未采纳时不应记录文献引用"
tr8 = run.read_jsonl(run.TRACE_PATH)
assert any(e["事件"] == "文献检索" for e in tr8), "轨迹应记录文献检索"
assert any(e["事件"] == "假设优化" and e["采纳"] for e in tr8), "轨迹应记录优化采纳"
assert any(e["事件"] == "假设优化" and not e["采纳"] for e in tr8), "轨迹应记录优化未采纳"
print("验收 8 通过：检索后优化定稿、校验把关、不合格保留初稿")

# ---- 验收 9：成本与用时记录（用量增量与牌价估算，纯程序不依赖数据） ----
snap9 = agents.usage_snapshot()
agents.USAGE["输入token"] += 2000
agents.USAGE["输出token"] += 500
agents.CALL_COUNT += 3
d9 = agents.usage_since(snap9)
assert d9 == {"calls": 3, "in": 2000, "out": 500}, f"用量增量应准确：{d9}"
assert abs(run.est_cost(1_000_000, 1_000_000) - 1.37) < 1e-6, "牌价估算应为输入输出牌价之和"
rec9 = {}
c9 = run.stamp_cost(rec9, snap9, __import__("time").time())
assert rec9["成本"]["模型调用"] == 3 and rec9["成本"]["输入token"] == 2000, "成本应写入记录"
assert rec9["成本"]["估算成本USD"] == run.est_cost(2000, 500), "记录成本应与估算函数一致"
assert rec9["成本"]["用时秒"] >= 0, "用时应非负"
print("验收 9 通过：成本与用时可记录、估算口径一致")

# ---- 验收 10：网络搜索结果映射、来源报告与失败重试（打桩原始结果，不联网） ----
import importlib as _importlib
_importlib.reload(search)   # 验收 8 把 search.search 换成了打桩函数，这里恢复真函数再测
_saved_raw, _saved_cache_path = search._ddgs_raw, search.CACHE_PATH
search.CACHE_PATH = os.path.join(BASE, "lit_cache_test.json")
if os.path.exists(search.CACHE_PATH):
    os.remove(search.CACHE_PATH)
# 结果映射：原始 {title, href, body} → 材料 {标题, 来源=网络搜索, 摘要=片段, 全文链接}，同链接去重
search._ddgs_raw = lambda q, limit: [
    {"title": "Reversals and Liquidity", "href": "https://x.org/a",
     "body": "  reversal   profits\n compensate liquidity provision "},
    {"title": "No Snippet Paper", "href": "https://x.org/b", "body": ""},
    {"title": "Same Link Again", "href": "https://x.org/a", "body": "duplicate"}]
_got = search.search("验收十检索词甲", limit=3)
assert len(_got) == 2, f"同链接重复结果应只留一条：{len(_got)} 条"
assert _got[0]["标题"] == "Reversals and Liquidity" and _got[0]["来源"] == "网络搜索", \
    "网络搜索结果来源应标注为网络搜索"
assert _got[0]["摘要"] == "reversal profits compensate liquidity provision", \
    f"摘要应取搜索片段并压空白：{_got[0]['摘要']}"
assert _got[0]["全文链接"] == "https://x.org/a" and _got[0]["年份"] is None, \
    "全文链接应取结果链接，年份缺失记 None"
assert _got[1]["摘要"] is None, "片段为空时摘要应为 None（仅标题级材料）"
_rep = search.last_report()
assert _rep[0]["来源"] == "网络搜索" and _rep[0]["结果"].startswith("返回"), \
    f"来源报告应记网络搜索成功条数：{_rep}"
# 失败入报告：两次都抛错 → 返回空、报告记失败与错误
def _boom_raw(q, limit):
    raise RuntimeError("网络故障")
search._ddgs_raw = _boom_raw
_got2 = search.search("验收十检索词乙", limit=3)
assert _got2 == [], "网络搜索失败应返回空列表、不中断"
_rep2 = search.last_report()
assert _rep2[0]["来源"] == "网络搜索" and _rep2[0]["结果"] == "失败" \
    and "网络故障" in _rep2[0]["错误"], f"来源报告应记失败原因：{_rep2}"
# 抖动一次后成功：首次抛错、重试拿到结果，报告记重试成功
_flaky = {"n": 0}
def _flaky_raw(q, limit):
    _flaky["n"] += 1
    if _flaky["n"] == 1:
        raise RuntimeError("暂时超时")
    return [{"title": "R", "href": "https://x.org/r", "body": "some snippet"}]
search._ddgs_raw = _flaky_raw
_got3 = search.search("验收十检索词丙", limit=3)
assert _got3 and _got3[0]["标题"] == "R", "失败后应重试并拿到结果"
assert "重试成功" in search.last_report()[0]["结果"], "来源报告应记重试成功"
assert not hasattr(search, "SOURCES"), "旧四源清单 SOURCES 应已删除"
search._ddgs_raw, search.CACHE_PATH = _saved_raw, _saved_cache_path
if os.path.exists(os.path.join(BASE, "lit_cache_test.json")):
    os.remove(os.path.join(BASE, "lit_cache_test.json"))
print("验收 10 通过：网络搜索映射（片段即摘要、同链接去重）、来源成败入报告、失败重试")

# ---- 验收 11：文献三段流程——有摘要才筛选深读，无摘要跳过优化 ----
_saved_search, _saved_fetch = search.search, search.fetch_fulltext
state["refine_mode"] = "采纳"
search.search = lambda query, limit=5: [
    {"标题": "Short-Term Reversal and Liquidity", "年份": 2010, "来源": "替身",
     "摘要": "reversal profits are related to liquidity provision",
     "全文链接": "https://example.org/full"}]
search.fetch_fulltext = lambda item: {"节选": "FULLTEXT-EXCERPT", "字数": 5000}
hyp11 = dict(HYP)
hyp11["search_queries"] = ["short-term reversal liquidity"]
run.apply_literature(hyp11)
assert state["pick_payload"] is not None, "有摘要时应先调用文献筛选"
assert state["refine_payload"]["lit"][0].get("全文节选") == "FULLTEXT-EXCERPT", \
    "筛选选中篇目的全文节选应随材料交给优化"
tr11 = run.read_jsonl(run.TRACE_PATH)
assert any(e["事件"] == "文献筛选" and e.get("选中") == ["L1"] for e in tr11), \
    "轨迹应记录文献筛选结果"
assert any(e["事件"] == "全文抓取" and e.get("成功") for e in tr11), "轨迹应记录全文抓取成功"
search.search = lambda query, limit=5: [
    {"标题": "Title Only Paper", "年份": 2015, "来源": "替身", "摘要": None, "全文链接": None}]
_refine_before = state["refine_calls"]
hyp11b, _ = run.apply_literature(dict(hyp11))
assert state["refine_calls"] == _refine_before, "材料无摘要时不应调用优化"
assert "材料不足" in hyp11b["优化说明"], "无摘要时登记应标注材料不足、未优化"
tr11b = run.read_jsonl(run.TRACE_PATH)
assert any(e["事件"] == "文献材料不足" for e in tr11b), "轨迹应记录文献材料不足"
search.search, search.fetch_fulltext = _saved_search, _saved_fetch
print("验收 11 通过：摘要筛选、全文节选入优化、无摘要跳过优化")

# ---- 验收 12：提示硬化、带摘要才缓存、网络重试、预计算字段 ----
import http.client as _hc
import tempfile as _tf

assert "ivol20" in calc.FIELDS and "resid_ret" in calc.FIELDS, "预计算字段应进入字段清单"
assert "ivol20" in wide and wide["ivol20"].notna().any().any(), "宽表应含 ivol20 且有值"
_ok12, _bad12 = calc.check_whitelist("neg(ts_mean(ivol20, 20))")
assert _ok12, f"ivol20 公式应过白名单：{_bad12}"
assert "分析师" in agents.DATA_BOUNDARY and "C_t" in agents.DATA_BOUNDARY, "数据边界说明应写明不可用数据"
assert "ts_corr(3" in agents.EXPRESS_DOC and "sector_mean(1" in agents.EXPRESS_DOC, "算子清单应带参数个数"

_saved_fake = agents._fake
agents.set_fake(None)
_captured = {}
_saved_call = agents.call_model
agents.call_model = lambda role, system, user: (_captured.update(user=user),
                                                {"formula": "close"})[1]
agents.write_formula({"measure": "m", "mechanism": "x", "baseline_formula": "close"},
                     None, cap=20)
agents.call_model = _saved_call
assert "复杂度上限 20" in _captured["user"] and "算子调用次数" in _captured["user"], \
    "写公式提示应含复杂度上限与计数法"

# 网络错误重试一次：第一次断读、第二次成功
import os as _os
_os.environ.setdefault("DEEPSEEK_API_KEY", "dummy")
_post_calls = {"n": 0}
_saved_post = agents._post_once
def _flaky_post(body, key):
    _post_calls["n"] += 1
    if _post_calls["n"] == 1:
        raise _hc.IncompleteRead(b"partial", 7)
    return {"usage": {"prompt_tokens": 3, "completion_tokens": 2},
            "choices": [{"message": {"content": "{\"ok\": true}"}}]}
agents._post_once = _flaky_post
_out12 = agents.call_model("expand", "s", "u")
agents._post_once = _saved_post
assert _out12 == {"ok": True} and _post_calls["n"] == 2, "网络断读应自动重试一次并成功"
agents.set_fake(_saved_fake)

# 文献缓存：只有标题的不缓存、带摘要的缓存、无摘要的旧缓存不沿用
_saved_web, _saved_cache_path = search._web_search, search.CACHE_PATH
_tmp_cache = _tf.mktemp(suffix=".json")
search.CACHE_PATH = _tmp_cache
_items_title = [{"标题": "T1", "年份": None, "来源": "网络搜索", "摘要": None, "全文链接": None}]
_items_abs = [{"标题": "T2", "年份": None, "来源": "网络搜索", "摘要": "some snippet", "全文链接": None}]
_box = {"items": _items_title, "calls": 0}
def _fake_web(q, limit):
    _box["calls"] += 1
    return list(_box["items"])
search._web_search = _fake_web
search.search("q-title-only")
_cache_now = search._load_cache()
assert "q-title-only" not in _cache_now, "纯标题结果不应写入缓存"
_box["items"] = _items_abs
search.search("q-with-abstract")
_cache_now = search._load_cache()
assert "q-with-abstract" in _cache_now, "带摘要结果应写入缓存"
_calls_before = _box["calls"]
search.search("q-with-abstract")
assert _box["calls"] == _calls_before, "带摘要的缓存应直接命中、不再请求来源"
import json as _json
with open(_tmp_cache, "w", encoding="utf-8") as _fh:
    _json.dump({"q-stale": _items_title}, _fh, ensure_ascii=False)
search.search("q-stale")
assert _box["calls"] > _calls_before, "只有标题的旧缓存不应沿用，应重新检索"
search._web_search, search.CACHE_PATH = _saved_web, _saved_cache_path
print("验收 12 通过：提示硬化、带摘要才缓存、网络重试、预计算字段")

# ---- 验收 13：搜索做实——refine 零引用零修改判假优化失败，正常 refine 照常采纳 ----
_saved_search13 = search.search
search.search = lambda query, limit=5: [
    {"标题": "Short-Term Reversal and Liquidity", "年份": 2010, "来源": "替身",
     "摘要": "reversal profits are related to liquidity provision", "全文链接": None}]
hyp13 = dict(HYP)
hyp13["search_queries"] = ["short-term reversal liquidity"]
for _mode13 in ("空转", "空转无修改"):
    state["refine_mode"] = _mode13
    _refine_before13 = state["refine_calls"]
    hyp13r, _ = run.apply_literature(dict(hyp13))
    assert state["refine_calls"] == _refine_before13 + 1, "空转场景应确有调用优化"
    assert hyp13r["falsify"] == HYP["falsify"], \
        f"模式 {_mode13}：零引用零修改应判优化失败、保留初稿，实际登记 {hyp13r['falsify']}"
    assert hyp13r["优化说明"] == "检索后优化失败，用初稿", \
        f"模式 {_mode13}：登记应沿用失败标注，实际 {hyp13r['优化说明']}"
    assert not hyp13r.get("lit_refs"), "判失败时不应记录文献引用"
tr13 = run.read_jsonl(run.TRACE_PATH)
assert any(e["事件"] == "假设优化失败" and e.get("原因") == "无引用无修改" for e in tr13), \
    "轨迹应记假设优化失败事件并注明原因“无引用无修改”"
state["refine_mode"] = "采纳"
hyp13c, _ = run.apply_literature(dict(hyp13))
assert hyp13c["falsify"] == "（优化）" + HYP["falsify"], "含引用与修改的正常优化应照常采纳"
assert hyp13c["lit_refs"] == ["L1"], "正常采纳时应记录文献引用"
search.search = _saved_search13
print("验收 13 通过：零引用零修改判优化失败用初稿并留痕，正常优化照常采纳")

# ---- 验收 14：反馈做实——反馈包组装完整，登记校验无回应拒登、合格回应放行 ----
# （端到端的送达与拒登/登记在验收 15 的循环第二轮中验；预算发放模式删除后，
#   本项改验组装与校验两个部件本身。）
prior14 = {"方向": "反馈测试方向", "机制类别": "过度反应", "假设": "第一版假设",
           "结论": "否决", "失效层": "想法层", "工具版本": calc.TOOLING_VERSION,
           "预测核对": [{"dim": "市值组", "a": "小", "b": "大", "key": True,
                         "a值": 0.001, "b值": 0.012, "兑现": False},
                        {"dim": "持有期", "a": "20", "b": "5", "key": False,
                         "a值": 0.010, "b值": 0.002, "兑现": True}],
           "生成侧对抗": {"换皮判断": "与经典反转同源", "预测问题": "无",
                          "机制问题": "无", "引用问题": "无"},
           "检验侧对抗": {"失效解释": "小市值组并无更强反转", "未覆盖的失效方式": "未按波动分组",
                          "备注": ""}}
run.append_jsonl(run.RECORDS_PATH, prior14)
cand_base = dict(HYP)
cand_base.update({"direction": "反馈测试方向", "exp_refs": ["E001"],
                  "diff_from_rejected": "限定触发条件，与已否决方向不同",
                  "search_queries": []})
cand_no_resp = dict(cand_base)
cand_resp = dict(cand_base)
cand_resp["feedback_response"] = ("上次市值组关键预测未兑现（小市值组 IC 反低于大市值组）："
                                  "本版改以行业内相对跌幅触发，回应市值组维度")
fb14 = run.build_feedback(run.read_jsonl(run.RECORDS_PATH), "反馈测试方向",
                          run.load_terrain())
assert fb14 is not None, "有历史记录时应能组装反馈包"
assert fb14["上次尝试"]["失效层"] == "想法层", "反馈包应含上次失效层"
assert fb14["未兑现维度"] == ["市值组"], f"反馈包应列未兑现维度：{fb14['未兑现维度']}"
assert fb14["检验侧备忘录"]["失效解释"] == "小市值组并无更强反转", "反馈包应含检验侧失效备忘录"
assert fb14["数据地形"] and fb14["数据地形"][0].startswith("C11"), \
    f"反馈包应含数据地形清单（首条为扫描过关格子）：{fb14['数据地形'][:1]}"
assert run.build_feedback(run.read_jsonl(run.RECORDS_PATH), "从未出现过的方向",
                          []) is None, "无历史记录的方向反馈包应为 None"
_sectors14 = set(calc.SECTOR_OF.values())
_errs_no = run.validate_registration(cand_no_resp, [], [], sectors=_sectors14,
                                     feedback_dims=fb14["未兑现维度"])
assert any("feedback_response" in e for e in _errs_no), \
    f"有反馈包而无回应的候选应被拒登并注明：{_errs_no}"
_errs_ok = run.validate_registration(cand_resp, [], [], sectors=_sectors14,
                                     feedback_dims=fb14["未兑现维度"])
assert _errs_ok == [], f"带合格回应（点名未兑现维度）的候选应放行：{_errs_ok}"
print("验收 14 通过：反馈包组装完整、无回应拒登、合格回应放行")

# ---- 验收 15：旧模式已删除——裁决（judge）与预算发放不复存在 ----
assert not hasattr(agents, "judge_revision"), "裁决调用 judge_revision 应已删除"
assert not hasattr(run, "can_issue"), "预算发放函数 can_issue 应已删除"
assert not hasattr(run, "run_direction"), "预算发放驱动 run_direction 应已删除"
print("验收 15 通过：裁决（judge）与预算发放模式已删除")

# ---- 验收 16：普通网络搜索接入——片段材料走通筛选→优化链路，轨迹来源标注网络搜索 ----
_saved_search, _saved_fetch = search.search, search.fetch_fulltext
_saved_report = list(search.LAST_REPORT)
state["refine_mode"] = "采纳"
def _web_fake_search(query, limit=5):
    search.LAST_REPORT = [{"来源": "网络搜索", "结果": "返回 2 条"}]
    return [
        {"标题": "Reversals and the Returns to Liquidity Provision", "年份": None,
         "来源": "网络搜索",
         "摘要": "different aspects of liquidity impact the performance of short-run reversals",
         "全文链接": "https://example.org/rev"},
        {"标题": "Short-Term Reversal and Liquidity", "年份": None, "来源": "网络搜索",
         "摘要": "reversal profits are related to liquidity provision",
         "全文链接": "https://example.org/full"}]
search.search = _web_fake_search
search.fetch_fulltext = lambda item: {"节选": "FULLTEXT-EXCERPT", "字数": 5000}
hyp16 = dict(HYP)
hyp16["search_queries"] = ["short-term reversal liquidity provision"]
state["pick_payload"] = None
_refine_before16 = state["refine_calls"]
run.apply_literature(hyp16)
assert state["pick_payload"] is not None, "带片段的网络搜索材料应先调用筛选"
assert state["refine_calls"] > _refine_before16, "筛选后应调用优化（片段即摘要，链路照常）"
assert state["refine_payload"]["lit"][0].get("全文节选") == "FULLTEXT-EXCERPT", \
    "筛选选中篇目的全文节选应随材料交给优化"
import json as _json16
_ev16 = [e for e in run.read_jsonl(run.TRACE_PATH) if e["事件"] == "文献检索"]
assert _ev16, "轨迹应记录文献检索事件"
assert "网络搜索" in _json16.dumps(_ev16[-1].get("来源报告"), ensure_ascii=False), \
    "轨迹检索事件的来源报告应标注网络搜索"
search.search, search.fetch_fulltext = _saved_search, _saved_fetch
search.LAST_REPORT = _saved_report
print("验收 16 通过：网络搜索材料走通筛选→优化链路、轨迹检索事件来源标注为网络搜索")

# ---- 验收 17：假设锁定 + 因子内循环——假设只定一次，循环只改公式 ----
_saved_search17, _saved_fetch17 = search.search, search.fetch_fulltext
_search_calls17 = {"n": 0}
def _counting_search17(query, limit=5):
    _search_calls17["n"] += 1
    return [{"标题": "Short-Term Reversal and Liquidity", "年份": 2010, "来源": "替身",
             "摘要": "reversal profits are related to liquidity provision",
             "全文链接": "https://example.org/full"}]
search.search = _counting_search17
search.fetch_fulltext = lambda item: {"节选": "FULLTEXT-EXCERPT", "字数": 5000}
state["refine_mode"] = "采纳"
hyp17 = dict(HYP)
hyp17.update({"exp_refs": ["E001"],
              "diff_from_rejected": "限定触发条件，与已否决方向不同",
              "search_queries": ["short-term reversal liquidity"]})
state["expand_hyps"] = [hyp17]
state["formula_seq"] = ["-(close / delay(close, 5) - 1)",
                        "neg(ts_mean(close / delay(close, 1) - 1, 20))",
                        "neg(ts_mean(close / delay(close, 1) - 1, 60))"]
_exp_before17 = len(state["expand_payloads"])
_formula_before17 = len(state["formula_payloads"])
_attack_before17 = state["post_attack_calls"]
stats17 = {"done": 0, "passed": 0, "pred_total": 0, "pred_hit": 0,
           "candidates": 0, "rejected": 0, "backtested": 0, "inexpressible": 0}
clue17 = {"direction": "锁定循环测试方向", "phenomenon": "某种现象",
          "source": "某种收益来源", "category": "过度反应"}
run.run_fresh_loop(clue17, wide, classics, cap, set(calc.SECTOR_OF.values()), stats17)
recs17 = [r for r in run.read_jsonl(run.RECORDS_PATH) if r["方向"] == "锁定循环测试方向"]
assert len(recs17) == 3, f"因子循环应跑满三轮、各写一条记录：{len(recs17)} 条"
assert [r["轮次"] for r in recs17] == [1, 2, 3], "三条记录轮次应为 1、2、3"
assert all(r["结论"] == "否决" for r in recs17), "三轮均应被否决（预验过的公式）"
assert len({r["假设"] for r in recs17}) == 1, "三轮假设文本应相同（假设已锁定）"
assert all(r["登记"]["否定条件"].startswith("（对抗后修订）") for r in recs17), \
    "三轮登记应均为对抗后修订的锁定版"
assert recs17[0]["假设锁定文本"] == recs17[0]["假设"], "首轮应记假设锁定文本"
assert recs17[1]["假设锁定文本"] == "" and recs17[2]["假设锁定文本"] == "", \
    "假设锁定文本仅首轮记"
assert [r["修订类型"] for r in recs17] == ["无", "因子", "因子"], \
    f"修订类型应依次为无/因子/因子：{[r['修订类型'] for r in recs17]}"
assert recs17[0]["修改要求"] == "" and recs17[1]["修改要求"] and recs17[2]["修改要求"], \
    "首轮无修改要求，后两轮应记产生本轮的修改要求"
assert len(state["expand_payloads"]) - _exp_before17 == 1, "生命周期内展开应恰好 1 次"
assert _search_calls17["n"] == 1, f"生命周期内搜索应恰好 1 次：{_search_calls17['n']} 次"
assert state["post_attack_calls"] - _attack_before17 == 1, "对抗后修订应恰好发生 1 次"
_fp17 = state["formula_payloads"][_formula_before17:]
assert len(_fp17) == 3, f"write_formula 应恰好调用 3 次：{len(_fp17)} 次"
assert _fp17[0]["revision"] is None, "首轮 write_formula 不应带修订依据"
_rev2 = _fp17[1]["revision"]
assert _rev2 and _rev2["修改要求"] == recs17[1]["修改要求"], \
    "第二轮 payload 应含程序组装的修改要求"
assert _rev2["判定数字"]["IC均值"] == recs17[0]["判定数字"]["IC均值"], \
    "第二轮 payload 应含首轮 IC"
assert (_rev2["对抗备忘录"] or {}).get("失效解释") == "信号强度不足，IC 未达门槛", \
    "第二轮 payload 应含首轮检验侧对抗备忘录"
assert recs17[1]["修改依据"] and "对抗" in recs17[1]["修改依据"], \
    "第二轮记录应注明修改依据含对抗意见"
state["formula_seq"] = None
state["expand_hyps"] = None
search.search, search.fetch_fulltext = _saved_search17, _saved_fetch17
print("验收 17 通过：假设锁定（展开/搜索/对抗后修订各一次）、因子内循环三轮、"
      "修订类型无/因子/因子、修改依据含程序要求与对抗备忘录")

print("\n全部替身验收通过")
