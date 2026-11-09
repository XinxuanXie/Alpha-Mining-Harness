# factor_agent.py — 因子 Agent（做）
# 职责：把一条假设写成一条公式；公式必须能被 calc.py 算出数值。
# 数字一律由 calc.py 计算，本文件只负责生成公式与按报错重写。

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

import calc

# ============================================================
# 材料：数据说明与算子清单（与 spec 一致，是给模型的输入）
# ============================================================
DATA_DOC = """数据为日频行情，覆盖 2000-2016 年美股（含已退市股票）。
可用字段：open、high、low、close（均为复权价）、volume（成交股数）、mktcap（总市值，千美元）、mktret（当日市值加权市场收益率，同一日对全体股票相同）。
每只股票另有 GICS 行业分类（静态），供 rank_sector、sector_mean 算子使用。
公式在全部股票上逐日计算，因子值越大应代表预期收益越高（方向与假设一致）。"""

OPS_DOC = """公式是一条表达式字符串，只能使用下列算子与七个字段，常数只能是数字，窗口 d 必须是正整数。
算术：+ - * /、neg(a)、abs(a)、log(a)（a<=0 输出缺失）
比较：gt(a,b) a 大于 b 取 1，否则取 0（配 ts_mean 可得一段时间内条件成立的天数占比）
截面：rank(a) 当日截面排名，取值 0 至 1；rank_sector(a) 当日同行业内的截面排名，取值 0 至 1；sector_mean(a) 当日同行业平均值，组内每只股票都取该值
时序：delay(a,d) d 日前的值；delta(a,d) a 减 d 日前的值；
ts_mean(a,d)、ts_sum(a,d)、ts_std(a,d)、ts_min(a,d)、ts_max(a,d) 最近 d 日的均值、总和、标准差、最小值、最大值；
ts_rank(a,d) 当日值在最近 d 日中的排名，取值 0 至 1；ts_corr(a,b,d) 最近 d 日的相关系数。
缺失规则：算子所需位置缺失则结果缺失，时序窗口缺一日则结果缺失。
注意：delay 与 delta 只取时点值（当日与 d 日前），不要求窗口内每日都有值，不受窗口缺失规则影响。"""

# ============================================================
# 调用模型：DeepSeek 接口（OpenAI 兼容），key 从环境变量读
# ============================================================
def call_model(messages):
    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        raise RuntimeError("未设置环境变量 DEEPSEEK_API_KEY，无法调用模型")
    body = json.dumps({
        "model": os.environ.get("DEEPSEEK_MODEL", "deepseek-chat"),
        "messages": messages,
        "temperature": 0.7,
    }).encode("utf-8")
    # 网络瞬时故障（断连、超时）自动重试；临时重定向在单次尝试内跟随到底
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {key}"}
    url = "https://api.deepseek.com/chat/completions"
    last_err = None
    for wait in (0, 5, 15, 30, 60):
        if wait:
            time.sleep(wait)
        try:
            current = url
            for _hop in range(6):
                req = urllib.request.Request(current, data=body, headers=headers)
                try:
                    with urllib.request.urlopen(req, timeout=300) as resp:
                        data = json.loads(resp.read().decode("utf-8"))
                    return data["choices"][0]["message"]["content"]
                except urllib.error.HTTPError as e:
                    if e.code in (301, 302, 307, 308) and e.headers.get("Location"):
                        current = urllib.parse.urljoin(current, e.headers["Location"])
                        continue
                    raise
            raise RuntimeError("重定向次数过多")
        except Exception as e:
            last_err = e
    raise RuntimeError(f"模型接口调用失败（已重试）：{last_err}")

def _extract_json(text):
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("输出中找不到 JSON 对象")
    return json.loads(text[start:end + 1])

def _ask(messages, format_retries=2):
    """要求模型输出一个 JSON 对象；格式不对时把问题返回模型重出，上限 format_retries 次。"""
    last_err = None
    for _ in range(format_retries + 1):
        text = call_model(messages)
        try:
            return _extract_json(text)
        except (ValueError, json.JSONDecodeError) as e:
            last_err = e
            messages = messages + [
                {"role": "assistant", "content": text},
                {"role": "user", "content": f"上次输出不是合法的 JSON 对象（{e}）。请只输出一个 JSON 对象，不要任何其他文字。"},
            ]
    raise RuntimeError(f"模型输出格式重试达上限：{last_err}")

# ============================================================
# 核对：独立调用，只判公式实际算的量是不是假设说的量
# 不写公式、不判好坏；与写公式分开调用，避免自己确认自己
# ============================================================
CHECK_SYSTEM = """你是一名核对员。给你一条假设和一条按该假设写出的因子公式，你只判断公式实际计算的量与假设所说的量是否一致。
核对只筛明显错误：公式算的是与假设完全不同的量、方向相反、假设的关键量根本没有出现，才判不一致。近似构造不算不一致：以日收益之和近似累计收益、以平滑处理近似原始量，只要核心量没有被换掉，一律放行。
判断要点：核心量是否对应（用了什么字段、多长窗口、如何组合）；方向是否一致（假设说该量高的股票收益低，公式应取负或对排名取反）；表达式中约分后消失的量视为没有用上（例如 close/volume*volume 约分后等于 close，其中并不含成交量）。
只输出一个 JSON 对象，不要任何其他文字：
一致时：{"aligned": true}
不一致时：{"aligned": false, "problem": "公式实际算的是什么、与假设差在哪里（一两句话）"}
你不评价因子是否有效，不预测收益。"""

def check_alignment(hypothesis, formula):
    """返回 (True, None) 或 (False, 问题描述)。"""
    user = f"""假设内容：{hypothesis['hypothesis']}
经济逻辑：{hypothesis['logic']}
机制类别：{hypothesis['mechanism']}

公式：{formula}

{DATA_DOC}

{OPS_DOC}"""
    messages = [{"role": "system", "content": CHECK_SYSTEM}, {"role": "user", "content": user}]
    out = _ask(messages)
    if out.get("aligned") is True:
        return True, None
    return False, str(out.get("problem", "公式与假设不一致，未说明原因"))

# ============================================================
# 构建：写公式 → 程序校验并试算 → 独立核对 → 不行按报错重写（上限以 spec 参数为准）
# ============================================================
SYSTEM = """你是一名因子研究员，任务是把给定的假设忠实地写成一条因子公式。
只输出一个 JSON 对象，不要任何其他文字：
能表达时：{"formula": "表达式"}
确实无法用给定字段与算子表达时：{"buildable": false, "reason": "原因"}
公式的核心信号必须来自假设本身，不得用其他信号替代。"""

def build_factor(hypothesis, wide, max_rewrite=3):
    """返回 (公式, None) 或 (None, 无法表达的原因)。"""
    user = f"""假设内容：{hypothesis['hypothesis']}
经济逻辑：{hypothesis['logic']}
机制类别：{hypothesis['mechanism']}

{DATA_DOC}

{OPS_DOC}"""
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]
    last_err = None
    for attempt in range(max_rewrite + 1):
        out = _ask(messages)
        if out.get("buildable") is False:
            return None, str(out.get("reason", "模型判定无法表达"))
        formula = out.get("formula")
        if not isinstance(formula, str) or not formula.strip():
            last_err = "输出缺少 formula 字段"
        else:
            try:
                values = calc.eval_formula(formula, wide)
                if values.notna().sum().sum() == 0:
                    raise ValueError("公式算出的因子值全部为空")
            except ValueError as e:
                last_err = str(e)
            else:
                aligned, problem = check_alignment(hypothesis, formula)
                if aligned:
                    return formula, None
                last_err = f"公式实际计算的量与假设不一致：{problem}"
                print(f"   核对未通过（第 {attempt + 1} 版）：{problem}")
        if attempt < max_rewrite:
            messages = messages + [
                {"role": "assistant", "content": json.dumps(out, ensure_ascii=False)},
                {"role": "user", "content": f"这条公式无法使用：{last_err}。请修正后重新输出 JSON 对象，只改公式的表达方式，不得改变假设的核心信号。"},
            ]
    return None, f"重写达上限：{last_err}"

# ============================================================
# 自检（块二验收）：直接运行本文件时执行
# ============================================================
if __name__ == "__main__":
    wide = calc.load_wide()
    hyp = {"hypothesis": "过去 5 日跌幅越大的股票，未来收益越高",
           "logic": "短期过度反应后的均值回复", "mechanism": "反转"}
    try:
        formula, reason = build_factor(hyp, wide)
        print("公式:", formula)
        print("无法表达原因:", reason)
        if formula:
            ic = calc.compute_ic_mean(calc.eval_formula(formula, wide), wide["close"], 5)
            print("该公式 IC 均值（h=5）:", ic)
    except RuntimeError as e:
        print("无法执行真实模型验收：", e)
