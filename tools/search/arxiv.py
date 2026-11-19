#!/usr/bin/env python3
"""arXiv 预印本检索脚本（给生成 agent 的文献探索用，免 key 的最后备选）。

用法:
  python tools/search/arxiv.py search "<英文检索式>" [--limit 10] [--all]
  （默认只搜 q-fin 分区；--all 才搜全站，一般不用）

定位:
  - OpenAlex 有每日额度、CORE 全文也有免费档限速；arXiv 不要 key、没有额度，
    主通道额度用完时靠它继续搜。代价是覆盖窄：只有预印本，金融看 q-fin 分区。
  - 它补的另一块是新：刚挂出的工作论文 OpenAlex 还没收录，这里能直接查到，
    且每条都带 PDF 地址。
  - 输出瘦身过的 JSON（标题、年份、作者、摘要、分类、PDF 地址），不裸传原始返回。
  - arXiv 官方要求请求间隔 3 秒以上；本脚本一次运行只发一次请求，天然满足。
"""
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

BASE = "https://export.arxiv.org/api/query"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
NS = {"a": "http://www.w3.org/2005/Atom",
      "arxiv": "http://arxiv.org/schemas/atom"}


def build_query(text, all_cats=False):
    """把检索词拼成 arXiv 的检索语法。

    两条实测规则：
    - 连字符必须拆开：all:short-term 匹配不到任何东西，拆成
      all:short AND all:term 才有结果（实测 0 条 vs 328 条）。
    - 默认限定 q-fin.* 分区：不限分区时 "short-term reversal" 搜出来的是
      地震、孤子、神经科学；限定后 39 条全是金融（实测对比过）。
    """
    words = [w for w in re.split(r"[\s\-]+", text) if w]
    body = "+AND+".join(f"all:{urllib.parse.quote(w)}" for w in words)
    if all_cats:
        return body
    return f"cat:q-fin.*+AND+{body}"


def slim(entry):
    title = " ".join((entry.findtext("a:title", default="", namespaces=NS) or "").split())
    summary = " ".join((entry.findtext("a:summary", default="", namespaces=NS) or "").split())[:500]
    published = entry.findtext("a:published", default="", namespaces=NS) or ""
    authors = [a.findtext("a:name", namespaces=NS) for a in entry.findall("a:author", NS)]
    pdf_url = ""
    for link in entry.findall("a:link", NS):
        if link.get("title") == "pdf" or link.get("type") == "application/pdf":
            pdf_url = link.get("href") or ""
    raw_id = entry.findtext("a:id", default="", namespaces=NS) or ""
    cats = [c.get("term") for c in entry.findall("a:category", NS)]
    return {
        "source": "arxiv",
        "id": raw_id.replace("http://arxiv.org/abs/", "").replace("https://arxiv.org/abs/", ""),
        "title": title,
        "year": int(published[:4]) if published[:4].isdigit() else None,
        "authors": authors,
        "categories": cats,
        "abstract": summary,
        "pdf_url": pdf_url,
    }


def cmd_search(query, limit, all_cats=False):
    q = (f"search_query={build_query(query, all_cats)}&start=0&max_results={limit}"
         f"&sortBy=relevance&sortOrder=descending")
    request = urllib.request.Request(f"{BASE}?{q}")
    request.add_header("User-Agent", UA)
    with urllib.request.urlopen(request, timeout=30) as response:
        body = response.read().decode("utf-8")
    if "Rate exceeded" in body:  # arXiv 限流时返回纯文本而不是 XML
        return [{"source": "arxiv", "error": "arXiv 限流（Rate exceeded），稍后再试"}]
    root = ET.fromstring(body)
    return [slim(e) for e in root.findall("a:entry", NS)]


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
    all_cats = "--all" in args
    if all_cats:
        args.remove("--all")
    if cmd == "search":
        try:
            out = cmd_search(" ".join(args[1:]), limit, all_cats)
        except (urllib.error.URLError, TimeoutError, ET.ParseError) as exc:
            out = [{"source": "arxiv", "error": f"检索失败：{exc}"}]
    else:
        print(__doc__)
        return
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
