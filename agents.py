# agents.py — 模型调用层（2026-11-15 新系统）
# 职责：三个模型调用——提出假设（propose_factor）、修改因子（modify_factor）、写经验卡（write_card）。
# 只生成，不计算数字，不写任何文件；判定归 graph.py 按程序规则执行，数字一律由 calc.py 计算。
# 本文件只把结构化输入拼成提示词、把模型输出解析成字典。
# 模型：DeepSeek（环境变量 DEEPSEEK_API_KEY，或由保险库启动器替换 call_model）。测试时可用 set_fake 注入替身。

import http.client
import json
import os
import time
import urllib.error
import urllib.request

API_URL = "https://api.deepseek.com/chat/completions"
MODEL = "deepseek-chat"
CALL_COUNT = 0          # 本进程的模型调用次数（供 run.py 算单位算力产出）
USAGE = {"输入token": 0, "输出token": 0}   # 本进程累计 token 用量（取自 API 返回的 usage）
_fake = None            # 替身函数：fake(role, payload) -> dict；测试时注入

def usage_snapshot():
    """当前累计用量快照：调用次数与输入/输出 token。"""
    return {"calls": CALL_COUNT, "in": USAGE["输入token"], "out": USAGE["输出token"]}

def usage_since(snap):
    """自快照以来的增量用量。"""
    return {"calls": CALL_COUNT - snap["calls"],
            "in": USAGE["输入token"] - snap["in"],
            "out": USAGE["输出token"] - snap["out"]}

def set_fake(fn):
    global _fake
    _fake = fn

# ============================================================
# 底层调用：发一次对话请求，要求返回一个 JSON 对象
# 网络类错误（断读、连接失败、超时）自动重试一次；服务器明确回错（如 401）不重试。
# ============================================================
_NET_ERRORS = (http.client.IncompleteRead, TimeoutError, ConnectionError)

def _post_once(body, key):
    req = urllib.request.Request(API_URL, data=json.dumps(body).encode("utf-8"),
                                 headers={"Authorization": f"Bearer {key}",
                                          "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as resp:
        return json.loads(resp.read().decode("utf-8"))

def _is_network_error(e):
    if isinstance(e, urllib.error.HTTPError):
        return False   # 服务器已明确应答（如鉴权失败），重试无意义
    return isinstance(e, _NET_ERRORS + (urllib.error.URLError,))

def call_model(role, system, user):
    global CALL_COUNT
    CALL_COUNT += 1
    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        raise RuntimeError("缺少环境变量 DEEPSEEK_API_KEY，无法调用模型")
    body = {
        "model": MODEL,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "response_format": {"type": "json_object"},
        "temperature": 0.7,
    }
    data = None
    for attempt in (1, 2):
        try:
            data = _post_once(body, key)
            break
        except Exception as e:
            if attempt == 2 or not _is_network_error(e):
                raise
            time.sleep(2)
    u = data.get("usage") or {}
    USAGE["输入token"] += u.get("prompt_tokens") or 0
    USAGE["输出token"] += u.get("completion_tokens") or 0
    return json.loads(data["choices"][0]["message"]["content"])

def _dispatch(role, payload, system, user):
    if _fake is not None:
        return _fake(role, payload)
    return call_model(role, system, user)

# ============================================================
# 可表达范围说明：写公式时必须让模型知道环境里有什么、没有什么
# ============================================================
EXPRESS_DOC = """可用日频字段：open、high、low、close、volume、mktcap（市值）、mktret（市场当日收益，对全体股票相同）、
ivol20（特质波动：过去 20 日个股收益对市场收益回归的残差标准差，程序预计算）、
resid_ret（当日残差收益：个股收益减去市场模型拟合值，程序预计算）。
可用算子（括号内为参数个数）：neg(1)、abs(1)、log(1)、sign(1，符号)、sqrt(1)、inverse(1，倒数)、rank(1，截面排名)、rank_sector(1，行业内排名)、
sector_mean(1，行业均值)、zscore(1，截面标准化)、winsorize(1，截面 1%/99% 分位截尾)、gt(2，大于取 1)、power(2，幂)、signed_power(2，带符号幂)、
resid(2，截面一元回归残差：第一个量对第二个量逐日回归取残差)、delay(2，延迟 d 日)、delta(2，与 d 日前之差)、
ts_mean(2)、ts_sum(2)、ts_std(2)、ts_min(2)、ts_max(2)、ts_rank(2，时序排名)、ts_median(2，时序中位数)、ts_skew(2，时序偏度)、
ts_kurt(2，时序峰度)、ts_decay(2，指数衰减平均，半衰期 d 日)、ts_count(2，窗口求和，对 0/1 量即为计数)、
ts_argmax(2，距窗口内最大值出现的天数)、ts_argmin(2，距窗口内最小值出现的天数)、ts_corr(3，两序列 d 日滚动相关),
ts_beta(3，滚动回归斜率：第一个量对第二个量)、where(3，条件选择：第一个量 > 0 取第二个量，否则取第三个量），
以及 + - * / 四则运算。时序算子的最后一个参数是窗口 d，为正整数（power 与 signed_power 的第二个参数是指数，不在此列）。
不可表达的构造：多变量回归（resid 只支持一个控制变量，ts_beta 只给斜率）；时序回归残差；
需要财务报表、分析师预期等未提供数据的量；变长窗口。ivol20 与 resid_ret 为程序预计算的市场模型残差类字段，窗口固定 20 日。
公式只能使用当日及以前的数据。"""

DATA_BOUNDARY = """数据边界（硬约束）：系统只有日频价量、市值、市场收益、行业归属与 ivol20、resid_ret 两个预计算字段。
不存在分析师覆盖人数、财务报表字段、涨跌停价格、新闻与文本数据，也没有这些数据的代理变量约定。
机制若依赖这类数据，不要提出；计算方式与基准公式中不得引用不存在的量，不得自创未定义符号（如 C_t）。"""

# ============================================================
# 调用一：提出假设（假设 Agent）
# 输入：2–3 个家族的全部条目原文 + 相关经验卡
# 输出：{"名称": str, "假设": str, "公式": str}，一轮一条
# ============================================================
PROPOSE_SYSTEM = """你是一名量化研究员。给你几个经典因子家族的全部条目原文和过去因子的经验卡，
你的任务是提出一条新的因子假设。条目是测量技术与构造手法的参考，不是现成零件：
先想清现象与机制，再决定用哪个量把这件事量出来，甚至可以把一个家族的测法用到另一个家族的对象上。
假设必须写清机制与收益来源：谁付钱、为什么轮到他付。只输出 JSON，不要输出其他文字。"""

def propose_factor(families_text, cards_text):
    user = f"""【经典因子条目】
{families_text}

【相关经验卡】
{cards_text}

【可表达范围】
{EXPRESS_DOC}

{DATA_BOUNDARY}

输出 JSON：{{"名称": "因子名", "假设": "机制与收益来源，一段", "公式": "公式字符串"}}
要求：只给一条；公式复杂度（算子调用与字段引用计数）不超过 20；公式只用当日及以前的数据。"""
    return _dispatch("propose", {"families": families_text}, PROPOSE_SYSTEM, user)

# ============================================================
# 调用二：修改因子（修改 Agent）
# 输入：原因子 + 完整成绩单 + 选定家族的条目原文 + 方法谱系
# 输出：{"候选": [{"家族": str, "方法": str, "改法": str, "公式": str}]}
# ============================================================
MODIFY_SYSTEM = """你是一名量化研究员。给你一条已回测的因子、它的完整成绩单、几个经典因子家族的条目原文和一份修改方法谱系，
你的任务是给出修改后的因子。每个家族出一条：用该家族的一个量，结合谱系中的一种方法改造原因子。
先用审判型方法（正交化、收益分解）判定成分，再用增益型方法改进；只改公式层，不改原假设。
方法名用谱系中的专业术语。只输出 JSON，不要输出其他文字。"""

METHODS_DOC = """方法谱系（方法 — 适用情形）：
波动率缩放（volatility scaling）— 极端组由高波动股票主导；分组收益不单调
中性化（neutralization）— 因子暴露主要来自行业构成或已知风格
正交化（orthogonalization）— 与已有因子相关过高，需判定独立信息含量（审判型）
残差收益构造（residual return construction）— 原始收益中市场共同成分占比过高
指数衰减加权（exponential decay weighting）— 信号随持有期衰减，信息在窗口内老化
缩尾处理（winsorization）— 少数极端观测主导截面排序
状态条件化（regime conditioning）— 机制明确限定了生效状态
收益分解（return decomposition）— 同一收益量混合了成因不同的成分（审判型）
间隔期构造（skip-period construction）— 近端收益的反转成分污染形成期信号
时序标准化（time-series standardization）— 截面水平差异过大，需以个股自身历史为基准"""

def modify_factor(name, hypothesis, formula, scorecard_text, families_text):
    user = f"""【原因子】
名称：{name}
假设：{hypothesis}
公式：{formula}

【完整成绩单】
{scorecard_text}

【经典因子条目】
{families_text}

【方法谱系】
{METHODS_DOC}

【可表达范围】
{EXPRESS_DOC}

输出 JSON：{{"候选": [{{"家族": "家族名", "方法": "谱系中的方法名", "改法": "改法说明一句", "公式": "公式字符串"}}]}}
要求：每个家族一条；公式复杂度不超过 20；负结果不许反号改方向。"""
    return _dispatch("modify", {"formula": formula}, MODIFY_SYSTEM, user)

# ============================================================
# 调用三：写经验卡（终结时）
# 输入：因子的名称、假设、公式、各轮成绩单摘要与最终结局
# 输出：{"名称": str, "公式": str, "死因分类": str, "结论": str}
# ============================================================
CARD_SYSTEM = """你是一名量化研究员。一条因子已经终结，你负责把这一轮的教训写成一张经验卡，
供以后的假设与修改环节检索使用。只写事实与判定，不写推测；推测性的判断要标明是推测。
死因分类只能从下列选一个：壳效应、乘积稀释、方向相反、持有期错配、测量失败、衰减、通过。
只输出 JSON，不要输出其他文字。"""

def write_card(name, hypothesis, formula, history_text, outcome):
    user = f"""【因子】
名称：{name}
假设：{hypothesis}
最终公式：{formula}
结局：{outcome}

【各轮记录】
{history_text}

输出 JSON：{{"名称": "{name}", "公式": "最终公式", "死因分类": "七类之一", "结论": "一句结论"}}
结论只写一句，写清这个因子测到了什么、死在哪一层或为什么通过。"""
    return _dispatch("write_card", {"formula": formula}, CARD_SYSTEM, user)

# ============================================================
# 调用四：为修改选家族（修改 Agent 的前置步）
# 输入：原因子 + 完整成绩单 + 家族索引（家族名与描述）
# 输出：{"家族": [家族名, ...]}，按成绩单特征选 3–4 个
# ============================================================
SELECT_SYSTEM = """你是一名量化研究员。一条因子回测未过门，你负责为修改环节挑选参考家族。
先看成绩单的特征（哪一项最弱、持有期形状、分组形态），再从家族索引里挑与这些特征对口的家族：
审判它到底测到了什么，优先于给它加东西。只输出 JSON，不要输出其他文字。"""

def select_modify_families(name, formula, scorecard_text, index_text):
    user = f"""【原因子】
名称：{name}
公式：{formula}

【完整成绩单】
{scorecard_text}

【家族索引】
{index_text}

输出 JSON：{{"家族": ["家族名", ...]}}
要求：选 3–4 个家族，家族名与索引中的写法一致。"""
    return _dispatch("select_families", {"formula": formula}, SELECT_SYSTEM, user)
