# chat.py — 因子挖掘交互 Agent（2026-11-15）
# 职责：在 graph.py 的端到端引擎之上提供对话层。用户可以给想法、给公式、问判断；
# Agent 自己也能提出想法、想清机制、写出公式并自行启动端到端运行，不需要逐项批准。
# 引擎的判定、账本、数据纪律不变：本层只负责对话与调度，工具调用一律走程序函数。
# 结构自上而下：模型调用 → 工具实现 → 后台运行线程 → 对话回合 → 主循环。

import json
import os
import queue
import sys
import threading
import urllib.request
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

import agents  # noqa: E402
import calc  # noqa: E402
import graph  # noqa: E402

# ============================================================
# 模型调用：与 agents.call_model 同口径（POST 到同一 API），
# 但保留多轮消息与工具调用。保险库启动器可替换 llm_raw。
# ============================================================
def llm_raw(body):
    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        raise RuntimeError("缺少环境变量 DEEPSEEK_API_KEY，无法调用模型")
    req = urllib.request.Request(
        agents.API_URL, data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as resp:
        return json.loads(resp.read().decode("utf-8"))

def llm_chat(messages, tools):
    body = {"model": agents.MODEL, "messages": messages,
            "tools": tools, "temperature": 0.7}
    data = llm_raw(body)
    return data["choices"][0]["message"]

# ============================================================
# 工具实现：每个工具是一个程序函数，返回值以文本回给模型
# ============================================================
COMPUTE_LOCK = threading.Lock()   # 回测是重活：同一时刻只跑一个（本机内存有限）

def tool_check_formula(formula):
    ok, errs = calc.check_whitelist(formula)
    if ok and calc.complexity(formula) > graph.COMPLEXITY_CAP:
        ok, errs = False, [f"复杂度 {calc.complexity(formula)} 超过上限 {graph.COMPLEXITY_CAP}"]
    if ok:
        try:
            calc.eval_formula(formula, graph._trial_wide())
        except Exception as e:
            ok, errs = False, [f"试算失败：{e}"]
    return f"检查通过，复杂度 {calc.complexity(formula)}" if ok else f"检查不通过：{'；'.join(map(str, errs))}"

def tool_backtest_formula(formula):
    chk = tool_check_formula(formula)
    if chk.startswith("检查不通过"):
        return chk
    with COMPUTE_LOCK:
        sc = graph.run_backtest(formula)
    passed = graph.judge(sc)
    return (f"成绩单（训练段）：\n{graph.scorecard_text(sc)}\n"
            f"判定：{'过门' if passed else '未过门'}（门：IC ≥ {graph.IC_GATE}，ICIR ≥ {graph.ICIR_GATE}）")

def tool_recent_results(limit=8):
    evs = [e for e in graph.ledger_events() if e.get("事件") == "回测"][-limit:]
    if not evs:
        return "账本里还没有回测记录。"
    lines = [f"{e['run_id']} 第{e['轮次']}轮 {e['名称']}：IC {e['IC']:.4f}，ICIR {e['ICIR']:.3f}，通过 {e['通过']}"
             for e in evs]
    cards = graph.load_cards()[-3:]
    if cards:
        lines.append("最近经验卡：")
        lines += [f"- {c['名称']}｜{c['死因分类']}｜{c['结论']}" for c in cards]
    return "\n".join(lines)

# ============================================================
# 后台运行线程：端到端任务排队逐个执行，主线程对话不阻塞
# ============================================================
JOBS = queue.Queue()
_STOP = object()   # 队列哨兵：与"无种子任务"（空字典）区分
WORKER = {"current": None, "done": 0, "stop": False}

def _new_run_id():
    return "F" + datetime.now().strftime("%Y%m%d%H%M%S")

def _run_one(seed):
    run_id = _new_run_id()
    WORKER["current"] = run_id
    init = {"run_id": run_id, "attempts": [], "cards_out": [], "queue": []}
    if seed and seed.get("formula"):
        init.update({"name": seed.get("name", ""), "hypothesis": seed.get("hypothesis", ""),
                     "formula": seed["formula"], "origin": "propose",
                     "round": 1, "validate_fails": 0})
        graph.ledger_append({"事件": "种子注入", "run_id": run_id,
                             "来源": "交互层", "公式": seed["formula"]})
    app = graph.compile_with_sqlite()
    config = {"configurable": {"thread_id": run_id}, "recursion_limit": 300}
    final = app.invoke(init, config)
    WORKER["current"] = None
    WORKER["done"] += 1
    best = max(final.get("attempts", []), key=lambda a: (a["IC"] or -9), default=None)
    print(f"\n[运行完成] {run_id}：共 {len(final.get('attempts', []))} 次尝试，"
          f"经验卡 {len(final.get('cards_out', []))} 张"
          + (f"；最佳 {best['名称']} IC {best['IC']:.4f} ICIR {best['ICIR']:.3f} 通过 {best['通过']}" if best else "")
          + "\n你> ", end="", flush=True)
    return run_id

def _worker_loop():
    while True:
        seed = JOBS.get()
        if seed is _STOP:
            break
        if WORKER["stop"]:
            WORKER["stop"] = False
            continue
        try:
            with COMPUTE_LOCK:
                _run_one(seed)
        except Exception as e:
            WORKER["current"] = None
            print(f"\n[运行出错] {e}\n你> ", end="", flush=True)

def tool_start_factor(name="", hypothesis="", formula=""):
    seed = {"name": name, "hypothesis": hypothesis, "formula": formula} if formula else {}
    JOBS.put(seed)
    return ("已启动一条端到端运行（后台执行，完成后会播报）。"
            if seed else "已启动一条端到端运行（后台执行，由引擎自行提出假设，完成后会播报）。")

def tool_start_auto(count=3):
    count = max(1, min(int(count), 10))
    for _ in range(count):
        JOBS.put({})
    return f"已排队 {count} 条自治运行（引擎自行提假设、修改、判定，逐条播报结果）。"

def tool_run_status():
    return (f"后台状态：{'正在跑 ' + WORKER['current'] if WORKER['current'] else '空闲'}，"
            f"排队 {JOBS.qsize()} 条，本次会话已完成 {WORKER['done']} 条。")

def tool_stop_auto():
    WORKER["stop"] = True
    return "已标记停止：当前这条跑完后不再继续排队中的运行。"

TOOLS = [
    {"type": "function", "function": {
        "name": "check_formula", "description": "程序检查一条公式：白名单、复杂度、试算。不回测。",
        "parameters": {"type": "object", "properties": {"formula": {"type": "string"}}, "required": ["formula"]}}},
    {"type": "function", "function": {
        "name": "backtest_formula", "description": "单独回测一条公式（仅训练段），返回 15 项成绩单与是否过门。",
        "parameters": {"type": "object", "properties": {"formula": {"type": "string"}}, "required": ["formula"]}}},
    {"type": "function", "function": {
        "name": "start_factor", "description": "启动一条端到端运行（后台）。给出公式则以该公式为种子（仍走检查、回测、修改、写卡全程）；不给则由引擎自行提出假设。",
        "parameters": {"type": "object", "properties": {
            "name": {"type": "string"}, "hypothesis": {"type": "string"}, "formula": {"type": "string"}}}}},
    {"type": "function", "function": {
        "name": "start_auto", "description": "排队多条自治运行，引擎自行提假设并端到端跑完。",
        "parameters": {"type": "object", "properties": {"count": {"type": "integer"}}}}},
    {"type": "function", "function": {
        "name": "run_status", "description": "查看后台运行状态。",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "stop_auto", "description": "停止排队中的后续运行（当前这条跑完为止）。",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "recent_results", "description": "读账本里最近的回测结果与经验卡。",
        "parameters": {"type": "object", "properties": {"limit": {"type": "integer"}}}}},
]

TOOL_FUNCS = {"check_formula": tool_check_formula, "backtest_formula": tool_backtest_formula,
              "start_factor": tool_start_factor, "start_auto": tool_start_auto,
              "run_status": tool_run_status, "stop_auto": tool_stop_auto,
              "recent_results": tool_recent_results}

# ============================================================
# 系统提示：角色、自治原则与纪律
# ============================================================
SYSTEM = f"""你是一名因子挖掘研究员，与用户在同一个终端里工作，目标是持续产出经得起检验的单因子想法。
你可以对话讨论，也可以调用工具动手：检查公式、单独回测、启动端到端运行、查看状态与结果。

工作方式：
- 用户给想法时，先把机制想清楚——谁付钱、为什么轮到他付、哪个量能测到它——再写成公式，然后直接用 start_factor 启动端到端运行，不需要等用户批准。
- 用户给公式时，先 check_formula，再视需要 backtest_formula 看成绩单，然后给出你的判断；值得跑全程的直接 start_factor。
- 用户没有想法时，你自己结合经典因子库与经验卡提出假设、写公式、启动运行。被问到时用 recent_results 与 run_status 回答。
- 汇报结果要带关键数字（IC、ICIR、是否过门），结论先行，不堆砌。

纪律（不可违反）：
- 判定门（IC ≥ 0.02、ICIR ≥ 0.2）、测试段与验证段的规矩由程序执行，你无权更改，也不要承诺绕过。
- 测出负值不反号当新因子；假设必须机制先行，不得从数据反推假设。
- {agents.DATA_BOUNDARY}
- 公式环境：{agents.EXPRESS_DOC}
"""

# ============================================================
# 对话回合：带工具循环，一轮最多 8 次工具调用
# ============================================================
def chat_turn(messages):
    for _ in range(8):
        msg = llm_chat(messages, TOOLS)
        messages.append(msg)
        calls = msg.get("tool_calls") or []
        if not calls:
            return msg.get("content") or ""
        for call in calls:
            fn = call["function"]["name"]
            try:
                args = json.loads(call["function"].get("arguments") or "{}")
                result = TOOL_FUNCS[fn](**args)
            except Exception as e:
                result = f"工具 {fn} 出错：{e}"
            messages.append({"role": "tool", "tool_call_id": call["id"], "content": str(result)})
    return "（本轮工具调用次数已达上限，先停在这里。）"

# ============================================================
# 主循环
# ============================================================
def main():
    threading.Thread(target=_worker_loop, daemon=True).start()
    messages = [{"role": "system", "content": SYSTEM}]
    print("因子挖掘交互 Agent。直接说想法、贴公式，或让我自己跑（例如：跑三条）。输入 退出 结束。")
    while True:
        try:
            text = input("你> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if text in ("退出", "exit", "quit"):
            break
        if not text:
            continue
        messages.append({"role": "user", "content": text})
        try:
            reply = chat_turn(messages)
        except Exception as e:
            reply = f"出错：{e}"
        messages.append({"role": "assistant", "content": reply})
        print(f"Agent> {reply}")
    print("结束。")

if __name__ == "__main__":
    main()
