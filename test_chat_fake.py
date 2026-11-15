# test_chat_fake.py — 交互层替身验收（假模型 + 假回测，不碰真实账本）
# 场景：用户给公式 → Agent 调 start_factor（种子端到端）与 backtest_formula →
#       后台线程跑完种子因子（过门、裁决、写卡）→ 用户问结果 → Agent 调 recent_results。
import json
import os
import sys
import tempfile
import threading
import time

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

import agents  # noqa: E402
import chat  # noqa: E402
import graph  # noqa: E402

F1 = "neg(close / delay(close, 20) - 1)"

def make_sc(ic, icir):
    return {"IC均值": ic, "ICIR": icir, "t值": 2.0, "覆盖率": 0.95, "因子自相关": 0.9,
            "各持有期IC": {"1": ic, "5": ic, "10": ic, "20": ic, "60": ic},
            "五组收益": [0.5, 0.6, 0.7, 0.8, 0.9], "分组单调性": 1.0,
            "多空价差": 0.004, "多空胜率": 0.55, "方向一致率": 0.53,
            "与经典因子最大相关": 0.5, "最大相关经典": "C01"}

# --- 对话模型脚本：按调用顺序返回预设消息 ---
def tool_msg(call_id, name, args):
    return {"choices": [{"message": {"role": "assistant", "content": None, "tool_calls": [
        {"id": call_id, "type": "function",
         "function": {"name": name, "arguments": json.dumps(args)}}]}}]}

SCRIPT = [
    tool_msg("c1", "start_factor", {"name": "种子反转", "hypothesis": "测试机制", "formula": F1}),
    tool_msg("c2", "backtest_formula", {"formula": F1}),
    {"choices": [{"message": {"role": "assistant", "content": "已启动，也单独测了。"}}]},
    tool_msg("c3", "recent_results", {"limit": 5}),
    {"choices": [{"message": {"role": "assistant", "content": "结果如上。"}}]},
]
script_iter = iter(SCRIPT)
chat.llm_raw = lambda body: next(script_iter)

# --- 引擎侧替身 ---
def fake_graph_model(role, payload):
    if role == "write_card":
        return {"名称": "卡", "公式": payload["formula"], "死因分类": "通过", "结论": "测试结论"}
    raise AssertionError(f"种子流程不应调用 {role}")

def main():
    tmp = tempfile.mkdtemp(prefix="chat_fake_")
    graph.LEDGER_PATH = os.path.join(tmp, "records.jsonl")
    graph.CARDS_PATH = os.path.join(tmp, "experience_cards.jsonl")
    graph._TRIAL_WIDE = None
    import sqlite3
    from langgraph.checkpoint.sqlite import SqliteSaver
    conn = sqlite3.connect(os.path.join(tmp, "ckpt.sqlite"), check_same_thread=False)
    graph.compile_with_sqlite = lambda: graph.build_graph(checkpointer=SqliteSaver(conn))
    agents.set_fake(fake_graph_model)
    graph.run_backtest = lambda f: make_sc(0.03, 0.30)
    graph.run_test_verdict = lambda f: {"IC均值": 0.025, "ICIR": 0.22, "t值": 2.5,
                                        "各持有期IC": {"1": 0.01, "5": 0.015, "10": 0.02, "20": 0.025, "60": 0.03}}
    import numpy as np
    import pandas as pd
    rng = np.random.default_rng(7)
    idx = pd.bdate_range("2000-01-03", periods=500)
    cols = list(range(40))
    base = np.cumprod(1 + rng.normal(0, 0.01, (500, 40)), axis=0) * 100
    synth = {k: pd.DataFrame(base, index=idx, columns=cols)
             for k in ("open", "high", "low", "close", "mktcap")}
    synth["volume"] = pd.DataFrame(rng.integers(1_000, 9_000, (500, 40)), index=idx, columns=cols).astype(float)
    synth["mktret"] = pd.DataFrame(rng.normal(0, 0.01, (500, 40)), index=idx, columns=cols)
    synth["ivol20"] = pd.DataFrame(rng.uniform(0.1, 0.5, (500, 40)), index=idx, columns=cols)
    synth["resid_ret"] = pd.DataFrame(rng.normal(0, 0.01, (500, 40)), index=idx, columns=cols)
    graph.train_wide = lambda: synth

    threading.Thread(target=chat._worker_loop, daemon=True).start()
    messages = [{"role": "system", "content": chat.SYSTEM}]
    messages.append({"role": "user", "content": f"用这个公式跑一条：{F1}"})
    reply = chat.chat_turn(messages)
    assert "已启动" in reply, reply
    tool_msgs = [m for m in messages if m.get("role") == "tool"]
    assert any("判定：过门" in m["content"] for m in tool_msgs), tool_msgs

    # 等后台种子运行完成
    for _ in range(100):
        if chat.WORKER["done"] >= 1 and chat.JOBS.empty():
            break
        time.sleep(0.2)
    assert chat.WORKER["done"] >= 1, "后台种子运行未完成"
    evs = [json.loads(l) for l in open(graph.LEDGER_PATH, encoding="utf-8")]
    kinds = [e["事件"] for e in evs]
    assert "种子注入" in kinds and "回测" in kinds and "测试段裁决" in kinds and "经验卡" in kinds, kinds

    messages.append({"role": "user", "content": "刚才那条结果如何"})
    reply = chat.chat_turn(messages)
    assert "结果如上" in reply
    tool_msgs = [m for m in messages if m.get("role") == "tool"]
    assert any("IC 0.0300" in m["content"] for m in tool_msgs), tool_msgs[-1]["content"]
    print("交互层替身验收通过：种子启动、单条回测、后台端到端、结果查询")

if __name__ == "__main__":
    main()
