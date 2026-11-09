# hypothesis_agent.py — 假设 Agent（想）
# 职责：依据数据说明与已试假设清单，成批提出假设。
# 模型只填量、经济逻辑、机制类别三项；假设句由程序按固定句式拼装。
# 本文件不计算数字；去重由程序按拼装后的假设句文本完全相同执行。

import html as html_lib
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

# ============================================================
# 材料：数据说明与机制类别（与 spec 一致，是给模型的输入）
# ============================================================
DATA_DOC = """数据为日频行情，覆盖 2000-2016 年美股（含已退市股票）。
可用字段：open、high、low、close（均为复权价）、volume（成交股数）、mktcap（总市值，千美元）、mktret（当日市场收益率，全体股票相同）。
量可以是全市场口径，也可以是行业内相对口径或行业整体口径（每只股票有 GICS 行业分类，如相对行业平均的强弱、行业整体的趋势），还可以相对市场基准（如与市场收益的相关、相对市场的强弱）；一段时间内的频率、占比类量同样可表达（如上涨天数占比）。
假设必须能用上述字段表达，并能通过历史数据检验。"""

MECHANISMS = ["反转", "动量", "量价", "波动率", "流动性", "日内隔夜", "规模", "其他"]

# 已占满的经典机制：全部条目源于已发表文献（公式与出处见 classic-factor-inspiration-2026-11-09.md）
# 用途是划界不是引路：只给机制句作地图，标出已有成熟因子的方向，要求在其之外构造。
# 不给公式——给公式会被模型照抄（2026-11-09 验收跑实测：8/14 条与经典相关 ≥ 0.86）。
# 公式在程序一侧（calc.CLASSIC_FORMULAS），仅作相关性参照，假设 Agent 不接触。
MECHANISM_NOTES = """短期过度反应后均值回复
多年期过度反应在随后数年反转
过去的赢家在随后数月继续跑赢（信息扩散慢、反应不足）
接近历史高点的股票被锚定低估、利好反应不足
涨幅由许多小步累积而成时反应不足、趋势更持久；由少数大跳构成时反应迅速
异常放量是注意力冲击，提高股票可见性与后续需求
低换手赢家的动量寿命更长，高换手赢家反转更快
高波动股票被彩票偏好与套利限制压价
出现过极端单日大涨的股票被彩票偏好高估
受杠杆约束的资金抢购高 Beta，使高 Beta 被高估、低 Beta 被低估
单位成交额的价格冲击越大、流动性越差，预期收益越高
换手低的股票流动性差且被忽视，预期收益更高
隔夜分量携带持续的信息流；隔夜与日内是两类投资者的拉锯，各自时段内延续、跨时段反转
日内涨幅多由日内追价构成，对后续收益形成反向压力
小市值股票被忽视且流动性差，平均收益更高
个股收益在相同日历月份跨年重复出现
行业层面的信息扩散比个股更慢，行业整体的趋势会延续"""

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
        "temperature": 0.9,
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

def _extract_json_array(text):
    start = text.find("[")
    end = text.rfind("]")
    if start < 0 or end <= start:
        raise ValueError("输出中找不到 JSON 数组")
    return json.loads(text[start:end + 1])

# ============================================================
# 检索：假设提出之后，程序按每条入选想法定向检索学术研究，
# 取论文标题与摘要供该条的打磨使用。模型不联网，检索一律由程序执行。
# 数据源依次尝试 OpenAlex、Semantic Scholar、arXiv（均免 key）；
# 某源失败或无结果则换下一源，全无结果则返回空，不阻断流程。
# 通用网页搜索（Bing）实测只返回门户首页，不作数据源。
# ============================================================
# 检索结果须含金融词才收（程序侧粗筛，滤掉字面误匹配）
_FIN_WORDS = ("stock", "equity", "return", "market", "trading", "investor", "portfolio", "share", "volatility")

def _get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return json.loads(urllib.request.urlopen(req, timeout=25).read().decode("utf-8"))

def _from_openalex(query, n):
    url = "https://api.openalex.org/works?" + urllib.parse.urlencode({"search": query, "per-page": n})
    out = []
    for w in _get_json(url).get("results", []):
        venue = ((w.get("primary_location") or {}).get("source") or {}).get("display_name") or ""
        out.append((w.get("title") or "", f"{venue} {w.get('publication_year') or ''}".strip()))
    return out

def _from_s2(query, n):
    url = "https://api.semanticscholar.org/graph/v1/paper/search?" + urllib.parse.urlencode(
        {"query": query, "limit": n, "fields": "title,abstract,year"})
    out = []
    for p in _get_json(url).get("data", []):
        out.append((p.get("title") or "", (p.get("abstract") or "")[:180]))
    return out

def _from_arxiv(query, n):
    url = ("http://export.arxiv.org/api/query?search_query=" + urllib.parse.quote(query)
           + f"&start=0&max_results={n}&sortBy=relevance")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    xml = urllib.request.urlopen(req, timeout=25).read().decode("utf-8", "ignore")
    out = []
    for entry in re.findall(r"<entry>(.*?)</entry>", xml, re.S):
        t = re.search(r"<title>(.*?)</title>", entry, re.S)
        s = re.search(r"<summary>(.*?)</summary>", entry, re.S)
        if t:
            clean = lambda x: html_lib.unescape(re.sub(r"\s+", " ", x)).strip()
            out.append((clean(t.group(1)), clean(s.group(1))[:180] if s else ""))
    return out

def _arxiv_query(english_query):
    words = [w for w in re.findall(r"[A-Za-z]+", english_query.lower())
             if w not in ("the", "of", "and", "in", "on", "a", "an", "to", "for", "with", "by")][:4]
    return " AND ".join(f"all:{w}" for w in words) or "all:stock"

def search_for(query, n=2):
    """按一条想法定向检索：依次问三个学术源，取前 n 条（标题 + 摘要或出处）。"""
    notes = []
    for fetch, arg in ((_from_openalex, query), (_from_s2, query), (_from_arxiv, _arxiv_query(query))):
        try:
            got = fetch(arg, n)
        except Exception:
            got = []
        for title, extra in got:
            if not title or not any(w in (title + " " + extra).lower() for w in _FIN_WORDS):
                continue
            notes.append(title if not extra else f"{title} — {extra}")
        if notes:
            break
    return notes

# ============================================================
# 提出：一批假设，模型填量、经济逻辑、机制类别，程序拼装假设句
# 漏斗顺序：出题（两倍候选，不预喂论文）→ 审核砍半 → 按条定向检索 → 逐条打磨 → 定稿
# ============================================================
SYSTEM = """你是一名因子研究员，任务是成批提出可用历史数据检验的因子假设。
只输出一个 JSON 数组，不要任何其他文字。数组每条含三项：
{"quantity": "量", "logic": "经济逻辑", "mechanism": "机制类别"}
mechanism 只能取给定清单中的一个。
quantity 是已定向的名词短语，带回望窗口（如“过去 20 日累计收益”）：它必须让“该量越大的股票，未来收益越高”成立；方向写进量本身，如反转类写“过去 20 日累计收益的相反数”。quantity 只写量本身，不写未来期限、分组或检验方式——那些由程序统一决定。"""

def _ask_items(messages, format_retries=2):
    """向模型请求一个 JSON 数组；格式不合要求时在同一对话里纠正重试。
    返回 (原始条目列表, 扩展后的对话, 模型最后的原文)。"""
    last_err = None
    for _ in range(format_retries + 1):
        text = call_model(messages)
        try:
            return _extract_json_array(text), messages, text
        except (ValueError, json.JSONDecodeError) as e:
            last_err = e
            messages = messages + [
                {"role": "assistant", "content": text},
                {"role": "user", "content": f"上次输出不是合法的 JSON 数组（{e}）。请只输出一个 JSON 数组，不要任何其他文字。"},
            ]
    raise RuntimeError(f"模型输出格式重试达上限：{last_err}")

def _validate(items, seen):
    """程序侧校验：三项非空、机制类别合法、与已试清单及本批不重复（按拼装句比对）。"""
    out = []
    for it in items:
        if not isinstance(it, dict):
            continue
        qty, logic, mech = it.get("quantity"), it.get("logic"), it.get("mechanism")
        if not (isinstance(qty, str) and qty.strip()):
            continue
        if not (isinstance(logic, str) and logic.strip()):
            continue
        if mech not in MECHANISMS:
            continue
        hyp = f"{qty.strip()}越大的股票，未来收益越高"
        if hyp in seen:
            continue
        seen.add(hyp)
        out.append({"hypothesis": hyp, "quantity": qty.strip(), "logic": logic, "mechanism": mech})
    return out

# ============================================================
# 审核：独立调用，只挑毛病与取舍，不提出新假设
# 与出题分开调用、角色相反，避免自己肯定自己；每条入选者附一个最主要的问题
# 与一个英文检索查询，供程序按该条定向检索
# ============================================================
REVIEW_SYSTEM = """你是一名审核员，负责审查一批候选因子假设。你不提出新假设，只做三件事：
1. 从候选中挑出值得继续的若干条，标准：与已试清单中已淘汰的死法距离远、机制类别分散、经济逻辑站得住、不是经典机制的标准构造换皮。
2. 给每条入选者指出一个最主要的问题：一句话，具体，不说空话。
3. 给每条入选者写一个英文检索查询，用于查这条想法的相关学术证据，短语式，如 "intraday momentum reversal stock evidence"。
只输出一个 JSON 数组，不要任何其他文字。每条含三项：
{"index": 候选序号, "problem": "最主要的问题", "query": "英文检索查询"}
按你的取舍从优到劣排序。"""

def _review(candidates, tried_text, batch):
    """返回 [{'index': 候选下标+1, 'problem': str, 'query': str}]；失败返回空列表（上层走兜底）。"""
    cand_text = "\n".join(
        f"{i + 1}. [{c['mechanism']}] {c['quantity']}（{c['logic']}）"
        for i, c in enumerate(candidates))
    user = f"""候选共 {len(candidates)} 条：
{cand_text}

已试假设清单（括号内为每条的结局；与这些相同或死法相同的不选）：
{tried_text}

已占满的经典机制（与这些机制的标准构造相近的不选）：
{MECHANISM_NOTES}

请挑出 {batch} 条。"""
    messages = [{"role": "system", "content": REVIEW_SYSTEM}, {"role": "user", "content": user}]
    try:
        items, _, _ = _ask_items(messages)
    except RuntimeError:
        return []
    picked = []
    for it in items:
        if not isinstance(it, dict):
            continue
        idx = it.get("index")
        if not isinstance(idx, int) or not (1 <= idx <= len(candidates)):
            continue
        if any(p["index"] == idx for p in picked):
            continue
        picked.append({"index": idx, "problem": str(it.get("problem", "") or ""),
                       "query": str(it.get("query", "") or "")})
        if len(picked) == batch:
            break
    return picked

# ============================================================
# 打磨：逐条进行；输入候选、审核员的问题、按该条检索到的学术摘录，
# 输出打磨后的一条（可微调、可改量、必要时改向）；失败则保留候选原样
# ============================================================
REFINE_SYSTEM = """你是一名因子研究员，负责把一条候选假设打磨成正式假设。
只输出一个 JSON 数组，数组只有一条，格式与提假设时相同：
{"quantity": "量", "logic": "经济逻辑", "mechanism": "机制类别"}
mechanism 只能取给定清单中的一个；quantity 的规则与提假设时相同（已定向、带回望窗口、方向写进量本身）。"""

def _refine(cand, problem, notes):
    """返回打磨后的原始条目 dict；失败返回 None。"""
    notes_text = "\n".join(f"- {n}" for n in notes) if notes else "（无）"
    user = f"""候选假设：量＝{cand['quantity']}；经济逻辑＝{cand['logic']}；机制类别＝{cand['mechanism']}

审核员指出的问题：{problem or '（无）'}

与这条想法相关的学术摘录（程序按该想法定向检索所得）：
{notes_text}

机制类别清单：{'、'.join(MECHANISMS)}

请打磨这条假设：针对审核员的问题修正；摘录若给出更明确的机制、方向或构造线索，据此加强；若摘录显示这个方向已有成熟研究且构造雷同，换参照对象或组合方式避开。可以微调，也可以改量本身，但机制类别须与改后的量一致。"""
    messages = [{"role": "system", "content": REFINE_SYSTEM}, {"role": "user", "content": user}]
    try:
        items, _, _ = _ask_items(messages)
    except RuntimeError:
        return None
    for it in items:
        if isinstance(it, dict) and it.get("quantity"):
            return it
    return None

def propose(tried, batch=8):
    """tried 为已试假设列表（条目带结局标注）。返回假设字典列表（已去重、已校验）。
    漏斗顺序：出题（batch*2 条候选，不预喂论文）→ 审核（独立调用砍到 batch 条，
    每条附问题与检索查询；审核失败则按原顺序取前 batch 条）→ 程序按条定向检索 →
    逐条打磨（回应问题与摘录；失败保留原样）→ 程序校验去重定稿。
    候选不超过 batch 时跳过审核与打磨，直接返回。"""
    tried_text = "\n".join(f"- {t}" for t in tried) if tried else "（无）"
    user = f"""{DATA_DOC}

机制类别清单：{'、'.join(MECHANISMS)}

已占满的经典机制（只有机制，没有公式；这张地图只用来划界——不要提与这些机制的标准构造相近的量，去地图之外构造：换信息来源、换参照对象、换组合方式）：
{MECHANISM_NOTES}

已试假设清单（括号内为每条的结局；不得重复提出，也不要重蹈已淘汰的死法）：
{tried_text}

请先提出 {batch * 2} 条候选假设，彼此尽量不同。"""
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]
    items, _, _ = _ask_items(messages)
    seen = {t.split(" 〔")[0] for t in tried}  # tried 条目带结局标注，去重只比对标注前的假设句
    candidates = _validate(items, set(seen))
    if len(candidates) <= batch:
        return candidates
    picked = _review(candidates, tried_text, batch)
    if not picked:
        picked = [{"index": i + 1, "problem": "", "query": ""} for i in range(batch)]
    out = []
    for p in picked:
        cand = candidates[p["index"] - 1]
        item = {"quantity": cand["quantity"], "logic": cand["logic"], "mechanism": cand["mechanism"]}
        if p["problem"] or p["query"]:
            notes = search_for(p["query"]) if p["query"] else []
            refined = _refine(cand, p["problem"], notes)
            if refined is not None:
                item = refined
        out.extend(_validate([item], seen))
    return out

# ============================================================
# 自检（块三验收）：直接运行本文件时执行
# ============================================================
if __name__ == "__main__":
    try:
        batch = propose(["过去 5 日跌幅越大的股票，未来收益越高"], batch=8)
        print(f"提出 {len(batch)} 条：")
        for b in batch:
            print("-", b["mechanism"], "|", b["hypothesis"])
    except RuntimeError as e:
        print("无法执行真实模型验收：", e)
