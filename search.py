# search.py — 文献检索
# 职责：按英文检索式查学术资料，返回材料列表（标题、年份、来源、摘要、全文链接）。
# 来源按序尝试：Semantic Scholar（有摘要）→ OpenAlex（有摘要）→ arXiv（有摘要）→ Crossref（仅标题级）。
# 来源遇 429 限流时等待后重试一次；每源的成败与错误记入 LAST_REPORT，供调度程序写入轨迹，
# 不再静默吞掉。全部失败返回空列表，不中断主流程。
# 另提供 fetch_fulltext：抓取开放获取的 HTML 全文并提取正文，供筛选后深读；抓不到返回空。
# 只用标准库。结果按检索式缓存到 lit_cache.json，同一检索式不重复请求。

import html.parser
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

BASE = os.path.dirname(os.path.abspath(__file__))
CACHE_PATH = os.path.join(BASE, "lit_cache.json")
TIMEOUT = 20

def _get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "factor-loop/1.0 (research)"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))

def _get_text(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": "factor-loop/1.0 (research)"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")

def _s2(query, limit):
    q = urllib.parse.quote(query)
    url = (f"https://api.semanticscholar.org/graph/v1/paper/search?query={q}"
           f"&fields=title,abstract,year,openAccessPdf&limit={limit}")
    data = _get_json(url)
    out = []
    for p in data.get("data") or []:
        if p.get("title"):
            oa = (p.get("openAccessPdf") or {}).get("url")
            out.append({"标题": p["title"], "年份": p.get("year"),
                        "来源": "Semantic Scholar", "摘要": (p.get("abstract") or "")[:800] or None,
                        "全文链接": oa})
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
        oa = ((w.get("best_oa_location") or {}).get("pdf_url")
              or (w.get("primary_location") or {}).get("pdf_url"))
        if w.get("title"):
            out.append({"标题": w["title"], "年份": w.get("publication_year"),
                        "来源": "OpenAlex", "摘要": abstract, "全文链接": oa})
    return out

def _arxiv(query, limit):
    # arXiv 的 all:"整句" 是精确短语匹配，几乎必然零结果；逐词 AND 才有命中（实测）。
    q = urllib.parse.quote(" AND ".join(f"all:{w}" for w in query.split()))
    url = (f"http://export.arxiv.org/api/query?search_query={q}"
           f"&start=0&max_results={limit}&sortBy=relevance")
    root = ET.fromstring(_get_text(url))
    ns = {"a": "http://www.w3.org/2005/Atom"}
    out = []
    for e in root.findall("a:entry", ns):
        title = " ".join((e.findtext("a:title", "", ns) or "").split())
        if not title:
            continue
        summary = " ".join((e.findtext("a:summary", "", ns) or "").split())[:800] or None
        published = e.findtext("a:published", "", ns) or ""
        abs_url = (e.findtext("a:id", "", ns) or "").strip()
        arxiv_id = abs_url.rsplit("/", 1)[-1] if abs_url else ""
        out.append({"标题": title, "年份": int(published[:4]) if published[:4].isdigit() else None,
                    "来源": "arXiv", "摘要": summary,
                    "全文链接": f"https://arxiv.org/html/{arxiv_id}" if arxiv_id else None})
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
        out.append({"标题": title, "年份": year, "来源": "Crossref", "摘要": None,
                    "全文链接": None})
    return out

SOURCES = (_s2, _openalex, _arxiv, _crossref)
SOURCE_NAMES = {"_s2": "Semantic Scholar", "_openalex": "OpenAlex",
                "_arxiv": "arXiv", "_crossref": "Crossref"}
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

class _TextExtractor(html.parser.HTMLParser):
    """从 HTML 中提取正文文字，跳过脚本、样式与导航。"""
    SKIP = {"script", "style", "noscript", "header", "footer", "nav"}

    def __init__(self):
        super().__init__()
        self.parts = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self._skip += 1

    def handle_endtag(self, tag):
        if tag in self.SKIP and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)

def fetch_fulltext(item, head_chars=9000, tail_chars=3000):
    """抓取材料的开放获取 HTML 全文并提取正文。
    返回 {"节选": 开头+结尾节选, "字数": 全文字数}；无链接、链接为 PDF 或抓取失败返回 None。
    PDF 无标准库解析手段，不抓；这类材料停留在摘要层。"""
    url = item.get("全文链接")
    if not url or url.lower().endswith(".pdf"):
        return None
    try:
        raw = _get_text(url, timeout=30)
    except Exception:
        return None
    parser = _TextExtractor()
    try:
        parser.feed(raw)
    except Exception:
        return None
    text = re.sub(r"\s+", " ", " ".join(parser.parts)).strip()
    if len(text) < 2000:   # 多半只是摘要页或跳转页，不算全文
        return None
    if len(text) <= head_chars + tail_chars:
        excerpt = text
    else:
        excerpt = text[:head_chars] + "\n……（中略）……\n" + text[-tail_chars:]
    return {"节选": excerpt, "字数": len(text)}
