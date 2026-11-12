# search.py — 文献检索
# 职责：按英文检索式查学术资料，返回材料列表（标题、年份、来源、摘要）。
# 来源按序尝试：Semantic Scholar（有摘要）→ OpenAlex（有摘要）→ Crossref（仅标题级）。
# 来源遇 429 限流时等待后重试一次；每源的成败与错误记入 LAST_REPORT，供调度程序写入轨迹，
# 不再静默吞掉。全部失败返回空列表，不中断主流程。
# 只用标准库。结果按检索式缓存到 lit_cache.json，同一检索式不重复请求。

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
CACHE_PATH = os.path.join(BASE, "lit_cache.json")
TIMEOUT = 20

def _get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "factor-loop/1.0 (research)"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))

def _s2(query, limit):
    q = urllib.parse.quote(query)
    url = (f"https://api.semanticscholar.org/graph/v1/paper/search?query={q}"
           f"&fields=title,abstract,year&limit={limit}")
    data = _get_json(url)
    out = []
    for p in data.get("data") or []:
        if p.get("title"):
            out.append({"标题": p["title"], "年份": p.get("year"),
                        "来源": "Semantic Scholar", "摘要": (p.get("abstract") or "")[:800] or None})
    return out

def _openalex(query, limit):
    q = urllib.parse.quote(query)
    url = f"https://api.openalex.org/works?search={q}&per-page={limit}"
    data = _get_json(url)
    out = []
    for w in data.get("results") or []:
        abstract = None
        inv = w.get("abstract_inverted_index")
        if inv:
            words = sorted(((pos, word) for word, poses in inv.items() for pos in poses))
            abstract = " ".join(word for _, word in words)[:800]
        if w.get("title"):
            out.append({"标题": w["title"], "年份": w.get("publication_year"),
                        "来源": "OpenAlex", "摘要": abstract})
    return out

def _crossref(query, limit):
    q = urllib.parse.quote(query)
    # 不带 select 参数：字段清单写错一个（如 year）Crossref 会整单拒绝（400），不过滤最稳。
    url = f"https://api.crossref.org/works?query={q}&rows={limit}"
    data = _get_json(url)
    out = []
    for it in (data.get("message") or {}).get("items") or []:
        title = (it.get("title") or [""])[0]
        if not title:
            continue
        year = None
        parts = ((it.get("published") or {}).get("date-parts") or [[None]])
        if parts and parts[0]:
            year = parts[0][0]
        out.append({"标题": title, "年份": year, "来源": "Crossref", "摘要": None})
    return out

SOURCES = (_s2, _openalex, _crossref)
SOURCE_NAMES = {"_s2": "Semantic Scholar", "_openalex": "OpenAlex", "_crossref": "Crossref"}
LAST_REPORT = []   # 最近一次 search() 的逐源结果（成功条数或失败错误），供轨迹记录

def last_report():
    return [dict(x) for x in LAST_REPORT]

def _attempt(fn, query, limit):
    """调用一个来源；遇 429 限流等待 3 秒重试一次。返回 (结果列表, 报告项)。"""
    name = SOURCE_NAMES.get(fn.__name__, fn.__name__)
    try:
        r = fn(query, limit)
        return r, {"来源": name, "结果": f"返回 {len(r)} 条"}
    except Exception as e:
        if not (isinstance(e, urllib.error.HTTPError) and e.code == 429):
            return [], {"来源": name, "结果": "失败",
                        "错误": f"{type(e).__name__}: {e}"[:120]}
    time.sleep(3)
    try:
        r = fn(query, limit)
        return r, {"来源": name, "结果": f"429 后重试成功，返回 {len(r)} 条"}
    except Exception as e:
        return [], {"来源": name, "结果": "失败",
                    "错误": f"429 重试后仍失败：{type(e).__name__}: {e}"[:120]}

def _load_cache():
    if os.path.exists(CACHE_PATH):
        try:
            with open(CACHE_PATH, encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            return {}
    return {}

def search(query, limit=5):
    """按检索式查资料，返回 [{标题, 年份, 来源, 摘要}]；摘要为 None 表示仅有标题级材料。"""
    global LAST_REPORT
    LAST_REPORT = []
    cache = _load_cache()
    if query in cache:
        LAST_REPORT = [{"来源": "缓存", "结果": f"返回 {len(cache[query][:limit])} 条"}]
        return cache[query][:limit]
    results = []
    for fn in SOURCES:
        results, item = _attempt(fn, query, limit)
        LAST_REPORT.append(item)
        if results:
            break
        time.sleep(1)
    if results:  # 空结果不缓存：限流等暂时失败不应把该检索式永久封死
        cache[query] = results
        try:
            with open(CACHE_PATH, "w", encoding="utf-8") as fh:
                json.dump(cache, fh, ensure_ascii=False)
        except Exception:
            pass
    return results[:limit]
