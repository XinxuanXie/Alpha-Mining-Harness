# 过程轨迹落盘：把一轮里发生的中间过程（候选、审核、检索、打磨、写公式尝试、核对、诊断）
# 逐条追加到 trace.jsonl，供事后研究发生了什么。只写不读：任何 Agent 都不读它，不进入任何提示。
import json
import os
from datetime import datetime

TRACE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "trace.jsonl")

def add(event):
    """追加一条轨迹。写失败不影响主流程。"""
    try:
        event = {"时间": datetime.now().isoformat(timespec="seconds"), **event}
        with open(TRACE_PATH, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception:
        pass
