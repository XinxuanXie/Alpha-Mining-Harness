#!/usr/bin/env python3
"""CORE 全文检索脚本（给生成 agent 的文献探索用，专长是开放获取全文）。

用法:
  python tools/core.py search "<英文检索式>" [--limit 10]  # 输出含是否有全文及全文长度
  python tools/core.py fulltext <CORE id 或 DOI>           # 取单篇全文（截断 30000 字符）

设计说明:
  - key 不写在脚本里，从环境变量 CORE_API_KEY 读；没有 key 能搜，但全文是锁的。
  - 输出是瘦身过的 JSON，不裸传 API 原始返回。
  - 备选方案：fulltext 时 CORE 里没有全文，自动降级到 Unpaywall 按 DOI 查免费
    全文地址（免 key），返回 best_oa_url；再没有，就明确报材料不足，不硬编。
  - 两个实测坑：请求必须带浏览器 UA（CORE 前面的 Cloudflare 按签名拦脚本 UA）；
    搜索路径末尾要带斜杠、详情路径不能带斜杠，规则相反，别改反。
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://api.core.ac.uk/v3"
UNPAYWALL = "https://api.unpaywall.org/v2"
EMAIL = "ysunfn@connect.ust.hk"  # Unpaywall 要求带邮箱参数，不是密钥
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
LOCKED = "Not available for public API users"


# ---------- 基础请求 ----------

def fetch_json(url, headers=None):
    request = urllib.request.Request(url)
    request.add_header("User-Agent", UA)
    for k, v in (headers or {}).items():
        request.add_header(k, v)
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_core(url):
    headers = {}
    key = os.environ.get("CORE_API_KEY", "").strip()
    if key:
        headers["Authorization"] = f"Bearer {key}"
    return fetch_json(url, headers)


# ---------- 结果瘦身 ----------

def slim(work):
    full = work.get("fullText") or ""
    has = bool(full) and full != LOCKED
    return {
        "id": work.get("id"),
        "title": work.get("title"),
        "year": work.get("yearPublished"),
        "doi": work.get("doi"),
        "venue": work.get("sourceFullName") or work.get("publisher"),
        "abstract": (work.get("abstract") or "")[:500],
        "has_fulltext": has,
        "fulltext_chars": len(full) if has else 0,
        "download_url": work.get("downloadUrl"),
    }


# ---------- Unpaywall 备选（只兜 fulltext） ----------

def unpaywall_lookup(doi):
    bare = doi.replace("https://doi.org/", "")
    q = urllib.parse.urlencode({"email": EMAIL})
    try:
        data = fetch_json(f"{UNPAYWALL}/{urllib.parse.quote(bare, safe='')}?{q}")
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return None
    loc = data.get("best_oa_location") or {}
    return loc.get("url_for_pdf") or loc.get("url")


# ---------- 两个命令 ----------

def cmd_search(query, limit):
    q = urllib.parse.urlencode({"q": query, "limit": limit})
    data = fetch_core(f"{BASE}/search/works/?{q}")  # 搜索路径带斜杠
    return [slim(w) for w in data.get("results", [])]


def fetch_work(ref):
    if ref.startswith("10."):
        q = urllib.parse.urlencode({"q": f'doi:"{ref}"', "limit": 1})
        data = fetch_core(f"{BASE}/search/works/?{q}")
        results = data.get("results", [])
        if not results:
            return None
        return results[0]
    return fetch_core(f"{BASE}/works/{ref}")  # 详情路径不带斜杠


def cmd_fulltext(ref):
    work = fetch_work(ref)
    if work is None:
        return {"ref": ref, "error": "CORE 里查不到这篇"}
    full = work.get("fullText") or ""
    if full and full != LOCKED:
        return {"id": work.get("id"), "title": work.get("title"),
                "fulltext_chars": len(full), "fulltext": full[:30000]}
    # CORE 没有全文：降级 Unpaywall 按 DOI 找免费地址
    doi = work.get("doi") or (ref if ref.startswith("10.") else None)
    oa_url = unpaywall_lookup(doi) if doi else None
    if oa_url:
        return {"id": work.get("id"), "title": work.get("title"),
                "error": "CORE 无全文，Unpaywall 找到免费全文地址",
                "best_oa_url": oa_url}
    return {"id": work.get("id"), "title": work.get("title"),
            "error": "CORE 与 Unpaywall 都没有全文，材料不足",
            "download_url": work.get("downloadUrl")}


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
    elif cmd == "fulltext":
        out = cmd_fulltext(args[1])
    else:
        print(__doc__)
        return
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
