#!/usr/bin/env python3
"""OpenAlex 文献检索脚本（给生成 agent 的文献探索用）。

用法:
  python tools/search/openalex.py search "<英文检索式>" [--limit 10]
  python tools/search/openalex.py citing <work_id 或 DOI> [--limit 10]      # 谁引用了它
  python tools/search/openalex.py references <work_id 或 DOI> [--limit 20]  # 它引用了谁

设计说明:
  - key 不写在脚本里，从环境变量 OPENALEX_API_KEY 读；没有 key 也能跑（走公共额度）。
  - 输出是瘦身过的 JSON（标题、年份、被引、DOI、出处、摘要），不裸传 API 原始返回。
  - 备选方案：search 时 OpenAlex 调不通，自动降级到 Crossref 检索（免 key），
    返回记录带 "source": "crossref" 标明来源；引用追踪没有备选，失败就报错。
"""
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://api.openalex.org"
CROSSREF = "https://api.crossref.org"
EMAIL = "ysunfn@connect.ust.hk"  # Crossref / OpenAlex polite pool 用，不是密钥
SELECT = ("id,display_name,publication_year,cited_by_count,doi,"
          "primary_location,abstract_inverted_index,referenced_works")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")


# ---------- 基础请求 ----------

def fetch_json(url, headers=None):
    request = urllib.request.Request(url)
    request.add_header("User-Agent", UA)
    for k, v in (headers or {}).items():
        request.add_header(k, v)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_openalex(url):
    headers = {}
    key = os.environ.get("OPENALEX_API_KEY", "").strip()
    if key:
        headers["Authorization"] = f"Bearer {key}"
    return fetch_json(url, headers)


# ---------- OpenAlex 结果瘦身 ----------

def rebuild_abstract(inverted):
    if not inverted:
        return ""
    positions = {}
    for word, idxs in inverted.items():
        for i in idxs:
            positions[i] = word
    return " ".join(positions[i] for i in sorted(positions))[:500]


def slim_openalex(work):
    loc = work.get("primary_location") or {}
    src = loc.get("source") or {}
    return {
        "source": "openalex",
        "id": (work.get("id") or "").replace("https://openalex.org/", ""),
        "title": work.get("display_name"),
        "year": work.get("publication_year"),
        "cited_by": work.get("cited_by_count"),
        "doi": work.get("doi"),
        "venue": src.get("display_name"),
        "abstract": rebuild_abstract(work.get("abstract_inverted_index")),
    }


def resolve_id(ref):
    if ref.startswith("10."):
        return f"{BASE}/works/doi:{ref}"
    return f"{BASE}/works/{ref.replace('https://openalex.org/', '')}"


# ---------- Crossref 备选（只兜 search） ----------

def slim_crossref(item):
    title = (item.get("title") or [""])[0]
    year = None
    for field in ("issued", "published-print", "published-online"):
        parts = ((item.get(field) or {}).get("date-parts") or [[None]])[0]
        if parts and parts[0]:
            year = parts[0]
            break
    abstract = re.sub(r"<[^>]+>", "", item.get("abstract") or "")[:500]
    return {
        "source": "crossref",
        "id": None,
        "title": title,
        "year": year,
        "cited_by": item.get("is-referenced-by-count"),
        "doi": ("https://doi.org/" + item["DOI"]) if item.get("DOI") else None,
        "venue": (item.get("container-title") or [""])[0],
        "abstract": abstract,
    }


def search_crossref(query, limit):
    q = urllib.parse.urlencode({"query.bibliographic": query, "rows": limit,
                                "mailto": EMAIL})
    data = fetch_json(f"{CROSSREF}/works?{q}")
    return [slim_crossref(it) for it in data.get("message", {}).get("items", [])]


# ---------- 三个命令 ----------

def cmd_search(query, limit):
    q = urllib.parse.urlencode({"search": query, "per-page": limit,
                                "select": SELECT, "mailto": EMAIL})
    try:
        data = fetch_openalex(f"{BASE}/works?{q}")
        return [slim_openalex(w) for w in data.get("results", [])]
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return search_crossref(query, limit)  # 主源不通，降级备选


def cmd_citing(ref, limit):
    work = fetch_openalex(resolve_id(ref))
    wid = (work.get("id") or "").replace("https://openalex.org/", "")
    q = urllib.parse.urlencode({"filter": f"cites:{wid}", "per-page": limit,
                                "select": SELECT, "mailto": EMAIL})
    data = fetch_openalex(f"{BASE}/works?{q}")
    return [slim_openalex(w) for w in data.get("results", [])]


def cmd_references(ref, limit):
    work = fetch_openalex(resolve_id(ref))
    refs = (work.get("referenced_works") or [])[:limit]
    if not refs:
        return []
    ids = "|".join(r.replace("https://openalex.org/", "") for r in refs)
    q = urllib.parse.urlencode({"filter": f"openalex:{ids}", "per-page": len(refs),
                                "select": SELECT, "mailto": EMAIL})
    data = fetch_openalex(f"{BASE}/works?{q}")
    return [slim_openalex(w) for w in data.get("results", [])]


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return
    cmd = args[0]
    limit = 10
    if "--limit" in args:
        i = args.index("--limit")
        limit = int(args[i + 1])
        args = args[:i] + args[i + 2:]
    if cmd == "search":
        out = cmd_search(" ".join(args[1:]), limit)
    elif cmd == "citing":
        out = cmd_citing(args[1], limit)
    elif cmd == "references":
        out = cmd_references(args[1], limit)
    else:
        print(__doc__)
        return
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
