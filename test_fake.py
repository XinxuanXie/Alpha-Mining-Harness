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
         "judge_seq": None, "judge_payloads": [],
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
        if payload.get("guidance"):
            # 改因子轮次：按裁决修改要求给出与基准不同的公式
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
    if role == "judge":
        state["judge_payloads"].append(payload)
        if state["judge_seq"]:
            return state["judge_seq"].pop(0)
        return {"决定": "改假设", "理由": "默认裁决：改假设", "修改要求": ""}
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
rec8, _, _, _ = run.process_hypothesis(hyp8, wide, classics, cap)
assert rec8["登记"]["否定条件"] == "（优化）" + HYP["falsify"], "合格的优化稿应被采用并锁定"
assert rec8["登记"]["文献引用"] == ["L1"], "登记应记录文献引用"
assert "L1" in rec8["登记"]["优化说明"], "登记应记录优化说明"
assert state["attack_reg_payload"]["lit"], "生成侧对抗应收到检索材料"
assert state["attack_reg_payload"]["lit"][0]["编号"] == "L1", "对抗收到的材料应带编号"
assert "引用问题" in rec8["生成侧对抗"], "生成侧对抗输出应含引用问题字段"
state["refine_mode"] = "不采纳"
rec8b, _, _, _ = run.process_hypothesis(dict(hyp8), wide, classics, cap)
assert rec8b["登记"]["否定条件"] == HYP["falsify"], "优化稿不合格时应保留初稿"
assert rec8b["登记"]["文献引用"] == [], "未采纳时不应记录文献引用"
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

# ---- 验收 10：检索来源报告、429 重试与 Crossref 请求（打桩来源，不联网） ----
import importlib as _importlib
import urllib.error as _urlerr
_importlib.reload(search)   # 验收 8 把 search.search 换成了打桩函数，这里恢复真函数再测
_saved_sources, _saved_cache_path = search.SOURCES, search.CACHE_PATH
search.CACHE_PATH = os.path.join(BASE, "lit_cache_test.json")
if os.path.exists(search.CACHE_PATH):
    os.remove(search.CACHE_PATH)
def _bad_src(query, limit):
    raise RuntimeError("源故障")
def _ok_src(query, limit):
    return [{"标题": "T", "年份": 2020, "来源": "替身源", "摘要": None}]
search.SOURCES = (_bad_src, _ok_src)
_got = search.search("验收十检索词甲", limit=3)
assert _got and _got[0]["标题"] == "T", "第一源失败应降级到第二源"
_rep = search.last_report()
assert _rep[0]["结果"] == "失败" and "源故障" in _rep[0]["错误"], f"来源报告应记失败原因：{_rep}"
assert _rep[1]["结果"].startswith("返回"), f"来源报告应记成功条数：{_rep}"
_flaky = {"n": 0}
def _flaky_src(query, limit):
    _flaky["n"] += 1
    if _flaky["n"] == 1:
        raise _urlerr.HTTPError("https://x", 429, "Too Many", {}, None)
    return [{"标题": "R", "年份": 2021, "来源": "替身源", "摘要": None}]
search.SOURCES = (_flaky_src,)
_got2 = search.search("验收十检索词乙", limit=3)
assert _got2 and _got2[0]["标题"] == "R", "429 后应重试并拿到结果"
assert "重试成功" in search.last_report()[0]["结果"], "来源报告应记 429 重试成功"
_captured = {}
_orig_get = search._get_json
search._get_json = lambda url: (_captured.setdefault("url", url),
                                {"message": {"items": [{"title": ["X"], "published": {"date-parts": [[2021]]},
                                                         "abstract": "<jats:p>Some &amp; finding</jats:p>"}]}})[1]
_out = search._crossref("q", 3)
search._get_json = _orig_get
assert "select=" not in _captured["url"], "Crossref 请求不应带 select 参数（无效字段会被整单拒绝）"
assert _out[0]["标题"] == "X" and _out[0]["年份"] == 2021, "Crossref 返回应能解析标题与年份"
assert _out[0]["摘要"] == "Some & finding", f"Crossref 摘要应去标签解实体：{_out[0]['摘要']}"
_terms = search._arxiv_term_sets("idiosyncratic volatility change reversal noise trader arbitrage limits")
assert _terms[0] == ["idiosyncratic", "volatility", "arbitrage"] and len(_terms[1]) == 2, \
    f"arXiv 词组应为核心 3 词与降级 2 词：{_terms}"
search.SOURCES, search.CACHE_PATH = _saved_sources, _saved_cache_path
if os.path.exists(os.path.join(BASE, "lit_cache_test.json")):
    os.remove(os.path.join(BASE, "lit_cache_test.json"))
print("验收 10 通过：来源成败入报告、429 重试、Crossref 请求无无效参数")

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
rec11, _, _, _ = run.process_hypothesis(hyp11, wide, classics, cap)
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
rec11b, _, _, _ = run.process_hypothesis(dict(hyp11), wide, classics, cap)
assert state["refine_calls"] == _refine_before, "材料无摘要时不应调用优化"
assert "材料不足" in rec11b["登记"]["优化说明"], "无摘要时登记应标注材料不足、未优化"
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
                     None, cap=14)
agents.call_model = _saved_call
assert "复杂度上限 14" in _captured["user"] and "算子调用次数" in _captured["user"], \
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
_saved_attempt, _saved_cache_path = search._attempt, search.CACHE_PATH
_tmp_cache = _tf.mktemp(suffix=".json")
search.CACHE_PATH = _tmp_cache
_items_title = [{"标题": "T1", "年份": 2020, "来源": "替身", "摘要": None, "全文链接": None}]
_items_abs = [{"标题": "T2", "年份": 2020, "来源": "替身", "摘要": "some abstract", "全文链接": None}]
_box = {"items": _items_title, "calls": 0}
def _fake_attempt(fn, q, limit):
    _box["calls"] += 1
    return list(_box["items"]), {"来源": "替身源", "结果": f"返回 {len(_box['items'])} 条"}
search._attempt = _fake_attempt
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
search._attempt, search.CACHE_PATH = _saved_attempt, _saved_cache_path
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
    rec13, _, _, _ = run.process_hypothesis(dict(hyp13), wide, classics, cap)
    assert state["refine_calls"] == _refine_before13 + 1, "空转场景应确有调用优化"
    assert rec13["登记"]["否定条件"] == HYP["falsify"], \
        f"模式 {_mode13}：零引用零修改应判优化失败、保留初稿，实际登记 {rec13['登记']['否定条件']}"
    assert rec13["登记"]["优化说明"] == "检索后优化失败，用初稿", \
        f"模式 {_mode13}：登记应沿用失败标注，实际 {rec13['登记']['优化说明']}"
    assert rec13["登记"]["文献引用"] == [], "判失败时不应记录文献引用"
tr13 = run.read_jsonl(run.TRACE_PATH)
assert any(e["事件"] == "假设优化失败" and e.get("原因") == "无引用无修改" for e in tr13), \
    "轨迹应记假设优化失败事件并注明原因“无引用无修改”"
state["refine_mode"] = "采纳"
rec13c, _, _, _ = run.process_hypothesis(dict(hyp13), wide, classics, cap)
assert rec13c["登记"]["否定条件"] == "（优化）" + HYP["falsify"], "含引用与修改的正常优化应照常采纳"
assert rec13c["登记"]["文献引用"] == ["L1"], "正常采纳时应记录文献引用"
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

# ---- 验收 15：新假设循环——逐轮裁决分流（改假设/改因子/终止），无改进停止 ----
state["formula_mode"] = "回登记基准"
_fresh_base = dict(HYP)
_fresh_base.update({"exp_refs": ["E001"], "search_queries": [],
                    "diff_from_rejected": "限定触发条件，与已否决方向不同"})
_resp_all_dims = ("逐条回应上次未兑现预测：市值组维度改以组内相对量触发；"
                  "持有期维度调整信号窗口与关键预测期限；行业维度限定高覆盖行业验证")
# 情形 A：第 1 轮否决 → 第 2 轮带反馈包换构造再测，账本两条、轮次与父假设成链
hyp_a1 = dict(_fresh_base)
hyp_a1["hypothesis"] = "循环甲第一轮假设：过去 5 日跌幅越大的股票，未来收益越高"
hyp_a2 = dict(_fresh_base)
hyp_a2.update({"hypothesis": "循环甲第二轮假设：近期波动越低的股票，未来收益越高",
               "measure": "过去 60 日日收益标准差取负",
               "baseline_formula": "neg(ts_std(close / delay(close, 1) - 1, 60))",
               "mechanism": "低波动股票被杠杆约束投资者忽视，赚风险定价偏差"})
hyp_a2_resp = dict(hyp_a2)
hyp_a2_resp["feedback_response"] = _resp_all_dims
_pay_before_a = len(state["expand_payloads"])
_rej_before_a = sum(1 for e in run.read_jsonl(run.TRACE_PATH) if e["事件"] == "拒登")
_judge_before_a = len(state["judge_payloads"])
state["judge_seq"] = [{"决定": "改假设", "理由": "构造与假设脱节，换假设",
                        "修改要求": "换一个构造角度"}]
state["expand_seq"] = [[hyp_a1], [hyp_a2, hyp_a2_resp]]
stats15a = {"done": run.MAX_TOTAL_ATTEMPTS - 2, "passed": 0, "pred_total": 0,
            "pred_hit": 0, "candidates": 0, "rejected": 0, "backtested": 0,
            "inexpressible": 0}
clue15a = {"direction": "循环新方向甲", "phenomenon": "某种现象",
           "source": "某种收益来源", "category": "过度反应"}
run.run_fresh_loop(clue15a, wide, classics, cap, set(calc.SECTOR_OF.values()), stats15a)
recs15a = [r for r in run.read_jsonl(run.RECORDS_PATH) if r["方向"] == "循环新方向甲"]
assert len(recs15a) == 2, f"新假设循环应完成两轮、各写一条记录：{len(recs15a)} 条"
assert [r["轮次"] for r in recs15a] == [1, 2], f"两条记录轮次应为 1、2：{[r.get('轮次') for r in recs15a]}"
assert recs15a[0]["父假设"] == "", "第 1 轮父假设应为空"
assert recs15a[1]["父假设"] == recs15a[0]["假设"], "第 2 轮父假设应为第 1 轮假设文本"
assert recs15a[0]["结论"] == "否决", f"第 1 轮应被否决以进入反馈轮：{recs15a[0]['结论']}"
assert recs15a[0]["修订类型"] == "无" and recs15a[0]["裁决理由"] == "", "首轮修订类型应为无"
assert recs15a[1]["修订类型"] == "假设", "裁决改假设时第 2 轮修订类型应为假设"
assert recs15a[1]["裁决理由"] == "构造与假设脱节，换假设", "第 2 轮应记上一轮裁决理由"
_ev_a = state["judge_payloads"][_judge_before_a]["evidence"]
assert _ev_a["失效层"] == recs15a[0]["失效层"] and _ev_a["判定数字"] is not None, \
    "裁决应收到本轮证据（失效层与判定数字）"
_pays_a = state["expand_payloads"][_pay_before_a:]
assert len(_pays_a) == 2, "循环应恰好展开两次（第三轮前因总上限停止）"
assert _pays_a[0]["feedback"] is None, "第 1 轮展开不应带反馈包"
assert _pays_a[1]["feedback"] is not None, "第 2 轮展开应带反馈包"
assert _pays_a[1]["feedback"]["上次尝试"]["失效层"] == recs15a[0]["失效层"], \
    "第 2 轮反馈包应含第 1 轮失效层"
_rej_a = [e for e in run.read_jsonl(run.TRACE_PATH) if e["事件"] == "拒登"][_rej_before_a:]
assert any(any("feedback_response" in x for x in e.get("原因", [])) for e in _rej_a), \
    "第 2 轮无 feedback_response 的候选应被拒登并注明原因，随后合格回应才登记"
# 情形 B：第 2 轮交回与第 1 轮实质相同的假设 → 无改进停止，不再有下一轮
hyp_b1 = dict(_fresh_base)
hyp_b1["hypothesis"] = "循环乙第一轮假设：过去 5 日跌幅越大的股票，未来收益越高"
hyp_b2 = dict(_fresh_base)
hyp_b2.update({"hypothesis": "循环乙第二轮假设：与第一轮同一构造",
               "feedback_response": _resp_all_dims})
state["expand_seq"] = [[hyp_b1], [hyp_b2]]
state["judge_seq"] = [{"决定": "改假设", "理由": "换假设再试", "修改要求": ""}]
stats15b = {"done": 0, "passed": 0, "pred_total": 0, "pred_hit": 0,
            "candidates": 0, "rejected": 0, "backtested": 0, "inexpressible": 0}
clue15b = {"direction": "循环新方向乙", "phenomenon": "某种现象",
           "source": "某种收益来源", "category": "过度反应"}
run.run_fresh_loop(clue15b, wide, classics, cap, set(calc.SECTOR_OF.values()), stats15b)
recs15b = [r for r in run.read_jsonl(run.RECORDS_PATH) if r["方向"] == "循环新方向乙"]
assert len(recs15b) == 1, f"无改进时第 2 轮不应写记录、不应有第 3 轮：{len(recs15b)} 条"
assert recs15b[0]["轮次"] == 1 and recs15b[0]["父假设"] == "", "乙方向应只有第 1 轮记录"
tr15 = run.read_jsonl(run.TRACE_PATH)
assert any(e["事件"] == "循环停止" and e.get("方向") == "循环新方向乙"
           and "无改进" in (e.get("原因") or "") for e in tr15), \
    "无改进应在轨迹记「循环停止」并注明原因"
# 情形 C：裁决改因子 → 下一轮沿用同一登记、公式按修改要求重写；再裁决终止 → 循环结束
hyp_c1 = dict(_fresh_base)
hyp_c1["hypothesis"] = "循环丙第一轮假设：过去 5 日跌幅越大的股票，未来收益越高"
state["expand_seq"] = [[hyp_c1]]
state["judge_seq"] = [{"决定": "改因子", "理由": "假设成立但窗口太短",
                        "修改要求": "把构造窗口拉长到 20 日"},
                       {"决定": "终止", "理由": "两轮均无信号", "修改要求": ""}]
_pay_before_c = len(state["expand_payloads"])
stats15c = {"done": 0, "passed": 0, "pred_total": 0, "pred_hit": 0,
            "candidates": 0, "rejected": 0, "backtested": 0, "inexpressible": 0}
clue15c = {"direction": "循环新方向丙", "phenomenon": "某种现象",
           "source": "某种收益来源", "category": "过度反应"}
run.run_fresh_loop(clue15c, wide, classics, cap, set(calc.SECTOR_OF.values()), stats15c)
recs15c = [r for r in run.read_jsonl(run.RECORDS_PATH) if r["方向"] == "循环新方向丙"]
assert len(recs15c) == 2, f"改因子后裁决终止，丙方向应恰有两轮记录：{len(recs15c)} 条"
assert recs15c[1]["假设"] == recs15c[0]["假设"], "改因子轮次应沿用同一登记假设，假设文本不变"
assert recs15c[1]["公式"] == state["revise_formula"], "改因子轮次公式应按修改要求重写"
assert recs15c[1]["公式"] != recs15c[0]["公式"], "改因子轮次公式应与上一轮不同"
assert recs15c[1]["修订类型"] == "因子", "裁决改因子时下一轮修订类型应为因子"
assert recs15c[1]["裁决理由"] == "假设成立但窗口太短", "改因子轮次应记裁决理由"
assert recs15c[1]["轮次"] == 2 and recs15c[1]["父假设"] == recs15c[0]["假设"], \
    "改因子轮次轮次与父假设应成链"
assert len(state["expand_payloads"]) - _pay_before_c == 1, "改因子轮次不应再展开"
tr15c = [e for e in run.read_jsonl(run.TRACE_PATH)
         if e["事件"] == "裁决" and e.get("方向") == "循环新方向丙"]
assert [e["决定"] for e in tr15c] == ["改因子", "终止"], \
    f"轨迹应依次记裁决改因子、终止：{[e.get('决定') for e in tr15c]}"
assert stats15c["done"] == 2, "丙方向两轮均应计入完成数"
state["expand_seq"] = None
state["judge_seq"] = None
state["formula_mode"] = None
assert not hasattr(run, "can_issue"), "预算发放函数 can_issue 应已删除"
assert not hasattr(run, "run_direction"), "预算发放驱动 run_direction 应已删除"
print("验收 15 通过：新假设循环两轮成链（轮次/父假设）、次轮带反馈包、无改进停止、"
      "裁决三路（改假设/改因子/终止）分流正确、旧模式已删除")

print("\n全部替身验收通过")
