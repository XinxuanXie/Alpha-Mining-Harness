# run.py — 调度程序
# 职责：按七步串联全流程——登记线索 → 展开假设 → 实现与程序检查 → 回测 → 对抗检验
#       → 讲评归档 → 经验回流与预算再发放。本文件是唯一有权写账本与经验库的程序。
# 依据：《因子挖掘系统新计划》与《第一期实现规格》。判定一律由程序按规则执行，模型不参与判定。

import json
import os
import sys
from datetime import datetime

import calc
import agents

# ============================================================
# 参数（规格第五节的待定数值，第一期初始值）
# ============================================================
BASE = os.path.dirname(os.path.abspath(__file__))
RECORDS_PATH = os.path.join(BASE, "records.jsonl")
EXP_PATH = os.path.join(BASE, "experience.jsonl")
CLUES_PATH = os.path.join(BASE, "clues.jsonl")
TRACE_PATH = os.path.join(BASE, "trace.jsonl")
IC_THRESHOLD = 0.02        # 基础判定：Rank IC 门槛
ICIR_THRESHOLD = 0.2       # 基础判定：ICIR 门槛
CORR_THRESHOLD = 0.8       # 基础判定：与经典因子最大相关上限
CONSISTENCY_MIN = 0.99     # 一致性检查：截面相关下限
HIT_LINE = 0.5             # 预算发放：方向预测命中率线
PRED_GAP = 0.005           # 预测兑现：两组 IC 差值线
SUBPERIOD_T = 2.0          # 对抗检验：子时段反例的 |t| 线
COVERAGE_MIN = 0.5         # 覆盖率异常线（低于此值记数据层）
EXP_LIMIT = 10             # 经验读入上限（条）
MAX_ATTEMPTS = 3           # 每个方向的尝试次数上限
FORMULA_REWRITE_MAX = 3    # 公式重写上限（一致性或可算性未过时，不计入尝试次数）
REVIEW_REWRITE_MAX = 2     # 讲评数字核对未过时的重写上限
MAX_TOTAL_ATTEMPTS = 9     # 循环运行的停止条件：本进程总尝试数上限（防无限消耗调用）

# ============================================================
# 读写：账本与经验库（JSON Lines，一行一条）
# ============================================================
def read_jsonl(path):
    if not os.path.exists(path):
        return []
    out = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out

def append_jsonl(path, obj):
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(obj, ensure_ascii=False) + "\n")

def trace(event, **fields):
    """过程轨迹：逐条事件落盘，只写不读——供实验结束后分析，不回流给模型、不进任何提示。

    写入失败绝不中断实验（best-effort，静默）。
    """
    try:
        row = {"时间": datetime.now().isoformat(timespec="seconds"), "事件": event}
        row.update(fields)
        append_jsonl(TRACE_PATH, row)
    except Exception:
        pass

# ============================================================
# 登记校验（规格 2.4）：程序逐项检查，任一不过即拒登
# ============================================================
def validate_registration(hyp, exp_entries, rejected_keys, sectors=None):
    errs = []
    if hyp.get("category") not in agents.CATEGORIES:
        errs.append(f"机制类别不在词表内：{hyp.get('category')}")
    bf = hyp.get("baseline_formula")
    if not bf:
        errs.append("基准公式为空")
    else:
        ok, bad = calc.check_whitelist(bf)
        if not ok:
            errs.append(f"基准公式含清单外算子或字段：{bad}")
    preds = hyp.get("predictions") or []
    if len(preds) < 2:
        errs.append("条件预测少于两条")
    if sum(1 for p in preds if p.get("key")) != 1:
        errs.append("关键预测必须恰有一条")
    for p in preds:
        dim, a, b = p.get("dim"), str(p.get("a")), str(p.get("b"))
        if dim not in ("市值组", "持有期", "行业"):
            errs.append(f"预测维度第一期不开放：{dim}")
        elif dim == "市值组" and not (a in ("小", "中", "大") and b in ("小", "中", "大")):
            errs.append(f"市值组预测的 a、b 只能取 小/中/大：{a} vs {b}")
        elif dim == "持有期" and not (a in ("1", "5", "10", "20", "60") and b in ("1", "5", "10", "20", "60")):
            errs.append(f"持有期预测的 a、b 只能取 1/5/10/20/60：{a} vs {b}")
        elif dim == "行业":
            if b != "整体":
                errs.append(f"行业预测的 b 固定为“整体”：{b}")
            if sectors is not None and a not in sectors:
                errs.append(f"行业预测的 a 必须是真实行业名：{a}")
    if exp_entries and not hyp.get("exp_refs"):
        errs.append("未引用任何经验条目")
    if rejected_keys and not (hyp.get("diff_from_rejected") or "").strip():
        errs.append("同类别有已否决或关键预测未兑现的方向，未写明区别")
    return errs

def validate_clue(clue, existing_directions):
    """线索登记校验：人工登记与 agent 自提同一标准。"""
    errs = []
    if clue.get("category") not in agents.CATEGORIES:
        errs.append(f"机制类别不在词表内：{clue.get('category')}")
    if not (clue.get("direction") or "").strip():
        errs.append("方向名为空")
    elif clue["direction"] in existing_directions:
        errs.append(f"方向已存在：{clue['direction']}")
    if not (clue.get("phenomenon") or "").strip():
        errs.append("现象为空")
    if not (clue.get("source") or "").strip():
        errs.append("收益来源为空")
    return errs

# ============================================================
# 预测核对（规格 2.3）：方向一致且两组 IC 差值 ≥ 0.005 记兑现
# 预测格式：{dim, a, b, key}，含义为 a 组的 IC 高于 b 组
# ============================================================
def check_predictions(hyp, metrics):
    results = []
    for p in hyp["predictions"]:
        dim, a, b = p["dim"], str(p["a"]), str(p["b"])
        va = vb = None
        if dim == "市值组":
            va, vb = metrics["分市值组IC"].get(a), metrics["分市值组IC"].get(b)
        elif dim == "持有期":
            va, vb = metrics["各持有期IC"].get(a), metrics["各持有期IC"].get(b)
        elif dim == "行业":
            va = metrics["分行业IC"].get(a)
            vb = metrics["IC均值"]  # b 固定为“整体”
        ok = va is not None and vb is not None and (va - vb) >= PRED_GAP
        results.append({"dim": dim, "a": a, "b": b, "key": bool(p.get("key")),
                        "a值": va, "b值": vb, "兑现": bool(ok)})
    return results

# ============================================================
# 对抗检验（规格 2.3）：只找反例，只否决，不改因子
# ============================================================
def adversarial(hyp, factor, baseline_values, metrics, wide, classics):
    adv = {"子时段反例": [], "对称检验": "不适用", "反例": False}
    full_ic = metrics["IC均值"]
    if full_ic is not None:
        for seg in metrics["分段IC"]:
            if (seg["IC"] is not None and seg["t值"] is not None
                    and (seg["IC"] > 0) != (full_ic > 0) and abs(seg["t值"]) >= SUBPERIOD_T):
                adv["子时段反例"].append(seg["段"])
        if adv["子时段反例"]:
            adv["反例"] = True
    # 对称检验：机制对称的类别强制执行。做法为信号两端分组检验——
    # 按基准值符号把股票日分正负两组，分别算因子 IC；任一组方向与全期相反且显著，记反例。
    # 基准值无符号变化（如波动恒为正）时不适用。
    if hyp["category"] in agents.SYMMETRIC_CATEGORIES and full_ic is not None:
        pos = baseline_values > 0
        neg = baseline_values < 0
        if pos.any().any() and neg.any().any():
            label = calc._label(wide["close"], calc.JUDGE_H)
            groups = []
            for name, m in (("正组", pos), ("负组", neg)):
                daily = calc._ic_series(factor.where(m), label)
                groups.append((name, calc._mean_or_none(daily), calc._t_of(daily)))
            flipped = [n for n, ic_g, t_g in groups
                       if ic_g is not None and t_g is not None
                       and (ic_g > 0) != (full_ic > 0) and abs(t_g) >= SUBPERIOD_T]
            if flipped:
                adv["对称检验"] = f"{flipped[0]}方向反转"
                adv["反例"] = True
            elif any(ic_g is None or ic_g == 0 or (ic_g > 0) != (full_ic > 0)
                     for _, ic_g, _ in groups):
                adv["对称检验"] = "对称性弱"
            else:
                adv["对称检验"] = "已执行（两端同向）"
        else:
            adv["对称检验"] = "不适用（基准值无符号变化）"
    return adv

# ============================================================
# 失效层定位（规格 2.7）：程序按固定规则判定
# ============================================================
def failure_layer(record_kind, metrics, base_ok, pred_results, adv):
    if record_kind == "无法表达":
        return "实现层"
    if metrics is not None and metrics["覆盖率"] is not None and metrics["覆盖率"] < COVERAGE_MIN:
        return "数据层"
    if base_ok:
        return "检验层"   # 基础判定已过，倒在预测核对或对抗检验
    return "想法层"

def exp_status(verdict):
    """经验状态与账本结论同名对齐：通过→已通过，条件成立→条件成立，否决→已否决。"""
    return {"通过": "已通过", "条件成立": "条件成立", "否决": "已否决"}[verdict]

# ============================================================
# 预算（规格第三节）：每方向最多 3 次，逐次按命中率动态发放
# ============================================================
def direction_stats(records, direction):
    mine = [r for r in records if r["方向"] == direction]
    used = len(mine)
    total = sum(len(r["预测核对"]) for r in mine if r.get("预测核对"))
    hit = sum(1 for r in mine if r.get("预测核对") for p in r["预测核对"] if p["兑现"])
    hit_rate = (hit / total) if total else None
    key_failed = any(p["key"] and not p["兑现"] for r in mine if r.get("预测核对") for p in r["预测核对"])
    return {"已用": used, "命中率": hit_rate, "关键预测曾未兑现": key_failed}

def can_issue(records, direction):
    st = direction_stats(records, direction)
    if st["已用"] >= MAX_ATTEMPTS:
        return False, f"已达上限 {MAX_ATTEMPTS} 次"
    if st["已用"] == 0:
        return True, "首次发放"
    if st["命中率"] is None:
        return True, "尚无可核对的预测，按未用满发放"
    if st["命中率"] >= HIT_LINE:
        return True, f"命中率 {st['命中率']:.2f} 达线"
    return False, f"命中率 {st['命中率']:.2f} 未达 {HIT_LINE}，停止发放并封存"

# ============================================================
# 单条假设的完整流程：第 3 至第 6 步（实现、回测、对抗、讲评）
# ============================================================
def process_hypothesis(hyp, wide, classics, cap_complexity):
    rec = {"方向": hyp["direction"], "机制类别": hyp["category"], "假设": hyp["hypothesis"],
           "登记": {"计算方式": hyp["measure"], "基准公式": hyp["baseline_formula"],
                    "机制": hyp["mechanism"], "条件预测": hyp["predictions"],
                    "否定条件": hyp["falsify"]},
           "公式": None, "判定数字": None, "预测核对": None, "对抗检验": None,
           "生成侧对抗": None, "检验侧对抗": None,
           "结论": None, "失效层": None}
    baseline_values = calc.eval_formula(hyp["baseline_formula"], wide)

    # 生成侧对抗审查（模型）：专攻登记内容——是否经典换皮、预测是否注水、机制是否自洽。
    # 只留痕，不参与判定，不给修改方案；攻击记录经已否决摘要回流，成为下一次展开必须回应的输入。
    try:
        rec["生成侧对抗"] = agents.attack_registration(hyp, calc.CLASSIC_FORMULAS)
    except Exception as e:
        trace("生成对抗失败", 方向=hyp["direction"], 假设=hyp["hypothesis"], 错误=str(e))
    trace("生成对抗", 方向=hyp["direction"], 假设=hyp["hypothesis"], 对抗=rec["生成侧对抗"])

    # 第 3 步：写公式 + 程序检查（白名单、复杂度、一致性）；登记锁定，只改公式
    formula, last_err = None, None
    for attempt in range(1, FORMULA_REWRITE_MAX + 2):
        out = agents.write_formula(hyp, last_err)
        if not out.get("formula"):
            trace("写公式", 方向=hyp["direction"], 假设=hyp["hypothesis"], 第几次=attempt,
                  公式=None, 模型原因=out.get("reason", ""))
            rec["结论"] = "无法表达"
            rec["失效层"] = "实现层"
            rec["无法表达原因"] = out.get("reason", "")
            return rec
        cand = out["formula"]
        ok, bad = calc.check_whitelist(cand)
        if not ok:
            last_err = f"公式含清单外算子或字段：{bad}"
            trace("公式检查", 方向=hyp["direction"], 假设=hyp["hypothesis"], 第几次=attempt,
                  公式=cand, 结果="未通过：" + last_err)
            continue
        if calc.complexity(cand) > cap_complexity:
            last_err = f"复杂度 {calc.complexity(cand)} 超过上限 {cap_complexity}"
            trace("公式检查", 方向=hyp["direction"], 假设=hyp["hypothesis"], 第几次=attempt,
                  公式=cand, 复杂度=calc.complexity(cand), 结果="未通过：" + last_err)
            continue
        try:
            values = calc.eval_formula(cand, wide)
        except ValueError as e:
            last_err = str(e)
            trace("公式检查", 方向=hyp["direction"], 假设=hyp["hypothesis"], 第几次=attempt,
                  公式=cand, 结果="未通过：" + last_err)
            continue
        corr = calc.consistency_corr(values, baseline_values)
        if corr is None or corr < CONSISTENCY_MIN:
            last_err = f"一致性相关 {corr} 低于 {CONSISTENCY_MIN}：公式计算的量与登记不一致"
            trace("公式检查", 方向=hyp["direction"], 假设=hyp["hypothesis"], 第几次=attempt,
                  公式=cand, 一致性相关=corr, 结果="未通过：" + last_err)
            continue
        formula, rec["一致性相关"] = cand, corr
        trace("公式检查", 方向=hyp["direction"], 假设=hyp["hypothesis"], 第几次=attempt,
              公式=cand, 复杂度=calc.complexity(cand), 一致性相关=corr, 结果="通过")
        break
    if formula is None:
        rec["结论"] = "无法表达"
        rec["失效层"] = "实现层"
        rec["无法表达原因"] = f"重写达上限，最后错误：{last_err}"
        trace("结论", 方向=hyp["direction"], 假设=hyp["hypothesis"], 结论="无法表达",
              失效层="实现层", 原因=rec["无法表达原因"])
        return rec
    rec["公式"] = formula
    values = calc.eval_formula(formula, wide)

    # 第 4 步：回测与基础判定
    metrics = calc.compute_metrics(values, wide, classics)
    rec["判定数字"] = metrics
    base_ok = calc.base_judge(metrics, IC_THRESHOLD, ICIR_THRESHOLD, CORR_THRESHOLD)
    trace("回测", 方向=hyp["direction"], 假设=hyp["hypothesis"],
          判定数字=metrics, 基础判定="通过" if base_ok else "未通过")

    # 第 5 步：对抗检验 + 预测核对
    adv = adversarial(hyp, values, baseline_values, metrics, wide, classics)
    rec["对抗检验"] = adv
    pred_results = check_predictions(hyp, metrics)
    rec["预测核对"] = pred_results
    trace("对抗与核对", 方向=hyp["direction"], 假设=hyp["hypothesis"],
          对抗检验=adv, 预测核对=pred_results)
    key_ok = all(p["兑现"] for p in pred_results if p["key"])
    general = [p for p in pred_results if not p["key"]]
    general_majority = (sum(1 for p in general if p["兑现"]) * 2 > len(general)) if general else True

    if base_ok and not adv["反例"] and key_ok and general_majority:
        verdict = "通过"
    elif base_ok and not adv["反例"] and key_ok:
        verdict = "条件成立"   # 基础判定过、无反例、关键预测兑现，仅一般预测未过半
    else:
        verdict = "否决"
    rec["结论"] = verdict
    rec["失效层"] = None if verdict == "通过" else failure_layer("判定", metrics, base_ok, pred_results, adv)
    if metrics["覆盖率"] is not None and metrics["覆盖率"] < COVERAGE_MIN and verdict != "通过":
        rec["失效层"] = "数据层"

    # 检验侧对抗审查（模型）：依据全部数字写失效解释，并指出程序检验覆盖不到的失效方式。
    # 只留痕、进经验，不推翻程序结论，不给改参数重跑的建议。
    try:
        rec["检验侧对抗"] = agents.attack_results(hyp, metrics, pred_results, adv, verdict,
                                                 gen_attack=rec["生成侧对抗"])
    except Exception as e:
        trace("检验对抗失败", 方向=hyp["direction"], 假设=hyp["hypothesis"], 错误=str(e))
    trace("检验对抗", 方向=hyp["direction"], 假设=hyp["hypothesis"], 对抗=rec["检验侧对抗"])

    # 第 6 步：讲评（数字由程序逐项核对，不符打回）
    review, review_ok = None, False
    for r_attempt in range(1, REVIEW_REWRITE_MAX + 2):
        review = agents.write_review(hyp, metrics, pred_results, adv, verdict)
        nums = review.get("numbers") or {}
        want = {"ic": metrics["IC均值"], "icir": metrics["ICIR"], "max_corr": metrics["与经典因子最大相关"]}
        review_ok = all(
            (nums.get(k) is None and v is None) or
            (nums.get(k) is not None and v is not None and round(float(nums[k]), 4) == round(float(v), 4))
            for k, v in want.items())
        if review_ok:
            break
        trace("讲评打回", 方向=hyp["direction"], 假设=hyp["hypothesis"], 第几次=r_attempt,
              模型数字=nums, 程序数字=want)
    rec["讲评核对"] = "通过" if review_ok else "核对失败"
    trace("结论", 方向=hyp["direction"], 假设=hyp["hypothesis"], 结论=verdict,
          失效层=rec["失效层"], 经验状态=exp_status(verdict), 讲评核对=rec["讲评核对"])
    return rec, review, exp_status(verdict), baseline_values

def save_experience(rec, review, status):
    entries = read_jsonl(EXP_PATH)
    no = f"E{len(entries) + 1:03d}"
    layer = rec["失效层"] or "无"
    key_dim = next((p["dim"] for p in (rec["预测核对"] or []) if p["key"] and not p["兑现"]), None)
    fail_tag = "" if status == "已通过" else f"{layer}" + (f"-关键预测未兑现（{key_dim}）" if key_dim else "")
    if status != "已通过" and (rec.get("对抗检验") or {}).get("对称检验") == "对称性弱":
        fail_tag += "-对称性弱"
    entry = {"编号": no, "机制类别": rec["机制类别"], "线索主题": rec["方向"], "状态": status,
             "失败模式标签": fail_tag, "适用条件": (review or {}).get("borrow", "") if review else "",
             "适用时段": "训练段 2000-2016",
             "讲评": ({"measures": review.get("measures", ""), "findings": review.get("findings", ""),
                       "avoid": review.get("avoid", ""), "borrow": review.get("borrow", "")}
                      if review and rec.get("讲评核对") == "通过" else
                      {"measures": "", "findings": "", "avoid": "", "borrow": ""}),
             "推测": (review or {}).get("speculation", "") if review else "",
             "生成侧对抗": rec.get("生成侧对抗"),
             "对抗备忘录": rec.get("检验侧对抗"),
             "来源假设": rec["假设"]}
    append_jsonl(EXP_PATH, entry)
    return entry

# ============================================================
# 主流程：逐条线索跑七步
# ============================================================
def retrieve_exp(category, entries):
    mine = [e for e in entries if e["机制类别"] == category]
    mine.sort(key=lambda e: 0 if e["状态"] in ("已否决", "条件成立") else 1)
    return mine[:EXP_LIMIT]

def rejected_summaries(category, records):
    out = []
    for r in records:
        if r["机制类别"] != category:
            continue
        key_fail = any(p["key"] and not p["兑现"] for p in (r.get("预测核对") or []))
        if r["结论"] == "否决" or key_fail:
            bits = []
            ga, ra = r.get("生成侧对抗") or {}, r.get("检验侧对抗") or {}
            if ga.get("换皮判断"):
                bits.append(f"换皮：{ga['换皮判断']}")
            if ga.get("预测问题") and ga["预测问题"] != "无":
                bits.append(f"预测：{ga['预测问题']}")
            if ga.get("机制问题") and ga["机制问题"] != "无":
                bits.append(f"机制：{ga['机制问题']}")
            if ra.get("失效解释"):
                bits.append(f"死因：{ra['失效解释']}")
            out.append({"方向": r["方向"], "假设摘要": r["假设"],
                        "结局": "已否决" if r["结论"] == "否决" else "关键预测未兑现",
                        "对抗摘要": "；".join(bits)})
    return out

def run_direction(clue, wide, classics, cap_complexity, sectors, stats):
    """跑完一个方向：逐次申请预算、展开、处理，直到停止发放、无合格登记或达总上限。"""
    direction = clue["direction"]
    while stats["done"] < MAX_TOTAL_ATTEMPTS:
        records = read_jsonl(RECORDS_PATH)
        ok, why = can_issue(records, direction)
        trace("预算决定", 方向=direction, 发放=ok, 原因=why)
        if not ok:
            print(f"方向「{direction}」停止发放：{why}")
            return
        entries = read_jsonl(EXP_PATH)
        exp_in = retrieve_exp(clue.get("category"), entries) if clue.get("category") else entries[:EXP_LIMIT]
        rej = rejected_summaries(clue.get("category"), records) if clue.get("category") else []
        hyps = agents.expand_hypotheses(clue, exp_in, rej)
        trace("展开候选", 方向=direction, 候选=hyps, 引用经验=[e["编号"] for e in exp_in])
        chosen = None
        for hyp in hyps:
            errs = validate_registration(
                hyp, exp_in,
                [r for r in rej] if clue.get("category") else [],
                sectors=sectors)
            if not errs:
                hyp["direction"] = direction
                chosen = hyp
                break
            trace("拒登", 方向=direction, 假设=hyp.get("hypothesis"), 原因=errs)
            print(f"假设拒登：{errs}")
        if chosen is None:
            trace("方向终止", 方向=direction, 原因="本轮无合格登记")
            print(f"方向「{direction}」本轮无合格登记，停止")
            return
        result = process_hypothesis(chosen, wide, classics, cap_complexity)
        if isinstance(result, tuple):
            rec, review, status, _ = result
        else:
            rec, review, status = result, None, "已否决"
        append_jsonl(RECORDS_PATH, rec)
        save_experience(rec, review, status)
        stats["done"] += 1
        stats["passed"] += 1 if rec["结论"] == "通过" else 0
        for p in (rec["预测核对"] or []):
            stats["pred_total"] += 1
            stats["pred_hit"] += 1 if p["兑现"] else 0
        print(f"方向「{direction}」第 {direction_stats(read_jsonl(RECORDS_PATH), direction)['已用']} 次尝试："
              f"{chosen['hypothesis'][:40]} → {rec['结论']}"
              + (f"（失效层 {rec['失效层']}）" if rec["失效层"] else ""))

def main():
    wide = calc.load_wide()
    classics = calc.load_classics(wide)
    cap_complexity = calc.classic_complexity_cap()
    sectors = set(calc.SECTOR_OF.values())
    print(f"复杂度上限 {cap_complexity}；已加载训练段数据")
    trace("实验开始", 初始线索数=len(read_jsonl(CLUES_PATH)), 复杂度上限=cap_complexity,
          总尝试上限=MAX_TOTAL_ATTEMPTS)
    calls0 = agents.CALL_COUNT
    stats = {"done": 0, "passed": 0, "pred_total": 0, "pred_hit": 0}
    processed = set()
    stop_reason = f"总尝试数达上限 {MAX_TOTAL_ATTEMPTS}"

    while stats["done"] < MAX_TOTAL_ATTEMPTS:
        clues = read_jsonl(CLUES_PATH)
        todo = [c for c in clues if c["direction"] not in processed]
        if not todo:
            # 无待处理线索：由模型基于经验与已否决记录自提新线索，程序校验后登记
            records = read_jsonl(RECORDS_PATH)
            existing = {c["direction"] for c in clues} | {r["方向"] for r in records}
            rej_all = [s for cat in agents.CATEGORIES for s in rejected_summaries(cat, records)]
            proposed = agents.propose_clues(sorted(existing), read_jsonl(EXP_PATH), rej_all)
            accepted = []
            for c in proposed:
                errs = validate_clue(c, existing | {a["direction"] for a in accepted})
                if not errs:
                    c = dict(c)
                    c["source"] = f"{c['source']}（agent 自提）"
                    accepted.append(c)
                else:
                    print(f"线索拒登：{errs}")
            trace("线索生成", 候选=proposed, 采纳=[a["direction"] for a in accepted])
            if not accepted:
                stop_reason = "agent 无新线索可提，循环结束"
                break
            for a in accepted:
                append_jsonl(CLUES_PATH, a)
                print(f"新线索登记：「{a['direction']}」（{a['category']}）")
            continue
        clue = todo[0]
        run_direction(clue, wide, classics, cap_complexity, sectors, stats)
        processed.add(clue["direction"])

    calls = agents.CALL_COUNT - calls0
    done, passed = stats["done"], stats["passed"]
    trace("实验结束", 完成尝试=done, 通过=passed, 模型调用=calls, 停止原因=stop_reason)
    print(f"\n本轮完成尝试 {done} 条，通过 {passed} 条；模型调用 {calls} 次；停止原因：{stop_reason}")
    if done:
        print(f"首版存活率 {passed / done:.2f}；预测命中率 "
              f"{(stats['pred_hit'] / stats['pred_total']) if stats['pred_total'] else 0:.2f}；"
              f"单位算力产出 {passed / calls * 1000 if calls else 0:.1f} 个/千次调用")

if __name__ == "__main__":
    main()
