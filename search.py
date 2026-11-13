# search.py — 文献检索（普通网络搜索）
# 职责：按英文检索式做普通网络搜索（DuckDuckGo，经 ddgs 包，无需 API key），
# 返回材料列表（标题、链接、摘要）。摘要取搜索结果的正文片段——筛选与优化读的是
# 片段，与原先读论文摘要同位。来源单一，不再逐源降级：失败或空结果时等待后重试
# 一次；成败与错误记入 LAST_REPORT，供调度程序写入轨迹，不再静默吞掉。
# 全部失败返回空列表，不中断主流程。
# 另提供 fetch_fulltext：抓取开放获取的 HTML 全文并提取正文，供筛选后深读；
# 链接为 PDF 或抓不到返回空（PDF 无标准库解析手段，停留在片段层）。
# 结果按检索式缓存到 lit_cache.json：只有带摘要（片段非空）的结果才写缓存，
# 缓存中只有标题级材料的条目不沿用，同一检索式不重复请求。

import html.parser
import json
import os
import re
import time
import urllib.request

from ddgs import DDGS

BASE = os.path.dirname(os.path.abspath(__file__))
CACHE_PATH = os.path.join(BASE, "lit_cache.json")
TIMEOUT = 30

LAST_REPORT = []   # 最近一次 search() 的来源结果（成功条数或失败错误），供轨迹记录

def last_report():
    return [dict(x) for x in LAST_REPORT]

def _get_text(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": "factor-loop/1.0 (research)"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")

def _ddgs_raw(query, limit):
    """向 DuckDuckGo 发一次检索，返回原始结果 [{title, href, body}]。"""
    with DDGS(timeout=TIMEOUT) as ddgs:
        return list(ddgs.text(query, max_results=limit))

def _web_search(query, limit):
    """把网络搜索原始结果整理成材料列表：片段压空白后截断充当摘要，
    片段为空则摘要为 None（仅标题级材料）；同链接重复结果只留一条。
    网络搜索不提供年份，年份记 None，下游按缺失处理。"""
    out, seen = [], set()
    for r in _ddgs_raw(query, limit):
        title = " ".join((r.get("title") or "").split())
        href = (r.get("href") or "").strip()
        if not title or (href and href in seen):
            continue
        if href:
            seen.add(href)
        snippet = " ".join((r.get("body") or "").split())[:800] or None
        out.append({"标题": title, "年份": None, "来源": "网络搜索",
                    "摘要": snippet, "全文链接": href or None})
    return out

def _attempt(query, limit):
    """调用网络搜索；失败或空结果等待 3 秒重试一次。返回 (结果列表, 报告项)。"""
    first_err = None
    try:
        r = _web_search(query, limit)
        if r:
            return r, {"来源": "网络搜索", "结果": f"返回 {len(r)} 条"}
        first_err = "返回空结果"
    except Exception as e:
        first_err = f"{type(e).__name__}: {e}"[:120]
    time.sleep(3)
    try:
        r = _web_search(query, limit)
        if r:
            return r, {"来源": "网络搜索", "结果": f"重试成功，返回 {len(r)} 条"}
        return [], {"来源": "网络搜索", "结果": "失败",
                    "错误": f"两次均为空结果（首次：{first_err}）"}
    except Exception as e:
        return [], {"来源": "网络搜索", "结果": "失败",
                    "错误": f"重试后仍失败（首次：{first_err}）：{type(e).__name__}: {e}"[:160]}

def _load_cache():
    if os.path.exists(CACHE_PATH):
        try:
            with open(CACHE_PATH, encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            return {}
    return {}

def search(query, limit=5):
    """按检索式查资料，返回 [{标题, 年份, 来源, 摘要, 全文链接}]；
    摘要为 None 表示仅有标题级材料（搜索片段为空）。"""
    global LAST_REPORT
    LAST_REPORT = []
    cache = _load_cache()
    if query in cache and any(it.get("摘要") for it in cache[query]):
        LAST_REPORT = [{"来源": "缓存", "结果": f"返回 {len(cache[query][:limit])} 条"}]
        return cache[query][:limit]
    # 缓存中只有标题级材料的条目不沿用：来源恢复后应能重新检索到带摘要的结果。
    results, item = _attempt(query, limit)
    LAST_REPORT.append(item)
    if results and any(it.get("摘要") for it in results):
        # 只缓存带摘要的结果：空结果不缓存（暂时失败不应把检索式永久封死），
        # 纯标题结果不缓存（下次运行应重试，争取拿到摘要）。
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
