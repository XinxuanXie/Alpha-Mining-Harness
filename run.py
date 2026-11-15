# run.py — 因子挖掘系统入口（2026-11-15 新系统）
# 用法：
#   python run.py --new        新开一条因子（自动生成 run_id，跑完整生命周期）
#   python run.py --resume ID  按 run_id 从最近检查点恢复
# 模型经保险库调用时，用 hidden_files/run_graph_with_vault.py 启动（原理同旧启动器）。

import argparse
import os
import sys
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

import graph  # noqa: E402

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--new", action="store_true", help="新开一条因子")
    ap.add_argument("--resume", metavar="RUN_ID", help="按 run_id 恢复")
    args = ap.parse_args()
    if not args.new and not args.resume:
        ap.error("需要 --new 或 --resume RUN_ID")

    app = graph.compile_with_sqlite()
    if args.resume:
        run_id = args.resume
        config = {"configurable": {"thread_id": run_id}, "recursion_limit": 300}
        print(f"恢复 thread {run_id}", flush=True)
        final = app.invoke(None, config)
    else:
        run_id = "F" + datetime.now().strftime("%Y%m%d%H%M%S")
        config = {"configurable": {"thread_id": run_id}, "recursion_limit": 300}
        print(f"新开 thread {run_id}", flush=True)
        final = app.invoke({"run_id": run_id, "attempts": [], "cards_out": [],
                            "queue": []}, config)

    print("=== 运行结束 ===", flush=True)
    print("run_id:", run_id, flush=True)
    print("尝试数:", len(final.get("attempts", [])), flush=True)
    for a in final.get("attempts", []):
        print(f"  第{a['轮次']}轮 {a['名称']} IC {a['IC']} ICIR {a['ICIR']} 通过 {a['通过']}", flush=True)
    print("经验卡:", len(final.get("cards_out", [])), "张", flush=True)
    for c in final.get("cards_out", []):
        print(f"  {c['名称']}｜{c['死因分类']}｜{c['结论']}", flush=True)
    if final.get("test_verdict"):
        print("测试段裁决:", final["test_verdict"], flush=True)

if __name__ == "__main__":
    main()
