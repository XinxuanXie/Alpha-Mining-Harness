# test_plumbing.py — 开发自检脚本（不属于系统本身）
# 用预设的模型回复替身验证块二、块三与调度的程序逻辑；
# 真实模型效果不在本脚本范围，需设置 DEEPSEEK_API_KEY 后单独验收。

import json
import os
import sys
import tempfile

import numpy as np

import calc
import factor_agent
import hypothesis_agent
import run as run_mod

PASS = []
def check(name, cond):
    PASS.append(cond)
    print(("PASS" if cond else "FAIL"), name)

def with_checker(build_stub):
    """替身分流：核对调用一律回复一致，其余调用交给 build_stub。"""
    def f(messages):
        if "核对员" in messages[0]["content"]:
            return '{"aligned": true}'
        return build_stub(messages)
    return f

# ---------- 块二：写错 → 按报错重写 → 成功 ----------
seq = iter([
    '{"formula": "foo(close)"}',
    '{"formula": "-delta(close, 5) / delay(close, 5)"}',
])
factor_agent.call_model = with_checker(lambda messages: next(seq))
wide = calc.load_wide()
hyp = {"hypothesis": "过去 5 日跌幅越大的股票，未来收益越高", "logic": "均值回复", "mechanism": "反转"}
formula, reason = factor_agent.build_factor(hyp, wide)
check("块二 报错后重写成功", formula == "-delta(close, 5) / delay(close, 5)" and reason is None)

# ---------- 块二：模型判定无法表达 ----------
factor_agent.call_model = with_checker(lambda messages: '{"buildable": false, "reason": "需要财务报表数据，现有字段不足"}')
formula, reason = factor_agent.build_factor(hyp, wide)
check("块二 无法表达路径", formula is None and "财务报表" in reason)

# ---------- 块二：反复写错 → 达上限记无法表达 ----------
calls = {"n": 0}
def always_bad(messages):
    calls["n"] += 1
    return '{"formula": "ts_mean(close, 0)"}'
factor_agent.call_model = with_checker(always_bad)
formula, reason = factor_agent.build_factor(hyp, wide, max_rewrite=3)
check("块二 重写达上限", formula is None and "达上限" in reason and calls["n"] == 4)

# ---------- 块二：核对驳回 → 按意见重写 → 成功 ----------
seq = iter([
    '{"formula": "ts_mean(close, 5)"}',
    '{"formula": "-delta(close, 5) / delay(close, 5)"}',
])
def picky_checker(messages):
    if "核对员" in messages[0]["content"]:
        if "ts_mean(close, 5)" in messages[-1]["content"]:
            return '{"aligned": false, "problem": "公式算的是5日均价，不是5日跌幅"}'
        return '{"aligned": true}'
    return next(seq)
factor_agent.call_model = picky_checker
formula, reason = factor_agent.build_factor(hyp, wide)
check("块二 核对驳回后重写成功", formula == "-delta(close, 5) / delay(close, 5)" and reason is None)

# ---------- 块二：核对始终不一致 → 达上限记无法表达 ----------
builds = {"n": 0}
def always_misaligned(messages):
    if "核对员" in messages[0]["content"]:
        return '{"aligned": false, "problem": "公式算的量与假设不一致"}'
    builds["n"] += 1
    return '{"formula": "-delta(close, 5) / delay(close, 5)"}'
factor_agent.call_model = always_misaligned
formula, reason = factor_agent.build_factor(hyp, wide, max_rewrite=3)
check("块二 核对达上限记无法表达", formula is None and "不一致" in reason and builds["n"] == 4)

# ---------- 块二附：新数据与新算子（gt / rank_sector / mktret / 分行业 IC） ----------
day_cnt = wide["close"].notna().sum(axis=1)
check("成分口径 日均可用股票约 500", 450 < float(day_cnt.mean()) < 560)
prop = calc.eval_formula("ts_mean(gt(close, delay(close, 1)), 20)", wide)
pv = prop.to_numpy()
check("新算子 gt 占比可算且在 0-1", np.nanmin(pv) >= 0 and np.nanmax(pv) <= 1 and np.isfinite(pv).sum() > 1_000_000)
sec_f = calc.eval_formula("rank_sector(close / delay(close, 20) - 1)", wide)
sv = sec_f.to_numpy()
check("新算子 rank_sector 可算且在 0-1", np.nanmin(sv) >= 0 and np.nanmax(sv) <= 1 and np.isfinite(sv).sum() > 1_000_000)
m_new = calc.compute_metrics(sec_f, wide, 5)
check("分行业 IC 已算出", isinstance(m_new.get("分行业IC"), dict) and len(m_new["分行业IC"]) >= 10)

# ---------- 块三：去重与校验 ----------
hypothesis_agent.call_model = lambda messages: json.dumps([
    {"quantity": "已试过的假设", "logic": "x", "mechanism": "动量"},
    {"quantity": "新假设一", "logic": "x", "mechanism": "动量"},
    {"quantity": "新假设一", "logic": "x", "mechanism": "动量"},
    {"quantity": "新假设二", "logic": "x", "mechanism": "不存在的类别"},
    {"quantity": "新假设三", "logic": "x", "mechanism": "规模"},
], ensure_ascii=False)
out = hypothesis_agent.propose(["已试过的假设越大的股票，未来收益越高"], batch=8)
check("块三 去重与类别校验", [o["hypothesis"] for o in out] == ["新假设一越大的股票，未来收益越高", "新假设三越大的股票，未来收益越高"])

# ---------- 块三：格式重试 ----------
seq = iter(["这不是JSON", '[{"quantity": "新假设九", "logic": "x", "mechanism": "反转"}]'])
hypothesis_agent.call_model = lambda messages: next(seq)
out = hypothesis_agent.propose([], batch=1)
check("块三 格式重试后成功", len(out) == 1 and out[0]["hypothesis"] == "新假设九越大的股票，未来收益越高")

# ---------- 块四：两轮端到端（替身模型 + 真实计算） ----------
tmp = tempfile.mkdtemp()
run_mod.RECORDS_PATH = os.path.join(tmp, "records.jsonl")
run_mod.PARAMS_LOG = os.path.join(tmp, "params_log.jsonl")
seen_user = []
round_no = {"n": 0}
def fake_hyp_model(messages):
    round_no["n"] += 1
    seen_user.append(messages[-1]["content"])
    r = round_no["n"]
    return json.dumps([
        {"quantity": f"第{r}轮假设{i}", "logic": "x", "mechanism": "反转"} for i in range(3)
    ], ensure_ascii=False)
hypothesis_agent.call_model = fake_hyp_model
factor_agent.call_model = with_checker(lambda messages: '{"formula": "-delta(close, 5) / delay(close, 5)"}')
sys.argv = ["run.py", "--rounds", "2", "--batch", "3"]
run_mod.main()
recs = calc.read_records(run_mod.RECORDS_PATH)
check("块四 两轮共 6 条记录", len(recs) == 6)
check("块四 每条五项齐全", all(set(r.keys()) == {"轮次", "假设", "公式", "判定数字", "结论"} for r in recs))
check("块四 轮次为 1,1,1,2,2,2", [r["轮次"] for r in recs] == [1, 1, 1, 2, 2, 2])
check("块四 第二轮已试清单含第一轮假设", "第1轮假设0" in seen_user[1])
check("块四 判定数字为指标组", all(isinstance(r["判定数字"], dict) and isinstance(r["判定数字"]["IC均值"], float) for r in recs))

print("\n总计:", sum(PASS), "/", len(PASS), "通过")
sys.exit(0 if all(PASS) else 1)
