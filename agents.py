# agents.py — 模型调用层
# 职责：八个模型调用——展开假设、文献筛选、文献优化假设、写公式、写讲评、生成侧对抗审查、检验侧对抗审查、提出线索。
# 只生成与判断，不计算数字，不写任何文件；对抗审查只留痕，不参与判定（判定归 run.py 按程序规则执行）。
# 数字一律由 calc.py 计算；本文件只把结构化输入拼成提示词、把模型输出解析成字典。
# 模型：DeepSeek（环境变量 DEEPSEEK_API_KEY）。测试时可用 set_fake 注入替身，跳过真实调用。

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
可用算子（括号内为参数个数）：neg(1)、abs(1)、log(1)、rank(1，截面排名)、rank_sector(1，行业内排名)、
sector_mean(1，行业均值)、gt(2，大于取 1)、delay(2，延迟 d 日)、delta(2，与 d 日前之差)、
ts_mean(2)、ts_sum(2)、ts_std(2)、ts_min(2)、ts_max(2)、ts_rank(2，时序排名)、ts_corr(3，两序列 d 日滚动相关)，
以及 + - * / 四则运算。时序算子的最后一个参数是窗口 d，为正整数。
不可表达的构造：任意窗口的回归斜率与残差本身（残差类量只能用预计算的 ivol20 与 resid_ret，窗口固定 20 日）；
逐日横截面回归；需要财务报表、分析师预期等未提供数据的量；变长窗口。
公式只能使用当日及以前的数据。"""

DATA_BOUNDARY = """数据边界（硬约束）：系统只有日频价量、市值、市场收益、行业归属与 ivol20、resid_ret 两个预计算字段。
不存在分析师覆盖人数、财务报表字段、涨跌停价格、新闻与文本数据，也没有这些数据的代理变量约定。
机制若依赖这类数据，不要提出；计算方式与基准公式中不得引用不存在的量，不得自创未定义符号（如 C_t）。"""

CATEGORIES = ["过度反应", "反应不足", "流动性", "波动", "规模", "价值", "情绪与注意力"]
SYMMETRIC_CATEGORIES = {"过度反应", "反应不足"}  # 词表中标为对称的类别，触发对称检验

# ============================================================
# 调用一：展开假设
# 输入：线索（方向、现象、收益来源）+ 经验条目 + 同类别已否决方向清单
#       + 方向第 2 次及以后尝试的结构化反馈包（上次回执与数据地形，run.py 组装）
# 输出：假设列表，每条为登记格式的字典；有反馈包时每条须带 feedback_response
# ============================================================
EXPAND_SYSTEM = """你是一名量化研究员。你的任务是把一条研究线索展开成少量可检验的假设。
每条假设必须有明确的机制与收益来源，并给出可被数据证伪的条件预测。
只输出 JSON，不要输出其他文字。"""

def expand_hypotheses(clue, exp_entries, rejected_same_category, sectors=None, feedback=None):
    payload = {"clue": clue, "exp_entries": exp_entries,
               "rejected_same_category": rejected_same_category,
               "feedback": feedback}
    exp_text = "\n".join(
        f"[经验{e['编号']}] 类别 {e['机制类别']}，状态 {e['状态']}：{e['讲评']['findings']} 避开：{e['讲评']['avoid']}"
        for e in exp_entries) or "（该类别暂无经验条目）"
    rej_text = "\n".join(
        f"- 方向「{r['方向']}」：{r['假设摘要']}（结局：{r['结局']}）"
        + (f"；对抗意见：{r['对抗摘要']}" if r.get("对抗摘要") else "")
        for r in rejected_same_category) or "（无）"
    fb_text = ""
    if feedback:
        lines = []
        last = feedback.get("上次尝试") or {}
        head = (f"上次尝试：假设「{last.get('假设', '')}」→ 结论 {last.get('结论', '')}，"
                f"失效层 {last.get('失效层', '')}")
        if last.get("无法表达原因"):
            head += f"，无法表达原因：{last['无法表达原因']}"
        lines.append(head)
        for p in feedback.get("预测核对") or []:
            lines.append(
                f"- 预测（{p['dim']}，{'关键' if p.get('key') else '一般'}）：{p['a']} 高于 {p['b']}"
                f"——实际 {p['a']} 组 IC {p.get('a值')} vs {p['b']} 组 IC {p.get('b值')}，"
                f"{'兑现' if p['兑现'] else '未兑现'}")
        memo = feedback.get("检验侧备忘录") or {}
        if memo.get("失效解释"):
            lines.append(f"检验侧失效备忘录：{memo['失效解释']}"
                         + (f"；未覆盖的失效方式：{memo['未覆盖的失效方式']}"
                            if memo.get("未覆盖的失效方式") else ""))
        ga = feedback.get("生成侧对抗") or {}
        ga_bits = [f"{k}：{ga[k]}" for k in ("换皮判断", "预测问题", "机制问题", "引用问题")
                   if ga.get(k) and ga[k] != "无"]
        if ga_bits:
            lines.append("生成侧对抗意见：" + "；".join(ga_bits))
        terr = feedback.get("数据地形") or []
        if terr:
            lines.append("数据地形（程序在训练段扫描所得、已过噪声标尺的条件规律，可作机制假设的入料）：")
            lines += [f"- {t}" for t in terr]
        fb_text = ("\n\n本方向上一次尝试的结构化反馈（本轮为该方向第 2 次及以后尝试）：\n"
                   + "\n".join(lines)
                   + "\n每条假设必须输出 feedback_response：逐条回应上次未兑现的预测"
                     "——本条假设改了什么、为什么；至少须点名一个未兑现预测的维度"
                     "（市值组 / 持有期 / 行业）。未写或未点名维度，登记会被程序拒登。")
    user = f"""线索：
方向：{clue['direction']}
现象：{clue['phenomenon']}
可能的收益来源：{clue['source']}

机制类别只能从这七类中选：{', '.join(CATEGORIES)}。

相关经验（展开时必须引用，用 exp_refs 标注编号）：
{exp_text}

同类别已被否决或关键预测未兑现的方向（新假设须在 diff_from_rejected 中写明与它们的区别，并回应其中的对抗意见；没有区别的不要提出）：
{rej_text}
{fb_text}

方向约定：假设与基准公式的方向须使因子值越大、预期收益越高；与收益呈反向关系的量，先取负再写。
基准公式须保留原始量纲与符号，不要套 rank 等截面变换（否则按符号分组的检验无法执行）。

可表达范围（计算方式与基准公式必须能在此范围内实现）：
{EXPRESS_DOC}

{DATA_BOUNDARY}

输出 JSON：{{"hypotheses": [每条假设一个对象]}}，每个对象字段：
direction（方向名，与线索一致）、category（机制类别）、hypothesis（一句话陈述）、
measure（计算方式的文字说明）、baseline_formula（用上述算子写出的基准公式，代表你声称要计算的量）、
mechanism（机制与收益来源）、
predictions（至少两条，每条 {{"dim": "市值组|持有期|行业", "a": "比较的一方", "b": "比较的另一方", "key": true/false}}，
含义为"a 组的 IC 高于 b 组"；市值组的 a、b 取自 小/中/大；持有期的 a、b 取自 1/5/10/20/60（天）；
行业的 a 只能取自下面的行业名清单、b 固定为 "整体"（a 写"整体"会被程序拒登）；恰有一条 key 为 true，即与机制直接对应的关键预测）、
行业名清单（行业预测的 a 只能取自）：{', '.join(sorted(sectors)) if sectors else '（未提供）'}
falsify（否定条件）、exp_refs（引用的经验编号列表）、diff_from_rejected（与上述已否决方向的区别，无则空字符串）、
feedback_response（给出上次尝试反馈时必填：逐条回应上次未兑现预测的修改与理由，至少点名一个未兑现维度；未给反馈时省略）、
search_queries（1 至 2 条英文检索式，用于为这条假设检索学术资料，须具体到机制与现象，如 "short-term return reversal liquidity provision"）。
展开 1 至 3 条假设，宁缺毋滥。"""
    out = _dispatch("expand", payload, EXPAND_SYSTEM, user)
    return out.get("hypotheses", [])

# ============================================================
# 调用二前置：文献筛选（读摘要挑全文）
# 输入：假设 + 检索到的学术资料（带编号与摘要）
# 输出：{"picks": [值得读全文的编号，至多 2 个], "reason": 逐篇取舍理由}
# 纪律：只能从有摘要的材料里挑；挑选只依据摘要与假设机制的相关性，不涉及任何回测数字。
# ============================================================
PICK_SYSTEM = """你是一名量化研究员。你的任务是读完检索材料的摘要，挑出值得读全文的少数几篇。
挑选标准：与假设的机制直接相关、摘要中报告了具体的构造或成立条件、能为优化登记提供依据。
只输出 JSON，不要输出其他文字。"""

def pick_readings(hyp, lit):
    payload = {"hyp": hyp, "lit": lit}
    lit_text = "\n".join(
        f"[{m['编号']}] {m['标题']}（{m.get('年份')}，{m.get('来源')}）：{m.get('摘要') or '（无摘要）'}"
        for m in lit)
    user = f"""假设：{hyp['hypothesis']}
机制：{hyp['mechanism']}

检索材料（带编号）：
{lit_text}

从中有摘要的材料里挑出最值得读全文的 1 至 2 篇；一篇都不值得读时 picks 为空。
输出 JSON：{{"picks": ["L1"], "reason": "逐篇说明为何选中、未选的为何淘汰"}}"""
    return _dispatch("pick", payload, PICK_SYSTEM, user)

# ============================================================
# 调用二：文献优化假设
# 输入：假设登记初稿 + 检索到的学术资料（带编号）
# 输出：优化后的登记五项（计算方式、基准公式、机制、条件预测、否定条件）
#       + lit_refs（实际用到的材料编号）+ changes（逐条说明改了什么、依据哪条材料）
# 纪律：此时尚无任何回测数字，优化只依据资料与机制推理；方向与类别不得更改；
#       材料与初稿冲突时以材料为准并说明；材料无关时可不改。
# ============================================================
REFINE_SYSTEM = """你是一名量化研究员。你的任务是依据检索到的学术资料，优化一条因子假设的登记内容。
优化只能依据给定资料与机制推理，不得虚构资料中没有的结论；资料与初稿冲突时以资料为准。
只输出 JSON，不要输出其他文字。"""

def refine_hypothesis(hyp, lit, sectors=None):
    payload = {"hyp": hyp, "lit": lit}

    def _lit_line(m):
        line = (f"[{m['编号']}] {m['标题']}（{m.get('年份')}，{m.get('来源')}）："
                f"{m.get('摘要') or '（无摘要，仅标题）'}")
        if m.get("全文节选"):
            line += f"\n全文节选（已深读）：{m['全文节选']}"
        return line

    lit_text = "\n".join(_lit_line(m) for m in lit)
    user = f"""假设登记初稿：
假设：{hyp['hypothesis']}
机制类别：{hyp['category']}（不得更改）
计算方式：{hyp['measure']}
基准公式：{hyp['baseline_formula']}
机制与收益来源：{hyp['mechanism']}
条件预测：{json.dumps(hyp['predictions'], ensure_ascii=False)}
否定条件：{hyp['falsify']}

方向约定与基准公式要求同展开时一致：因子值越大、预期收益越高；基准公式保留原始量纲与符号，不套 rank。
可表达范围：
{EXPRESS_DOC}

{DATA_BOUNDARY}

检索到的学术资料：
{lit_text}

依据资料优化登记五项：计算方式、基准公式、机制、条件预测、否定条件。
重点：资料报告的典型构造、成立条件与已知失效条件，应反映到计算方式与条件预测中；
条件预测的维度与取值规则同展开时一致（市值组 小/中/大；持有期 1/5/10/20/60；行业 a 为真实行业名、b 为"整体"）。
行业名清单（行业预测的 a 只能取自）：{', '.join(sorted(sectors)) if sectors else '（未提供）'}
资料与初稿无关或不足以支持修改时，返回初稿原文，changes 写"无修改"。

输出 JSON：
{{"measure": "优化后的计算方式", "baseline_formula": "优化后的基准公式",
  "mechanism": "优化后的机制与收益来源",
  "predictions": [同初稿格式的条件预测，至少两条、恰一条 key 为 true],
  "falsify": "优化后的否定条件",
  "lit_refs": ["实际用到的材料编号，如 L1"],
  "changes": "逐条说明改了什么、依据哪条材料；无修改时写 无修改"}}"""
    return _dispatch("refine", payload, REFINE_SYSTEM, user)

# ============================================================
# 调用三：写公式
# 输入：一条已登记假设 + 上次失败原因（首次为空）
# 输出：{"formula": 表达式} 或 {"formula": null, "reason": 原因}
# ============================================================
FORMULA_SYSTEM = """你是一名量化工程师。你的任务是把一条假设的计算方式写成一条公式表达式。
公式只能使用给定的字段与算子。只输出 JSON，不要输出其他文字。"""

def write_formula(hyp, error=None, cap=None, guidance=None):
    payload = {"hyp": hyp, "error": error, "guidance": guidance}
    user = f"""假设的计算方式：{hyp['measure']}
机制：{hyp['mechanism']}
登记的基准公式（供理解要算的量，不要直接照抄，写出你自己的实现）：{hyp['baseline_formula']}
方向约定：公式须使因子值越大、预期收益越高；与收益呈反向关系的量先取负。

可表达范围：
{EXPRESS_DOC}
"""
    if cap:
        user += f"""
复杂度上限 {cap}：复杂度 = 公式中算子调用次数 + 字段引用次数（四则运算、常数与括号不计）。
下笔前先按此口径自数一遍；预计超限时优先简化——去掉一层变换、合并相近窗口、用预计算字段代替多层构造——不要改变要计算的量。
"""
    if error:
        user += f"\n上一次的公式未通过检查，原因：{error}。请修正公式本身，不要改变要计算的量。\n"
    if guidance:
        user += (f"\n本轮为改因子修订：登记假设不变，按以下修改要求重写公式：{guidance}。"
                 "公式允许偏离登记的基准公式，但必须实现计算方式所指的量，并遵守方向约定。\n")
    user += """输出 JSON：{"formula": "表达式字符串"}；确实无法用给定算子表达时输出 {"formula": null, "reason": "原因"}。"""
    return _dispatch("formula", payload, FORMULA_SYSTEM, user)

# ============================================================
# 调用四：写讲评
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
# 调用五：生成侧对抗审查
# 输入：一条已登记假设 + 经典因子公式清单
# 输出：攻击记录。只攻击、只留痕：不作通过与否的结论，不给修改方案，不参与判定。
# 攻击记录随账本与经验回流，成为下一次展开必须回应的输入。
# ============================================================
ATTACK_REG_SYSTEM = """你是一名持怀疑态度的量化评审。你的任务是攻击一条刚登记的因子假设，找出它最可能站不住的地方。
你只负责攻击：不作通过与否的结论，不给修改方案，不预测它的回测数字。只输出 JSON，不要输出其他文字。"""

def attack_registration(hyp, classic_formulas, lit=None):
    payload = {"hyp": hyp, "classic_formulas": classic_formulas, "lit": lit}
    classics_text = "\n".join(f"{i + 1:02d}. {f}" for i, f in enumerate(classic_formulas))
    lit_text = "\n".join(
        f"[{m['编号']}] {m['标题']}（{m.get('年份')}，{m.get('来源')}）：{m.get('摘要') or '（无摘要，仅标题）'}"
        for m in (lit or [])) or "（本次无检索材料）"
    user = f"""待攻击的假设登记：
假设：{hyp['hypothesis']}
机制类别：{hyp['category']}
计算方式：{hyp['measure']}
基准公式：{hyp['baseline_formula']}
机制与收益来源：{hyp['mechanism']}
条件预测：{json.dumps(hyp['predictions'], ensure_ascii=False)}
否定条件：{hyp['falsify']}
文献引用：{hyp.get('lit_refs') or '（未引用）'}

经典因子公式清单（编号即账本中的经典编号）：
{classics_text}

检索到的学术资料：
{lit_text}

攻击四件事：
1. 换皮：这条假设与清单中哪条经典因子最像？像在什么地方？它声称的区别是否真实成立？
2. 预测注水：条件预测里有没有写了等于没写的（按机制必然如此、无法被数据证伪）、或刻意绕开否定条件的？
3. 机制自洽：机制叙述与收益来源是否自洽？"赚谁的钱、对方为何持续付钱"是否说得通？
4. 引用核对：声称的机制与所引用的资料对不对得上？引用是否只是贴标签（材料与机制无关、或材料并不支持该机制）？未引用资料时写 无。

输出 JSON：
{{"最像的经典": "只填编号，如 C09；没有像的写 无",
  "相似点": "与该条经典像在什么地方",
  "换皮判断": "区别是否成立及理由",
  "预测问题": "注水或绕开之处，无则写 无",
  "机制问题": "不自洽之处，无则写 无",
  "引用问题": "引用与机制对不上或贴标签之处，无则写 无"}}"""
    return _dispatch("attack_reg", payload, ATTACK_REG_SYSTEM, user)

# ============================================================
# 调用六：检验侧对抗审查
# 输入：假设登记 + 全部判定数字 + 预测核对 + 程序对抗结果 + 程序结论
# 输出：失效解释备忘录。只依据给定数字攻击，不引入新数字，不给改参数重跑的建议，
# 不推翻程序结论。备忘录存入经验库，供后续研究与下一次展开使用。
# ============================================================
ATTACK_RES_SYSTEM = """你是一名持怀疑态度的量化评审。你的任务是在程序判定之后攻击一条假设的结果，解释它最可能为何成立或失效，并指出程序检验覆盖不到的失效方式。
你只能依据给定的数字，不引入新数字；不给修改参数重跑的建议；不推翻程序给出的结论。只输出 JSON，不要输出其他文字。"""

def attack_results(hyp, metrics, pred_results, adv_results, verdict, gen_attack=None):
    payload = {"hyp": hyp, "metrics": metrics, "pred_results": pred_results,
               "adv_results": adv_results, "verdict": verdict, "gen_attack": gen_attack}
    claimed = (gen_attack or {}).get("最像的经典", "（生成侧对抗缺失）")
    user = f"""假设：{hyp['hypothesis']}
计算方式：{hyp['measure']}
机制：{hyp['mechanism']}

判定数字（程序计算）：IC均值 {metrics['IC均值']}，ICIR {metrics['ICIR']}，
与经典因子最大相关 {metrics['与经典因子最大相关']}（最大相关经典：{metrics.get('最大相关经典')}），覆盖率 {metrics['覆盖率']}，
分市值组IC {metrics['分市值组IC']}，各持有期IC {metrics['各持有期IC']}，
分行业IC {metrics['分行业IC']}，分段IC {metrics['分段IC']}。
条件预测核对：{json.dumps(pred_results, ensure_ascii=False)}
程序对抗检验结果：{json.dumps(adv_results, ensure_ascii=False)}
程序结论：{verdict}

换皮交叉核对：生成侧对抗在回测前声称这条假设最像的经典是「{claimed}」；
程序实测的最大相关经典是 {metrics.get('最大相关经典')}，相关 {metrics['与经典因子最大相关']}。
两者是否一致、声称的区别是否被实测支持，必须在备注中点明；声称不像但实测相关高、或点名的对象与实测不符的，直接指出。

输出 JSON：
{{"失效解释": "依据上述数字，这条假设最可能的死因（结论为通过时，写它最脆弱、最可能在样本外失效之处）",
  "未覆盖的失效方式": "程序已执行的检验（子时段反例、信号两端分组、预测核对）覆盖不到的失效方式，无则写 无",
  "备注": "换皮交叉核对的结论，以及其他值得后续研究注意的攻击点"}}"""
    return _dispatch("attack_res", payload, ATTACK_RES_SYSTEM, user)

# ============================================================
# 调用七：提出线索
# 输入：已有方向清单 + 全部经验条目 + 全部已否决摘要
# 输出：新线索列表。线索由模型自提，程序做词表与去重校验后才登记（见 run.py）。
# ============================================================
PROPOSE_SYSTEM = """你是一名量化研究负责人。你的任务是基于已有研究记录提出新的研究线索，开辟值得检验的方向。
线索要具体到现象与可能的收益来源；不得与已有方向重复或同义改名；不得重提已封存方向的同一机制。
只输出 JSON，不要输出其他文字。"""

def propose_clues(existing_directions, exp_entries, rejected):
    payload = {"existing_directions": existing_directions,
               "exp_entries": exp_entries, "rejected": rejected}
    exp_text = "\n".join(
        f"[经验{e['编号']}] 类别 {e['机制类别']}，状态 {e['状态']}：{e['讲评']['findings']}"
        f" 借用：{e['讲评']['borrow']}"
        + (f" 对抗备忘录：{e['对抗备忘录']['失效解释']}；未覆盖：{e['对抗备忘录']['未覆盖的失效方式']}"
           if e.get("对抗备忘录") else "")
        for e in exp_entries) or "（暂无经验条目）"
    rej_text = "\n".join(
        f"- 方向「{r['方向']}」：{r['假设摘要']}（结局：{r['结局']}）"
        + (f"；对抗意见：{r['对抗摘要']}" if r.get("对抗摘要") else "")
        for r in rejected) or "（无）"
    user = f"""已有方向（不得重复，不得同义改名重提）：
{', '.join(existing_directions) or '（无）'}

机制类别只能从这七类中选：{', '.join(CATEGORIES)}。
优先考虑：尚未有方向覆盖的机制类别；经验中指出值得借用的结论；对抗备忘录中"未覆盖的失效方式"提示的新角度；
已否决方向的同一机制不得原样重提，换角度须在 phenomenon 中写明新角度。

已有经验：
{exp_text}

已否决或关键预测未兑现的方向：
{rej_text}

{DATA_BOUNDARY}
线索优先落在价量与预计算字段可表达的机制上。

输出 JSON：{{"clues": [每条线索一个对象]}}，每个对象字段：
direction（简短的方向名）、phenomenon（观察到的现象）、source（可能的收益来源）、category（机制类别）。
提出 1 至 3 条，宁缺毋滥；确实没有新角度时输出空列表。"""
    out = _dispatch("propose", payload, PROPOSE_SYSTEM, user)
    return out.get("clues", [])

# ============================================================
# 调用八：裁决下一步修订（新假设循环专用）
# 输入：本轮证据（失效层、逐条预测核对与实际分组数字、回测指标、
#       双侧对抗意见、公式与一致性/复杂度信息）
# 输出：三选一——改因子 / 改假设 / 终止，附一句话理由与一条具体修改要求。
# 裁决只决定改什么，无判定权；通过与否由程序判定门决定。
# ============================================================
JUDGE_SYSTEM = """你是一名量化研究负责人。一条假设刚完成一轮回测与检验且未通过，你要依据本轮证据裁决下一步怎么走。
三选一：改因子（假设本身成立，问题在公式构造：下一轮沿用同一登记假设、按修改要求重写公式重测）；
改假设（假设本身有问题：下一轮带反馈包重新展开、提出完整新假设）；
终止（本假设到此为止，无值得再试的修订）。
修改要求只许给一类、必须具体（改因子时指明公式怎么改；改假设时指明新假设应换什么角度；终止时可为空）。
你没有判定权，不得推翻程序结论，不得引入证据之外的数字。只输出 JSON，不要输出其他文字。"""

def judge_revision(evidence):
    payload = {"evidence": evidence}
    m = evidence.get("判定数字") or {}
    user = f"""本轮证据：
假设：{evidence.get('假设')}
公式：{evidence.get('公式')}（一致性相关 {evidence.get('一致性相关')}，复杂度 {evidence.get('复杂度')}）
程序结论：{evidence.get('结论')}；失效层：{evidence.get('失效层')}
判定数字：{json.dumps(m, ensure_ascii=False) if m else '（无，公式未通过程序检查或无法表达）'}
逐条预测核对：{json.dumps(evidence.get('预测核对'), ensure_ascii=False)}
生成侧对抗意见：{json.dumps(evidence.get('生成侧对抗'), ensure_ascii=False)}
检验侧对抗意见：{json.dumps(evidence.get('检验侧对抗'), ensure_ascii=False)}
无法表达原因：{evidence.get('无法表达原因')}

输出 JSON：
{{"决定": "改因子 | 改假设 | 终止（三选一）",
  "理由": "一句话，依据上述证据",
  "修改要求": "一条具体要求，只许一类；终止时可为空字符串"}}"""
    return _dispatch("judge", payload, JUDGE_SYSTEM, user)
