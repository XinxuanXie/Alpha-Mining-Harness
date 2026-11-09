# run.py — 调度
# 职责：按想、做、测、记的顺序串联四步，逐条处理假设；只有本程序写记录文件。
# 运行：python run.py [--rounds N] [--batch N]（参数在运行前设定，运行期间不更改）

import argparse
import json
import os

import calc
import factor_agent
import hypothesis_agent

# ============================================================
# 参数（出自 spec 参数表）
# ============================================================
BATCH = 8          # 每轮批量（条假设）
H = 20             # 判定期限（日）：统一口径，经典因子与生成因子同尺测算
THRESHOLD = 0.02  # 门槛：Rank IC 均值 ≥ 此值
ICIR_THRESHOLD = 0.2  # 门槛：ICIR ≥ 此值（与 IC 门槛同时满足）
CORR_THRESHOLD = 0.8  # 门槛：与经典因子最大相关 < 此值（≥ 此值视为与经典重复）
MAX_REWRITE = 3    # 公式重写上限（次）
FEEDBACK_MAX = 3   # 判定反馈修改上限（次）：不通过后按程序诊断改公式、重测的次数
MAX_ROUNDS = 10    # 运行轮次上限

BASE = os.path.dirname(os.path.abspath(__file__))
RECORDS_PATH = os.path.join(BASE, "records.jsonl")
PARAMS_LOG = os.path.join(BASE, "params_log.jsonl")

# ============================================================
# 主循环：一轮 = 想（成批提出）→ 逐条 做（写公式）→ 测（判定）→ 记（落盘）
# ============================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=MAX_ROUNDS)
    ap.add_argument("--batch", type=int, default=BATCH)
    args = ap.parse_args()

    wide = calc.load_wide()
    # 经典因子值：读存好的值表（无表时算一次并存表），供相关性判定使用
    classic_values = calc.load_classics(wide, calc.CLASSIC_FORMULAS)
    records = calc.read_records(RECORDS_PATH)
    start_round = max([r["轮次"] for r in records], default=0) + 1
    # 已通过因子的因子值，供「与已通过因子最大相关」使用（含往轮通过者）
    passed_values = []
    for rec in records:
        if rec["结论"] == "通过":
            try:
                passed_values.append(calc.eval_formula(rec["公式"], wide))
            except ValueError:
                pass

    for rnd in range(start_round, start_round + args.rounds):
        # 本轮参数随记录一并保存，可查
        with open(PARAMS_LOG, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"轮次": rnd, "批量": args.batch, "判定期限": H,
                                 "门槛": THRESHOLD, "ICIR门槛": ICIR_THRESHOLD, "相关门槛": CORR_THRESHOLD,
                                 "重写上限": MAX_REWRITE, "反馈修改上限": FEEDBACK_MAX}, ensure_ascii=False) + "\n")
        try:
            hyps = hypothesis_agent.propose(
                calc.tried_hypotheses(records, THRESHOLD, ICIR_THRESHOLD, CORR_THRESHOLD),
                batch=args.batch)
        except RuntimeError as e:
            print(f"第 {rnd} 轮停止：{e}")
            break
        print(f"第 {rnd} 轮：提出 {len(hyps)} 条")
        for hyp in hyps:
            try:
                formula, reason = factor_agent.build_factor(hyp, wide, max_rewrite=MAX_REWRITE)
            except RuntimeError as e:
                print(f"第 {rnd} 轮停止（已落盘的记录不受影响）：{e}")
                return
            if formula is None:
                rec = {"轮次": rnd, "假设": hyp["hypothesis"], "公式": reason,
                       "判定数字": None, "结论": "无法表达"}
                calc.append_record(RECORDS_PATH, rec)
                records.append(rec)
                print(" -", rec["结论"], "|", hyp["hypothesis"][:36])
                continue
            # 判定反馈修改：不通过时程序按指标诊断最突出的问题，译成修改要求返回因子 Agent 改公式，
            # 改后重新核对与判定；每个版本各记一行。训练段内迭代，验证与测试段不受影响。
            attempt = formula
            for rev in range(FEEDBACK_MAX + 1):
                values = calc.eval_formula(attempt, wide)
                metrics = calc.compute_metrics(values, wide, H, passed_values, classic_values)
                passed = calc.judge(metrics["IC均值"], THRESHOLD, metrics["ICIR"], ICIR_THRESHOLD,
                                    metrics["与经典因子最大相关"], CORR_THRESHOLD)
                rec = {"轮次": rnd, "假设": hyp["hypothesis"], "公式": attempt,
                       "判定数字": metrics, "结论": "通过" if passed else "不通过"}
                calc.append_record(RECORDS_PATH, rec)
                records.append(rec)
                print(" -", rec["结论"], (f"（修改第 {rev} 版）" if rev else ""), "|", hyp["hypothesis"][:36],
                      "| IC:", metrics["IC均值"], "| ICIR:", metrics["ICIR"])
                if passed:
                    passed_values.append(values)
                    break
                if rev == FEEDBACK_MAX:
                    break
                diag = calc.diagnose(metrics, THRESHOLD, ICIR_THRESHOLD, CORR_THRESHOLD)
                feedback = diag + "\n\n上一版的全部关键指标：\n" + calc.metrics_brief(metrics)
                try:
                    new_formula, _ = factor_agent.build_factor(
                        hyp, wide, max_rewrite=MAX_REWRITE, feedback=feedback, prev_formula=attempt)
                except RuntimeError as e:
                    print(f"第 {rnd} 轮停止（已落盘的记录不受影响）：{e}")
                    return
                if new_formula is None or new_formula == attempt:
                    break
                attempt = new_formula
    print("完成。记录总数:", len(records))

if __name__ == "__main__":
    main()
