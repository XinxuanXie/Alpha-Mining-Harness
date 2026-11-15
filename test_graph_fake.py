# test_graph_fake.py — 新系统替身验收（假模型 + 假回测，不碰真实账本与经验卡）
# 场景：propose 首式不合格被打回重写 → 主因子未过门 → modify 产出两条候选 →
#       候选一未过门、再改产出一条（追加队尾，不覆盖候选二）→ 候选二过门（测测试段、写卡）→
#       第 3 轮候选未过门 → 满轮写卡 → 结束。
# 另验：测试段幂等（重复触发不重测）、检查点落盘后可读回最终状态。
import json
import os
import sqlite3
import sys
import tempfile

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

import agents  # noqa: E402
import graph  # noqa: E402

F1 = "neg(close / delay(close, 20) - 1)"
C1 = "neg(ts_mean(close / delay(close, 1) - 1, 20))"
C2 = "ts_mean(volume, 5) / ts_mean(volume, 60)"
C3 = "neg(ts_std(close / delay(close, 1) - 1, 20))"
BAD = "foo(close)"
BAD2 = "where(ts_mean(close, 20) > close, close, 0)"   # 裸比较：白名单放行、求值器拒绝

def make_sc(ic, icir):
    return {"IC均值": ic, "ICIR": icir, "t值": 2.0, "覆盖率": 0.95, "因子自相关": 0.9,
            "各持有期IC": {"1": ic, "5": ic, "10": ic, "20": ic, "60": ic},
            "五组收益": [0.5, 0.6, 0.7, 0.8, 0.9], "分组单调性": 1.0,
            "多空价差": 0.004, "多空胜率": 0.55, "方向一致率": 0.53,
            "与经典因子最大相关": 0.5, "最大相关经典": "C01"}

FAKE_BT = {F1: make_sc(0.005, 0.05), C1: make_sc(0.001, 0.01),
           C2: make_sc(0.03, 0.30), C3: make_sc(-0.004, -0.05)}
test_calls = {"n": 0}
propose_calls = {"n": 0}

def fake_model(role, payload):
    if role == "propose":
        propose_calls["n"] += 1
        if propose_calls["n"] == 1:
            return {"名称": "坏公式二", "假设": "测试用", "公式": BAD2}
        if propose_calls["n"] == 2:
            return {"名称": "坏公式", "假设": "测试用", "公式": BAD}
        return {"名称": "主因子", "假设": "测试用机制，付钱者明确", "公式": F1}
    if role == "select_families":
        names = [graph.family_display_name(s) for s in ("02-reversal", "04-volatility-risk")]
        return {"家族": names}
    if role == "modify":
        if payload["formula"] == C1:
            return {"候选": [
                {"家族": "反转", "方法": "正交化", "改法": "测试", "公式": C3}]}
        if payload["formula"] == F1:
            return {"候选": [
                {"家族": "反转", "方法": "指数衰减加权", "改法": "测试", "公式": C1},
                {"家族": "波动与风险", "方法": "波动率缩放", "改法": "测试", "公式": C2}]}
        return {"候选": []}
    if role == "write_card":
        cause = "通过" if payload["formula"] == C2 else "衰减"
        return {"名称": "卡", "公式": payload["formula"], "死因分类": cause, "结论": "测试结论"}
    raise AssertionError(f"未知 role {role}")

def fake_test_verdict(formula):
    test_calls["n"] += 1
    return {"IC均值": 0.025, "ICIR": 0.22, "t值": 2.5,
            "各持有期IC": {"1": 0.01, "5": 0.015, "10": 0.02, "20": 0.025, "60": 0.03}}

def main():
    tmp = tempfile.mkdtemp(prefix="graph_fake_")
    graph.LEDGER_PATH = os.path.join(tmp, "records.jsonl")
    graph.CARDS_PATH = os.path.join(tmp, "experience_cards.jsonl")
    agents.set_fake(fake_model)
    # 试算用合成宽表（结构与真实宽表同形，只为验证求值器接受/拒绝）
    import numpy as np
    import pandas as pd
    rng = np.random.default_rng(7)
    idx = pd.bdate_range("2000-01-03", periods=500)
    cols = list(range(40))
    base = np.cumprod(1 + rng.normal(0, 0.01, (500, 40)), axis=0) * 100
    synth = {k: pd.DataFrame(base * (1 + rng.normal(0, 0.001, (500, 40))), index=idx, columns=cols)
             for k in ("open", "high", "low", "close", "mktcap")}
    synth["volume"] = pd.DataFrame(rng.integers(1_000, 9_000, (500, 40)), index=idx, columns=cols).astype(float)
    synth["mktret"] = pd.DataFrame(rng.normal(0, 0.01, (500, 40)), index=idx, columns=cols)
    synth["ivol20"] = pd.DataFrame(rng.uniform(0.1, 0.5, (500, 40)), index=idx, columns=cols)
    synth["resid_ret"] = pd.DataFrame(rng.normal(0, 0.01, (500, 40)), index=idx, columns=cols)
    graph.train_wide = lambda: synth
    graph.run_backtest = lambda f: FAKE_BT[f]
    graph.run_test_verdict = fake_test_verdict

    from langgraph.checkpoint.sqlite import SqliteSaver
    conn = sqlite3.connect(os.path.join(tmp, "ckpt.sqlite"), check_same_thread=False)
    app = graph.build_graph(checkpointer=SqliteSaver(conn))
    config = {"configurable": {"thread_id": "FAKE1"}, "recursion_limit": 300}
    final = app.invoke({"run_id": "FAKE1", "attempts": [], "cards_out": [], "queue": []}, config)

    got = [a["公式"] for a in final["attempts"]]
    assert got == [F1, C1, C2, C3], f"尝试顺序不符（应含同轮候选不被覆盖）：{got}"
    assert propose_calls["n"] == 3, "两条不合格公式（含裸比较）应各触发一次重写"
    assert test_calls["n"] == 1, f"测试段应只测一次，实际 {test_calls['n']}"
    cards = final["cards_out"]
    assert {c["公式"] for c in cards} == {C2, C3}, f"经验卡不符：{cards}"
    assert any(c["死因分类"] == "通过" for c in cards)

    # 幂等：对已测公式再触发裁决节点，不应产生第二次回测
    again = graph.node_test_verdict({"formula": C2, "run_id": "FAKE1"})
    assert test_calls["n"] == 1 and again["test_verdict"]["过门"] is True
    events = [json.loads(l) for l in open(graph.LEDGER_PATH, encoding="utf-8")]
    assert sum(1 for e in events if e.get("事件") == "测试段裁决") == 1

    # 检查点：最终状态可读回
    snap = app.get_state(config)
    assert snap.values["run_id"] == "FAKE1" and len(snap.values["attempts"]) == 4
    print("替身验收全部通过：回边重写、修改队列、过门裁决、满轮写卡、测试段幂等、检查点读回")


def test_route_caps():
    # 满轮次公式不合格：直接写卡，不回 modify
    assert graph.route_validate({"valid": False, "validate_fails": 1,
                                 "origin": "modify", "round": 3}) == "write_card"
    # 未满轮次：回来源重写
    assert graph.route_validate({"valid": False, "validate_fails": 1,
                                 "origin": "modify", "round": 2}) == "modify"
    assert graph.route_validate({"valid": True, "round": 3}) == "backtest"
    print("路由上限检查通过：满轮次不合格直接结案")

if __name__ == "__main__":
    main()
    test_route_caps()
