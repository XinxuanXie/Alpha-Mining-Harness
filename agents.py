# agents.py — 模型调用层
# 职责：五个模型调用——展开假设、写公式、写讲评、生成侧对抗审查、检验侧对抗审查。
# 只生成与判断，不计算数字，不写任何文件；对抗审查只留痕，不参与判定（判定归 run.py 按程序规则执行）。
# 数字一律由 calc.py 计算；本文件只把结构化输入拼成提示词、把模型输出解析成字典。
# 模型：DeepSeek（环境变量 DEEPSEEK_API_KEY）。测试时可用 set_fake 注入替身，跳过真实调用。

import json
import os
import urllib.request

API_URL = "https://api.deepseek.com/chat/completions"
MODEL = "deepseek-chat"
CALL_COUNT = 0          # 本进程的模型调用次数（供 run.py 算单位算力产出）
_fake = None            # 替身函数：fake(role, payload) -> dict；测试时注入

def set_fake(fn):
    global _fake
    _fake = fn

# ============================================================
# 底层调用：发一次对话请求，要求返回一个 JSON 对象
# ============================================================
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
    req = urllib.request.Request(API_URL, data=json.dumps(body).encode("utf-8"),
                                 headers={"Authorization": f"Bearer {key}",
                                          "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return json.loads(data["choices"][0]["message"]["content"])

def _dispatch(role, payload, system, user):
    if _fake is not None:
        return _fake(role, payload)
    return call_model(role, system, user)

# ============================================================
# 可表达范围说明：写公式时必须让模型知道环境里有什么、没有什么
# ============================================================
EXPRESS_DOC = """可用日频字段：open、high、low、close、volume、mktcap（市值）、mktret（市场当日收益，对全体股票相同）。
可用算子：neg、abs、log、rank（截面排名）、rank_sector（行业内排名）、sector_mean（行业均值）、gt（大于取 1）、
delay（延迟 d 日）、delta（与 d 日前之差）、ts_mean、ts_sum、ts_std、ts_min、ts_max、ts_rank（时序排名）、
ts_corr（两序列 d 日相关），以及 + - * / 四则运算。窗口 d 为正整数。
不可表达的构造：逐点回归的斜率、残差、R 方本身（除非能用 ts_corr 与 ts_std 等价写出）；
逐日横截面回归；需要财务报表、分析师预期等未提供字段的量；变长窗口。
公式只能使用当日及以前的数据。"""

CATEGORIES = ["过度反应", "反应不足", "流动性", "波动", "规模", "价值", "情绪与注意力"]
SYMMETRIC_CATEGORIES = {"过度反应", "反应不足"}  # 词表中标为对称的类别，触发对称检验

# ============================================================
# 调用一：展开假设
# 输入：线索（方向、现象、收益来源）+ 经验条目 + 同类别已否决方向清单
# 输出：假设列表，每条为登记格式的字典
# ============================================================
EXPAND_SYSTEM = """你是一名量化研究员。你的任务是把一条研究线索展开成少量可检验的假设。
每条假设必须有明确的机制与收益来源，并给出可被数据证伪的条件预测。
只输出 JSON，不要输出其他文字。"""

def expand_hypotheses(clue, exp_entries, rejected_same_category):
    payload = {"clue": clue, "exp_entries": exp_entries,
               "rejected_same_category": rejected_same_category}
    exp_text = "\n".join(
        f"[经验{e['编号']}] 类别 {e['机制类别']}，状态 {e['状态']}：{e['讲评']['findings']} 避开：{e['讲评']['avoid']}"
        for e in exp_entries) or "（该类别暂无经验条目）"
    rej_text = "\n".join(
        f"- 方向「{r['方向']}」：{r['假设摘要']}（结局：{r['结局']}）"
        + (f"；对抗意见：{r['对抗摘要']}" if r.get("对抗摘要") else "")
        for r in rejected_same_category) or "（无）"
    user = f"""线索：
方向：{clue['direction']}
现象：{clue['phenomenon']}
可能的收益来源：{clue['source']}

机制类别只能从这七类中选：{', '.join(CATEGORIES)}。

相关经验（展开时必须引用，用 exp_refs 标注编号）：
{exp_text}

同类别已被否决或关键预测未兑现的方向（新假设须在 diff_from_rejected 中写明与它们的区别，并回应其中的对抗意见；没有区别的不要提出）：
{rej_text}

方向约定：假设与基准公式的方向须使因子值越大、预期收益越高；与收益呈反向关系的量，先取负再写。

可表达范围（计算方式与基准公式必须能在此范围内实现）：
{EXPRESS_DOC}

输出 JSON：{{"hypotheses": [每条假设一个对象]}}，每个对象字段：
direction（方向名，与线索一致）、category（机制类别）、hypothesis（一句话陈述）、
measure（计算方式的文字说明）、baseline_formula（用上述算子写出的基准公式，代表你声称要计算的量）、
mechanism（机制与收益来源）、
predictions（至少两条，每条 {{"dim": "市值组|持有期|行业", "a": "比较的一方", "b": "比较的另一方", "key": true/false}}，
含义为"a 组的 IC 高于 b 组"；市值组的 a、b 取自 小/中/大；持有期的 a、b 取自 1/5/10/20/60（天）；
行业的 a 为行业名、b 固定为 "整体"；恰有一条 key 为 true，即与机制直接对应的关键预测）、
falsify（否定条件）、exp_refs（引用的经验编号列表）、diff_from_rejected（与上述已否决方向的区别，无则空字符串）。
展开 1 至 3 条假设，宁缺毋滥。"""
    out = _dispatch("expand", payload, EXPAND_SYSTEM, user)
    return out.get("hypotheses", [])

# ============================================================
# 调用二：写公式
# 输入：一条已登记假设 + 上次失败原因（首次为空）
# 输出：{"formula": 表达式} 或 {"formula": null, "reason": 原因}
# ============================================================
FORMULA_SYSTEM = """你是一名量化工程师。你的任务是把一条假设的计算方式写成一条公式表达式。
公式只能使用给定的字段与算子。只输出 JSON，不要输出其他文字。"""

def write_formula(hyp, error=None):
    payload = {"hyp": hyp, "error": error}
    user = f"""假设的计算方式：{hyp['measure']}
机制：{hyp['mechanism']}
登记的基准公式（供理解要算的量，不要直接照抄，写出你自己的实现）：{hyp['baseline_formula']}
方向约定：公式须使因子值越大、预期收益越高；与收益呈反向关系的量先取负。

可表达范围：
{EXPRESS_DOC}
"""
    if error:
        user += f"\n上一次的公式未通过检查，原因：{error}。请修正公式本身，不要改变要计算的量。\n"
    user += """输出 JSON：{"formula": "表达式字符串"}；确实无法用给定算子表达时输出 {"formula": null, "reason": "原因"}。"""
    return _dispatch("formula", payload, FORMULA_SYSTEM, user)

# ============================================================
# 调用三：写讲评
# 输入：假设登记 + 判定数字 + 预测核对 + 对抗结果 + 结论
# 输出：讲评字典，数字走 numbers 字段（程序逐项与账本核对）
# ============================================================
REVIEW_SYSTEM = """你是一名量化研究复盘员。你的任务是为一条已判定假设写讲评。
讲评只能陈述给定数字支持的规律；涉及机制原因的推断写入 speculation 并明确其为推测。
numbers 字段必须原样抄录给定的判定数字，不得改动或估算。只输出 JSON，不要输出其他文字。"""

def write_review(hyp, metrics, pred_results, adv_results, verdict):
    payload = {"hyp": hyp, "metrics": metrics, "pred_results": pred_results,
               "adv_results": adv_results, "verdict": verdict}
    user = f"""假设：{hyp['hypothesis']}
计算方式：{hyp['measure']}
机制：{hyp['mechanism']}

判定数字（程序计算）：IC均值 {metrics['IC均值']}，ICIR {metrics['ICIR']}，
与经典因子最大相关 {metrics['与经典因子最大相关']}，覆盖率 {metrics['覆盖率']}，
分市值组IC {metrics['分市值组IC']}，各持有期IC {metrics['各持有期IC']}，分段IC {metrics['分段IC']}。
条件预测核对：{json.dumps(pred_results, ensure_ascii=False)}
对抗检验结果：{json.dumps(adv_results, ensure_ascii=False)}
结论：{verdict}

输出 JSON：
{{"measures": "该因子的计算量测度什么",
  "findings": "指标显示的规律，包括在哪些时段、哪类股票上成立或失效",
  "avoid": "后续研究应避开的方向",
  "borrow": "可借用的结论",
  "speculation": "机理性推测，无则空字符串",
  "numbers": {{"ic": 上面的IC均值, "icir": 上面的ICIR, "max_corr": 上面的与经典因子最大相关}}}}"""
    return _dispatch("review", payload, REVIEW_SYSTEM, user)

# ============================================================
# 调用四：生成侧对抗审查
# 输入：一条已登记假设 + 经典因子公式清单
# 输出：攻击记录。只攻击、只留痕：不作通过与否的结论，不给修改方案，不参与判定。
# 攻击记录随账本与经验回流，成为下一次展开必须回应的输入。
# ============================================================
ATTACK_REG_SYSTEM = """你是一名持怀疑态度的量化评审。你的任务是攻击一条刚登记的因子假设，找出它最可能站不住的地方。
你只负责攻击：不作通过与否的结论，不给修改方案，不预测它的回测数字。只输出 JSON，不要输出其他文字。"""

def attack_registration(hyp, classic_formulas):
    payload = {"hyp": hyp, "classic_formulas": classic_formulas}
    classics_text = "\n".join(f"{i + 1:02d}. {f}" for i, f in enumerate(classic_formulas))
    user = f"""待攻击的假设登记：
假设：{hyp['hypothesis']}
机制类别：{hyp['category']}
计算方式：{hyp['measure']}
基准公式：{hyp['baseline_formula']}
机制与收益来源：{hyp['mechanism']}
条件预测：{json.dumps(hyp['predictions'], ensure_ascii=False)}
否定条件：{hyp['falsify']}

经典因子公式清单（编号即账本中的经典编号）：
{classics_text}

攻击三件事：
1. 换皮：这条假设与清单中哪条经典因子最像？像在什么地方？它声称的区别是否真实成立？
2. 预测注水：条件预测里有没有写了等于没写的（按机制必然如此、无法被数据证伪）、或刻意绕开否定条件的？
3. 机制自洽：机制叙述与收益来源是否自洽？"赚谁的钱、对方为何持续付钱"是否说得通？

输出 JSON：
{{"最像的经典": "编号与一句相似点，或写 无",
  "换皮判断": "区别是否成立及理由",
  "预测问题": "注水或绕开之处，无则写 无",
  "机制问题": "不自洽之处，无则写 无"}}"""
    return _dispatch("attack_reg", payload, ATTACK_REG_SYSTEM, user)

# ============================================================
# 调用五：检验侧对抗审查
# 输入：假设登记 + 全部判定数字 + 预测核对 + 程序对抗结果 + 程序结论
# 输出：失效解释备忘录。只依据给定数字攻击，不引入新数字，不给改参数重跑的建议，
# 不推翻程序结论。备忘录存入经验库，供后续研究与下一次展开使用。
# ============================================================
ATTACK_RES_SYSTEM = """你是一名持怀疑态度的量化评审。你的任务是在程序判定之后攻击一条假设的结果，解释它最可能为何成立或失效，并指出程序检验覆盖不到的失效方式。
你只能依据给定的数字，不引入新数字；不给修改参数重跑的建议；不推翻程序给出的结论。只输出 JSON，不要输出其他文字。"""

def attack_results(hyp, metrics, pred_results, adv_results, verdict):
    payload = {"hyp": hyp, "metrics": metrics, "pred_results": pred_results,
               "adv_results": adv_results, "verdict": verdict}
    user = f"""假设：{hyp['hypothesis']}
计算方式：{hyp['measure']}
机制：{hyp['mechanism']}

判定数字（程序计算）：IC均值 {metrics['IC均值']}，ICIR {metrics['ICIR']}，
与经典因子最大相关 {metrics['与经典因子最大相关']}，覆盖率 {metrics['覆盖率']}，
分市值组IC {metrics['分市值组IC']}，各持有期IC {metrics['各持有期IC']}，
分行业IC {metrics['分行业IC']}，分段IC {metrics['分段IC']}。
条件预测核对：{json.dumps(pred_results, ensure_ascii=False)}
程序对抗检验结果：{json.dumps(adv_results, ensure_ascii=False)}
程序结论：{verdict}

输出 JSON：
{{"失效解释": "依据上述数字，这条假设最可能的死因（结论为通过时，写它最脆弱、最可能在样本外失效之处）",
  "未覆盖的失效方式": "程序已执行的检验（子时段反例、信号两端分组、预测核对）覆盖不到的失效方式，无则写 无",
  "备注": "其他值得后续研究注意的攻击点，无则空字符串"}}"""
    return _dispatch("attack_res", payload, ATTACK_RES_SYSTEM, user)
