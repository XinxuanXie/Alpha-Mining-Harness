# graph.py — 因子挖掘系统（LangGraph 版，2026-11-15）
# 职责：按《因子挖掘系统方案（2026-11-15）》组装状态图并执行。
# 程序节点负责抽材料、检查、回测、判定、测试段裁决、落盘；Agent 节点只做提出假设、选家族、修改、写卡。
# 判定一律由程序按门执行，模型不参与判定。数据边界：生成与修改只用训练段；测试段仅裁决节点加载；
# 验证段任何环节不加载。
# 运行顺序自上而下：参数 → 账本与数据 → 成绩单与判定 → 材料 → 状态 → 节点 → 路由 → 组图。

import hashlib
import json
import operator
import os
import random
from typing import Annotated, Optional, TypedDict

import numpy as np
import pandas as pd

import agents
import calc

# ============================================================
# 参数（本文件内部固定值，与规格一致）
# ============================================================
BASE = os.path.dirname(os.path.abspath(__file__))
LIB_DIR = os.path.join(BASE, "classic_library")
LIB_INDEX = os.path.join(BASE, "classic_library.md")
LEDGER_PATH = os.path.join(BASE, "records.jsonl")
CARDS_PATH = os.path.join(BASE, "experience_cards.jsonl")
CHECKPOINT_PATH = os.path.join(BASE, "checkpoints.sqlite")
IC_GATE = 0.02          # 判定门：20 日 Rank IC
ICIR_GATE = 0.2         # 判定门：ICIR
COMPLEXITY_CAP = 20     # 复杂度上限
MAX_ROUND = 3           # 因子总轮次上限（含首版）
VALIDATE_RETRY = 2      # 公式未通过程序检查时的重写上限
MAX_ATTEMPTS = 13       # 单 thread 回测总上限（1＋3＋9 满树）；防检查失败重写使队列无限增长
TEST_START, TEST_END = "2017-01-01", "2019-12-31"   # 测试段
DEATH_CAUSES = ["壳效应", "乘积稀释", "方向相反", "持有期错配", "测量失败", "衰减", "通过"]

# 家族文件：文件名（去扩展名）→ 路径；家族显示名取文件首行
FAMILY_FILES = {}
for _fn in sorted(os.listdir(LIB_DIR)):
    if _fn.endswith(".md"):
        FAMILY_FILES[_fn[:-3]] = os.path.join(LIB_DIR, _fn)

# ============================================================
# 账本与经验卡：只追加，不改写；更正靠追加更正记录
# ============================================================
def ledger_append(event):
    event = dict(event)
    with open(LEDGER_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")

def ledger_events():
    if not os.path.exists(LEDGER_PATH):
        return []
    out = []
    with open(LEDGER_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return out

def formula_key(formula):
    return hashlib.sha256(formula.encode("utf-8")).hexdigest()[:16]

def find_test_verdict(key):
    """按幂等键查已有测试段裁决；查到返回裁决字典，查不到返回 None。"""
    for ev in ledger_events():
        if ev.get("事件") == "测试段裁决" and ev.get("公式键") == key:
            return ev.get("裁决")
    return None

def load_cards():
    if not os.path.exists(CARDS_PATH):
        return []
    out = []
    with open(CARDS_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return out

def append_card(card):
    with open(CARDS_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(card, ensure_ascii=False) + "\n")

def relevant_cards(families, limit=12):
    """取与所抽家族相关的经验卡：名称/结论/公式命中家族关键词者优先，再补最近的卡。"""
    cards = load_cards()
    keys = set()
    for fam in families:
        keys.add(fam)
        for kw in ("动量", "反转", "季节", "波动", "流动性", "换手", "规模", "价格",
                   "隔夜", "日内", "扩散", "公司行为", "增发", "量价", "趋势", "均线",
                   "K线", "形态", "摆动", "超买超卖"):
            if kw in fam:
                keys.add(kw)
    hit = [c for c in cards
           if any(k in (c.get("名称", "") + c.get("结论", "") + c.get("公式", "")) for k in keys)]
    picked = hit[-limit:]
    if len(picked) < limit:
        for c in reversed(cards):
            if c not in picked:
                picked.append(c)
            if len(picked) >= limit:
                break
    return picked

def cards_text(cards):
    if not cards:
        return "（暂无经验卡）"
    return "\n".join(
        f"- {c.get('名称')}｜{c.get('死因分类')}｜{c.get('结论')}" for c in cards)

# ============================================================
# 数据加载：训练段宽表缓存；测试段宽表按已验证口径单独加载
# ============================================================
_TRAIN_WIDE = None
_TEST_WIDE = None

def train_wide():
    global _TRAIN_WIDE
    if _TRAIN_WIDE is None:
        _TRAIN_WIDE = calc.load_wide()
    return _TRAIN_WIDE

def test_wide():
    """测试段口径（与历次手工裁决一致）：放宽加载上限补齐标签，公式在全宽表上求值，
    因子值切 2017–2019 后算指标。仅裁决节点调用。"""
    global _TEST_WIDE
    if _TEST_WIDE is None:
        old = calc.TRAIN_END
        calc.TRAIN_END = "2020-04-30"
        try:
            _TEST_WIDE = calc.load_wide()
        finally:
            calc.TRAIN_END = old
    return _TEST_WIDE

# ============================================================
# 成绩单（15 项）与判定（两门）
# ============================================================
def build_scorecard(fac, wide):
    """成绩单组装已收回 calc.scorecard，本函数仅作转发。"""
    return calc.scorecard(fac, wide)

def judge(scorecard):
    ic, icir = scorecard.get("IC均值"), scorecard.get("ICIR")
    return bool(ic is not None and ic >= IC_GATE and icir is not None and icir >= ICIR_GATE)

def scorecard_text(sc):
    if not sc:
        return "（无成绩单）"
    def r(x, n=4):
        return None if x is None else round(x, n)
    return "\n".join([
        f"总判：20日IC {r(sc['IC均值'])}，ICIR {r(sc['ICIR'], 3)}，t {r(sc['t值'], 2)}，覆盖率 {r(sc['覆盖率'], 3)}，因子自相关 {r(sc['因子自相关'], 3)}",
        f"持有期IC：{ {k: r(v) for k, v in sc['各持有期IC'].items()} }",
        f"五组收益：{[round(x * 100, 2) for x in sc['五组收益']]}%，单调性 {r(sc['分组单调性'], 2)}，多空价差 {round(sc['多空价差'] * 100, 2)}%，多空胜率 {r(sc['多空胜率'], 3)}，方向一致率 {r(sc['方向一致率'], 3)}",
    ])

def run_backtest(formula):
    """训练段回测：返回成绩单。验收时可被替身替换（见 test_graph_fake.py）。"""
    wide = train_wide()
    fac = calc.eval_formula(formula, wide)
    return build_scorecard(fac, wide)

def run_test_verdict(formula):
    """测试段裁决：返回成绩单（仅 IC/ICIR/t/持有期用于裁决口径展示）。"""
    wide = test_wide()
    fac = calc.eval_formula(formula, wide)
    test = fac[(fac.index >= TEST_START) & (fac.index <= TEST_END)]
    return calc.compute_metrics(test, wide)

# ============================================================
# 材料：家族条目原文与索引
# ============================================================
def family_text(stem):
    with open(FAMILY_FILES[stem], encoding="utf-8") as f:
        return f.read()

def families_text(stems):
    return "\n\n".join(family_text(s) for s in stems)

def library_index_text():
    with open(LIB_INDEX, encoding="utf-8") as f:
        return f.read()

def family_display_name(stem):
    """家族显示名：取家族文件首行标题（如「一、动量」）。"""
    with open(FAMILY_FILES[stem], encoding="utf-8") as f:
        first = f.readline().strip().lstrip("#").strip()
    return first or stem

# ============================================================
# 状态对象：一条因子的全部状态只装在这一个对象里
# ============================================================
class FactorState(TypedDict, total=False):
    run_id: str
    families: list            # 本轮抽到的家族（文件名词干）
    materials: str            # 家族条目原文
    cards_text: str           # 相关经验卡文本
    name: str
    hypothesis: str
    formula: str
    origin: str               # 当前公式来源：propose / modify
    method_note: str          # 当前公式的家族与方法注明（候选时）
    round: int
    validate_fails: int
    last_error: str
    valid: bool
    scorecard: dict
    verdict: bool
    queue: list               # 待处理的候选队列（顺序处理）
    has_next: bool            # dispatch 是否取到下一条候选
    attempts: Annotated[list, operator.add]
    test_verdict: Optional[dict]
    outcome: str              # 当前因子结局：通过 / 判死 / 满轮次 / 公式不合格
    cards_out: Annotated[list, operator.add]

# ============================================================
# 节点
# ============================================================
def node_draw_materials(state):
    rng = random.Random(state["run_id"])
    stems = rng.sample(sorted(FAMILY_FILES), 3)
    cards = relevant_cards([family_display_name(s) for s in stems])
    ledger_append({"事件": "抽材料", "run_id": state["run_id"],
                   "家族": [family_display_name(s) for s in stems]})
    return {"families": stems, "materials": families_text(stems),
            "cards_text": cards_text(cards)}

def node_propose(state):
    out = agents.propose_factor(state["materials"], state["cards_text"])
    ledger_append({"事件": "提出假设", "run_id": state["run_id"],
                   "名称": out.get("名称"), "公式": out.get("公式")})
    return {"name": out.get("名称", ""), "hypothesis": out.get("假设", ""),
            "formula": out.get("公式", ""), "origin": "propose",
            "method_note": "", "round": 1, "validate_fails": 0, "last_error": ""}

_TRIAL_WIDE = None

def _trial_wide():
    """试算用宽表：训练宽表的前 400 行。结构性错误（求值器不支持的节点等）与数据无关，
    在切片上必然复现；窗口不足只产生缺失值，不报错。"""
    global _TRIAL_WIDE
    if _TRIAL_WIDE is None:
        tw = {}
        for k, v in train_wide().items():
            try:
                tw[k] = v.iloc[:400]
            except Exception:
                tw[k] = v
        _TRIAL_WIDE = tw
    return _TRIAL_WIDE

def node_validate(state):
    formula = state.get("formula", "")
    ok, errs = calc.check_whitelist(formula)
    comp = calc.complexity(formula) if ok else None
    if ok and comp > COMPLEXITY_CAP:
        ok, errs = False, [f"复杂度 {comp} 超过上限 {COMPLEXITY_CAP}"]
    if ok:
        # 白名单只查算子与字段名，查不出求值器不支持的表达式结构（如裸比较 > <）。
        # 以求值器本身为准做一次切片试算，过不了同样打回重写，避免回测节点崩溃。
        try:
            calc.eval_formula(formula, _trial_wide())
        except Exception as e:
            ok, errs = False, [f"试算失败：{e}"]
    fails = state.get("validate_fails", 0) + (0 if ok else 1)
    ledger_append({"事件": "程序检查", "run_id": state["run_id"], "公式": formula,
                   "通过": ok, "错误": errs if not ok else []})
    return {"valid": ok, "validate_fails": fails,
            "last_error": "" if ok else "；".join(str(e) for e in errs)}

def node_backtest(state):
    sc = run_backtest(state["formula"])
    passed = judge(sc)
    attempt = {"轮次": state.get("round", 1), "名称": state.get("name"),
               "公式": state["formula"], "来源": state.get("origin"),
               "方法注明": state.get("method_note", ""),
               "IC": sc["IC均值"], "ICIR": sc["ICIR"], "通过": passed}
    ledger_append({"事件": "回测", "run_id": state["run_id"], **attempt})
    return {"scorecard": sc, "verdict": passed, "attempts": [attempt]}

def node_modify(state):
    if state.get("round", 1) >= MAX_ROUND:
        return {"queue": state.get("queue") or []}
    index = library_index_text()
    sel = agents.select_modify_families(
        state["name"], state["formula"], scorecard_text(state["scorecard"]), index)
    stems_by_name = {}
    for stem in FAMILY_FILES:
        stems_by_name[family_display_name(stem)] = stem
        stems_by_name[stem] = stem
    chosen = []
    for fam in sel.get("家族", []):
        stem = stems_by_name.get(fam)
        if stem and stem not in chosen:
            chosen.append(stem)
    if not chosen:
        chosen = state.get("families", [])[:3]
    out = agents.modify_factor(
        state["name"], state["hypothesis"], state["formula"],
        scorecard_text(state["scorecard"]), families_text(chosen))
    queue = []
    for cand in out.get("候选", []):
        if cand.get("公式"):
            queue.append({
                "name": f"{state['name']}（{cand.get('方法', '修改')}）",
                "hypothesis": state["hypothesis"],
                "formula": cand["公式"],
                "method_note": f"{cand.get('家族', '')} × {cand.get('方法', '')}：{cand.get('改法', '')}",
                "round": state.get("round", 1) + 1,
            })
    ledger_append({"事件": "修改产出", "run_id": state["run_id"],
                   "候选数": len(queue),
                   "候选": [{"公式": q["formula"], "方法注明": q["method_note"]} for q in queue]})
    # 新候选追加到队尾，不覆盖尚未处理的同轮候选（按轮次广度优先逐条处理）；
    # 已回测数＋排队数达到总上限后不再追加，保证 thread 必然终止
    pending = (state.get("queue") or [])
    room = MAX_ATTEMPTS - len(state.get("attempts", [])) - len(pending)
    return {"queue": pending + queue[:max(room, 0)]}

def node_dispatch(state):
    """从队列取下一条候选装入工作字段；has_next 标记是否取到。
    成绩单不清空：候选公式未通过检查而回 modify 重写时，要用父因子的成绩单。"""
    queue = state.get("queue") or []
    if not queue or len(state.get("attempts", [])) >= MAX_ATTEMPTS:
        return {"has_next": False, "queue": []}
    nxt, rest = queue[0], queue[1:]
    return {"queue": rest, "has_next": True,
            "name": nxt["name"], "hypothesis": nxt["hypothesis"],
            "formula": nxt["formula"], "method_note": nxt.get("method_note", ""),
            "origin": "modify", "round": nxt.get("round", 2),
            "validate_fails": 0, "last_error": "", "outcome": ""}

def node_test_verdict(state):
    key = formula_key(state["formula"])
    existing = find_test_verdict(key)
    if existing is not None:
        return {"test_verdict": existing}
    m = run_test_verdict(state["formula"])
    裁决 = {"IC均值": m["IC均值"], "ICIR": m["ICIR"], "t值": m["t值"],
            "各持有期IC": m["各持有期IC"],
            "过门": bool(m["IC均值"] is not None and m["IC均值"] >= IC_GATE
                        and m["ICIR"] is not None and m["ICIR"] >= ICIR_GATE)}
    ledger_append({"事件": "测试段裁决", "run_id": state["run_id"],
                   "公式键": key, "公式": state["formula"], "裁决": 裁决})
    return {"test_verdict": 裁决}

def _history_text(state):
    lines = []
    for a in state.get("attempts", []):
        lines.append(f"第{a['轮次']}轮（{a.get('来源')}）{a['公式']} → IC {a['IC']}，ICIR {a['ICIR']}，通过 {a['通过']}")
    return "\n".join(lines) if lines else "（无回测记录）"

def node_write_card(state):
    outcome = state.get("outcome")
    if not outcome:
        if state.get("verdict"):
            outcome = "通过"
        elif not state.get("valid", True) and state.get("validate_fails", 0) > VALIDATE_RETRY:
            outcome = "公式不合格"
        elif state.get("round", 1) >= MAX_ROUND:
            outcome = "满轮次"
        else:
            outcome = "判死"
    card = None
    for _ in range(2):
        out = agents.write_card(state.get("name", ""), state.get("hypothesis", ""),
                                state.get("formula", ""), _history_text(state), outcome)
        if all(out.get(k) for k in ("名称", "公式", "死因分类", "结论")) \
                and out["死因分类"] in DEATH_CAUSES:
            card = {k: out[k] for k in ("名称", "公式", "死因分类", "结论")}
            break
    if card is None:
        card = {"名称": state.get("name", ""), "公式": state.get("formula", ""),
                "死因分类": "通过" if outcome == "通过" else "测量失败",
                "结论": "经验卡生成未通过格式校验，按结局由程序补记。"}
    append_card(card)
    ledger_append({"事件": "经验卡", "run_id": state["run_id"], "卡": card})
    return {"cards_out": [card]}

# ============================================================
# 路由
# ============================================================
def route_validate(state):
    if state.get("valid"):
        return "backtest"
    # 满轮次的公式不合格直接结案，不得回 modify 产生超轮次候选
    if state.get("validate_fails", 0) > VALIDATE_RETRY or state.get("round", 1) >= MAX_ROUND:
        return "write_card"
    return state.get("origin", "propose")

def route_modify(state):
    # 修改无产出：当前因子就此终结，写卡；有候选：进 dispatch 逐条处理
    return "dispatch" if state.get("queue") else "write_card"

def route_backtest(state):
    if state.get("verdict"):
        return "test_verdict"
    if state.get("round", 1) < MAX_ROUND:
        return "modify"
    return "write_card"

def dispatch_entry(state):
    """write_card 之后：队列还有候选则继续取下一条，否则结束。"""
    return "dispatch" if state.get("queue") else "__end__"

# ============================================================
# 组图
# ============================================================
def build_graph(checkpointer=None):
    from langgraph.graph import StateGraph, START, END

    g = StateGraph(FactorState)
    g.add_node("draw_materials", node_draw_materials)
    g.add_node("propose", node_propose)
    g.add_node("validate", node_validate)
    g.add_node("backtest", node_backtest)
    g.add_node("modify", node_modify)
    g.add_node("dispatch", node_dispatch)
    g.add_node("test_verdict", node_test_verdict)
    g.add_node("write_card", node_write_card)

    g.add_edge(START, "draw_materials")
    # 种子入口：初始状态已带公式（来自交互层或人工指定）时跳过提出，直接检查；
    # 材料照常抽取，供检查不合格回 propose 重写时使用
    g.add_conditional_edges("draw_materials", _after_draw,
                            {"propose": "propose", "validate": "validate"})
    g.add_edge("propose", "validate")
    g.add_conditional_edges("validate", route_validate,
                            {"backtest": "backtest", "propose": "propose",
                             "modify": "modify", "write_card": "write_card"})
    g.add_conditional_edges("backtest", route_backtest,
                            {"test_verdict": "test_verdict", "modify": "modify",
                             "write_card": "write_card"})
    g.add_conditional_edges("modify", route_modify,
                            {"dispatch": "dispatch", "write_card": "write_card"})
    # dispatch 装入下一条候选后去 validate；队列为空（状态无新公式）时结束。
    g.add_conditional_edges("dispatch", _route_after_dispatch,
                            {"validate": "validate", "__end__": END})
    g.add_edge("test_verdict", "write_card")
    g.add_conditional_edges("write_card", dispatch_entry,
                            {"dispatch": "dispatch", "__end__": END})
    return g.compile(checkpointer=checkpointer)

def _after_draw(state):
    return "validate" if state.get("formula") else "propose"

def _route_after_dispatch(state):
    return "validate" if state.get("has_next") else "__end__"

def compile_with_sqlite(db_path=CHECKPOINT_PATH):
    import sqlite3
    from langgraph.checkpoint.sqlite import SqliteSaver
    conn = sqlite3.connect(db_path, check_same_thread=False)
    saver = SqliteSaver(conn)
    return build_graph(checkpointer=saver)
