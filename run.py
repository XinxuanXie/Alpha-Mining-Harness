# run.py — 调度程序
# 职责：按七步串联全流程——登记线索 → 展开假设 → 实现与程序检查 → 回测 → 对抗检验
#       → 讲评归档 → 经验回流。本文件是唯一有权写账本与经验库的程序。
#       驱动方式为假设锁定 + 因子内循环：新方向的假设只定一次并锁定，
#       循环只在因子层改公式；已有记录的旧方向跳过。
# 依据：《因子挖掘系统新计划》与《第一期实现规格》。判定一律由程序按规则执行，模型不参与判定。

import csv
import json
import os
import sys
import time
from datetime import datetime

import calc
import agents
import search

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
COMPLEXITY_CAP = 20        # 复杂度上限：固定值（Ethan 2026-11-13 定），不再由经典库最大复杂度推导
CONSISTENCY_MIN = 0.99     # 一致性检查：截面相关下限
PRED_GAP = 0.005           # 预测兑现：两组 IC 差值线
SUBPERIOD_T = 2.0          # 对抗检验：子时段反例的 |t| 线
COVERAGE_MIN = 0.5         # 覆盖率异常线（低于此值记数据层）
EXP_LIMIT = 10             # 经验读入上限（条）
FORMULA_REWRITE_MAX = 3    # 公式重写上限（一致性或可算性未过时，不计入尝试次数）
REVIEW_REWRITE_MAX = 2     # 讲评数字核对未过时的重写上限
MAX_TOTAL_ATTEMPTS = int(os.environ.get("FACTOR_MAX_TOTAL_ATTEMPTS", "9"))  # 循环运行的停止条件：本进程总尝试数上限（防无限消耗调用）；可用环境变量 FACTOR_MAX_TOTAL_ATTEMPTS 调整
PRICE_IN_PER_M_USD = 0.27   # DeepSeek Chat 牌价：输入每百万 token 美元数（估算成本用，以官方价格为准）
PRICE_OUT_PER_M_USD = 1.10  # DeepSeek Chat 牌价：输出每百万 token 美元数

def est_cost(in_tokens, out_tokens):
    """按牌价估算成本（美元）。"""
    return round(in_tokens * PRICE_IN_PER_M_USD / 1e6
                 + out_tokens * PRICE_OUT_PER_M_USD / 1e6, 5)

def stamp_cost(rec, snap, t0):
    """把一条尝试的成本与用时写入账本记录：自快照以来的模型用量增量 + 墙钟用时。"""
    u = agents.usage_since(snap)
    rec["成本"] = {"模型调用": u["calls"], "输入token": u["in"], "输出token": u["out"],
                   "估算成本USD": est_cost(u["in"], u["out"]),
                   "用时秒": round(time.time() - t0, 1)}
    return rec["成本"]

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
def validate_registration(hyp, exp_entries, rejected_keys, sectors=None, feedback_dims=None):
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
    if feedback_dims is not None:
        # 有上次尝试的反馈包：必须逐条回应未兑现预测，且至少点名一个未兑现维度，
        # 否则反馈没有落到修改上，拒登。
        resp = (hyp.get("feedback_response") or "").strip()
        if not resp:
            errs.append("有上次尝试反馈包，未写 feedback_response（须逐条回应未兑现预测）")
        elif feedback_dims and not any(DIM_KEYWORD.get(d, d) in resp for d in feedback_dims):
            errs.append("feedback_response 未提及任何未兑现预测的维度（市值组/持有期/行业）")
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

def cross_check(gen_attack, metrics):
    """换皮交叉核对（程序比对）：生成侧声称的最像经典编号 vs 程序实测的最大相关经典编号。"""
    claimed = ((gen_attack or {}).get("最像的经典") or "").strip()
    actual = (metrics or {}).get("最大相关经典")
    if not claimed.startswith("C") or not actual:
        return "无法比对"
    return "一致" if claimed[:3].upper() == actual.upper() else "不一致"


# ============================================================
# 阶段 A 的文献链：检索 → 筛选 → 全文抓取 → 优化定稿
# 按登记里的检索式查资料，模型据此优化登记五项；优化稿须重新通过
# 登记校验才采用，否则保留初稿；全程尚无回测数字。一个方向只走一次。
# ============================================================
def apply_literature(hyp):
    lit = []
    queries = [q for q in (hyp.get("search_queries") or []) if q][:2]
    if queries:
        seen_titles = set()
        reports = []
        for q in queries:
            for item in search.search(q, limit=5):
                if item["标题"] not in seen_titles:
                    seen_titles.add(item["标题"])
                    lit.append(item)
            reports.append({"检索式": q, "来源报告": search.last_report()})
        lit = lit[:5]
        for i, item in enumerate(lit):
            item["编号"] = f"L{i + 1}"
        trace("文献检索", 方向=hyp["direction"], 假设=hyp["hypothesis"], 查询=queries,
              条数=len(lit), 标题=[m["标题"][:60] for m in lit], 来源报告=reports)
        if not lit:
            trace("文献检索失败", 方向=hyp["direction"], 假设=hyp["hypothesis"],
                  来源报告=reports)
    if lit:
        with_abs = [m for m in lit if m.get("摘要")]
        if not with_abs:
            # 材料不足门：没有一篇带摘要，筛选与优化无从依据，跳过并留痕，不空转。
            hyp["优化说明"] = "材料不足（检索材料均无摘要），未优化"
            trace("文献材料不足", 方向=hyp["direction"], 假设=hyp["hypothesis"],
                  原因="检索材料均无摘要，跳过筛选与优化")
        else:
            # 文献筛选：模型读摘要挑 1 至 2 篇，抓其开放获取全文深读，节选随材料交给优化。
            picks = []
            try:
                picked = agents.pick_readings(hyp, lit)
                by_id = {m["编号"]: m for m in with_abs}
                picks = [by_id[i] for i in (picked.get("picks") or []) if i in by_id][:2]
                trace("文献筛选", 方向=hyp["direction"], 假设=hyp["hypothesis"],
                      选中=[m["编号"] for m in picks],
                      理由=(picked.get("reason") or "")[:300])
            except Exception as e:
                trace("文献筛选失败", 方向=hyp["direction"], 假设=hyp["hypothesis"],
                      错误=str(e))
            for m in picks:
                ft = search.fetch_fulltext(m)
                if ft:
                    m["全文节选"] = ft["节选"]
                    trace("全文抓取", 方向=hyp["direction"], 假设=hyp["hypothesis"],
                          编号=m["编号"], 成功=True, 字数=ft["字数"])
                else:
                    trace("全文抓取", 方向=hyp["direction"], 假设=hyp["hypothesis"],
                          编号=m["编号"], 成功=False)
            try:
                refined = agents.refine_hypothesis(hyp, lit,
                                                   sectors=frozenset(calc.SECTOR_OF.values()))
            except Exception as e:
                refined = None
                hyp["优化说明"] = "检索后优化失败，用初稿"
                trace("假设优化失败", 方向=hyp["direction"], 假设=hyp["hypothesis"],
                      错误=str(e))
            if refined:
                # 假优化硬校验：无引用且无修改（空或仅写“无修改”），等于没有用上任何
                # 检索材料，判优化失败、用初稿，不许以“采纳”名义空转。
                chg = (refined.get("changes") or "").strip()
                if not refined.get("lit_refs") and chg in ("", "无修改"):
                    hyp["优化说明"] = "检索后优化失败，用初稿"
                    trace("假设优化失败", 方向=hyp["direction"], 假设=hyp["hypothesis"],
                          原因="无引用无修改")
                    refined = None
            if refined:
                merged = dict(hyp)
                for k in ("measure", "baseline_formula", "mechanism", "predictions", "falsify"):
                    if refined.get(k):
                        merged[k] = refined[k]
                errs = validate_registration(merged, [], [],
                                             frozenset(calc.SECTOR_OF.values()))
                if not errs:
                    merged["lit_refs"] = refined.get("lit_refs") or []
                    merged["优化说明"] = refined.get("changes") or ""
                    hyp = merged
                    trace("假设优化", 方向=hyp["direction"], 假设=hyp["hypothesis"],
                          采纳=True, 引用=merged["lit_refs"],
                          说明=merged["优化说明"][:200])
                else:
                    trace("假设优化", 方向=hyp["direction"], 假设=hyp["hypothesis"],
                          采纳=False, 原因=errs)

    return hyp, lit

# ============================================================
# 阶段 B 的一轮：第 3 至第 6 步（实现、回测、对抗、讲评）
# 假设已在阶段 A 锁定；revision 非空时为因子修订轮次——按程序给出的
# 修改要求改公式，假设与登记一字不动。
# ============================================================
def process_hypothesis(hyp, wide, classics, cap_complexity, revision=None, lit=None):
    if revision:
        trace("因子修订", 方向=hyp["direction"], 修改要求=revision.get("修改要求"))
    lit = lit or []
    rec = {"方向": hyp["direction"], "机制类别": hyp["category"], "假设": hyp["hypothesis"],
           "登记": {"计算方式": hyp["measure"], "基准公式": hyp["baseline_formula"],
                    "机制": hyp["mechanism"], "条件预测": hyp["predictions"],
                    "否定条件": hyp["falsify"],
                    "文献引用": hyp.get("lit_refs") or [],
                    "优化说明": hyp.get("优化说明", "")},
           "公式": None, "判定数字": None, "预测核对": None, "对抗检验": None,
           "生成侧对抗": None, "检验侧对抗": None, "换皮交叉": None,
           "结论": None, "失效层": None}
    baseline_values = calc.eval_formula(hyp["baseline_formula"], wide)

    # 生成侧对抗审查（模型）：专攻登记内容——是否经典换皮、预测是否注水、机制是否自洽。
    # 只留痕，不参与判定，不给修改方案；攻击记录经已否决摘要回流，成为下一次展开必须回应的输入。
    try:
        rec["生成侧对抗"] = agents.attack_registration(hyp, calc.CLASSIC_FORMULAS, lit=lit)
    except Exception as e:
        trace("生成对抗失败", 方向=hyp["direction"], 假设=hyp["hypothesis"], 错误=str(e))
    trace("生成对抗", 方向=hyp["direction"], 假设=hyp["hypothesis"], 对抗=rec["生成侧对抗"])

    # 第 3 步：写公式 + 程序检查（白名单、复杂度、一致性）；登记锁定，只改公式
    formula, last_err = None, None
    for attempt in range(1, FORMULA_REWRITE_MAX + 2):
        out = agents.write_formula(hyp, last_err, cap=cap_complexity, revision=revision)
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
        # 因子修订轮次：修改要求本就指向公式层构造（窗口、参照系、组合、门控），
        # 公式允许偏离登记基准，一致性不按基准公式对拍（数值照常计算并记账）；
        # 白名单、复杂度、可算性三项检查照常。首版照旧：一致性低于下限打回重写。
        if revision is None and (corr is None or corr < CONSISTENCY_MIN):
            last_err = f"一致性相关 {corr} 低于 {CONSISTENCY_MIN}：公式计算的量与登记不一致"
            trace("公式检查", 方向=hyp["direction"], 假设=hyp["hypothesis"], 第几次=attempt,
                  公式=cand, 一致性相关=corr, 结果="未通过：" + last_err)
            continue
        formula, rec["一致性相关"] = cand, corr
        trace("公式检查", 方向=hyp["direction"], 假设=hyp["hypothesis"], 第几次=attempt,
              公式=cand, 复杂度=calc.complexity(cand), 一致性相关=corr,
              结果="通过" if revision is None else "通过（因子修订轮次，未按基准公式对拍）")
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
    rec["换皮交叉"] = cross_check(rec["生成侧对抗"], metrics)
    trace("换皮交叉", 方向=hyp["direction"], 假设=hyp["hypothesis"],
          声称最像=(rec["生成侧对抗"] or {}).get("最像的经典"),
          实测最大相关=metrics.get("最大相关经典"), 结果=rec["换皮交叉"])

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
             "换皮交叉": rec.get("换皮交叉"),
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
            if ga.get("引用问题") and ga["引用问题"] != "无":
                bits.append(f"引用：{ga['引用问题']}")
            if ra.get("失效解释"):
                bits.append(f"死因：{ra['失效解释']}")
            out.append({"方向": r["方向"], "假设摘要": r["假设"],
                        "结局": "已否决" if r["结论"] == "否决" else "关键预测未兑现",
                        "对抗摘要": "；".join(bits)})
    return out

# ============================================================
# 反馈包（保留部件，已不再接入循环：阶段 A 展开无反馈）：
# 把上次尝试的完整回执结构化喂回展开，
# 让修改有据可依：改了什么、为什么，由展开在 feedback_response 中逐条回应，
# 登记校验把关（见 validate_registration）。训练段数字按既定口径可喂生成侧；
# 修改只能以新尝试出现，同一次尝试内仍不按回测或对抗改登记。
# ============================================================
TERRAIN_PATH = os.path.join(BASE, "..", "hidden_files", "scan_results.csv")
DIM_KEYWORD = {"市值组": "市值", "持有期": "持有期", "行业": "行业"}

def load_terrain():
    """数据地形：扫描探针中已过噪声标尺的条件规律（pass 为真），格式化为短清单。
    行格式：信号编号 + 方案 + 格子 + IC + 三子时段 IC。文件缺失或无过关格子时返回空。"""
    if not os.path.exists(TERRAIN_PATH):
        return []
    out = []
    with open(TERRAIN_PATH, encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if (row.get("pass") or "").strip().lower() != "true":
                continue
            out.append(
                f"{row['signal']} {row['scheme']} {row['cell']} IC {float(row['ic_full']):.3f}"
                f"（三子时段 {float(row['ic_2000_2005']):.3f}/{float(row['ic_2006_2010']):.3f}"
                f"/{float(row['ic_2011_2016']):.3f}）")
    return out

def build_feedback(records, direction, terrain):
    """组装一个方向的结构化反馈包；该方向尚无任何尝试记录时返回 None。
    内容：上次尝试的结论与失效层、最近一次有预测核对的逐条核对（实际分组 IC）、
    生成侧与检验侧对抗意见、该方向全部未兑现预测的维度、数据地形清单。"""
    mine = [r for r in records if r["方向"] == direction]
    if not mine:
        return None
    last = mine[-1]
    with_preds = [r for r in mine if r.get("预测核对")]
    pred_src = with_preds[-1] if with_preds else None
    unfulfilled = sorted({p["dim"] for r in mine for p in (r.get("预测核对") or [])
                          if not p["兑现"]})
    return {
        "上次尝试": {"假设": last["假设"], "结论": last["结论"],
                     "失效层": last.get("失效层"),
                     "无法表达原因": last.get("无法表达原因", "")},
        "预测核对": (pred_src or {}).get("预测核对"),
        "预测核对来源": (pred_src or {}).get("假设"),
        "未兑现维度": unfulfilled,
        "检验侧备忘录": (pred_src or {}).get("检验侧对抗") or last.get("检验侧对抗"),
        "生成侧对抗": last.get("生成侧对抗") or (pred_src or {}).get("生成侧对抗"),
        "数据地形": terrain,
    }

# ============================================================
# 阶段 A 的对抗后修订：生成侧对抗之后，把对抗意见喂给修订调用
#（复用 refine 的五项输出协议），修订稿重过登记校验才采用并锁定；
# 不合格保留对抗前版本。只修订一遍，不循环对抗。
# ============================================================
def revise_after_attack_step(hyp, attack, exp_in, rej_keys, sectors):
    failed = None
    try:
        rev = agents.revise_after_attack(hyp, attack, sectors=sectors)
    except Exception as e:
        rev, failed = None, f"修订调用失败：{e}"
    if not rev:
        reason = failed or "修订无输出"
        trace("对抗后修订", 方向=hyp["direction"], 假设=hyp["hypothesis"], 采纳=False,
              说明=reason)
        trace("对抗后修订未采用", 方向=hyp["direction"], 假设=hyp["hypothesis"],
              原因=reason)
        return hyp
    merged = dict(hyp)
    for k in ("measure", "baseline_formula", "mechanism", "predictions", "falsify"):
        if rev.get(k):
            merged[k] = rev[k]
    errs = validate_registration(merged, exp_in, rej_keys, sectors=sectors)
    if errs:
        trace("对抗后修订", 方向=hyp["direction"], 假设=hyp["hypothesis"], 采纳=False,
              说明=(rev.get("changes") or "")[:200])
        trace("对抗后修订未采用", 方向=hyp["direction"], 假设=hyp["hypothesis"], 原因=errs)
        return hyp
    trace("对抗后修订", 方向=hyp["direction"], 假设=hyp["hypothesis"], 采纳=True,
          说明=(rev.get("changes") or "")[:200])
    return merged

# ============================================================
# 修改要求（程序组装）：阶段 B 每轮未过后，程序按本轮数字与失效类型
# 模板化给出一条修改要求，只许改一类公式层构造（窗口 / 参照系 /
# 组合方式 / 符号与门控），不调模型。要求连同上一版公式、本轮全部
# 数字、逐条预测实际值与检验侧对抗备忘录，一并喂给写公式 agent。
# ============================================================
def build_revision_requirement(rec):
    if rec["结论"] == "无法表达":
        return ("组合方式：上一版未能写出可通过程序检查的公式"
                f"（{rec.get('无法表达原因') or '原因未记'}），"
                "简化构造——减少嵌套与变换层数，优先用单层时序算子与预计算字段"
                "实现登记的计算方式；只改组合方式，不改窗口与参照系。")
    m = rec["判定数字"] or {}
    adv = rec["对抗检验"] or {}
    if adv.get("子时段反例"):
        return (f"窗口：子时段 {'、'.join(adv['子时段反例'])} 的 IC 方向与全期相反且显著，"
                "把构造窗口拉长做平滑，只改窗口长度，不改参照系与组合方式。")
    sym = adv.get("对称检验") or ""
    if "方向反转" in sym:
        return (f"符号与门控：{sym}——信号两端方向不一致，只保留与全期同向一端的门控"
                "（反向一端置零）；只改门控，不改窗口与参照系。")
    for p in rec["预测核对"] or []:
        if p.get("key") and not p["兑现"]:
            dim, a, b = p["dim"], p["a"], p["b"]
            if dim == "持有期":
                return (f"窗口：关键预测（持有期 {a} 日高于 {b} 日）未兑现，"
                        f"实际 {a} 日 IC {p['a值']}、{b} 日 IC {p['b值']}；"
                        "把构造窗口向实际更强的期限调整，只改窗口。")
            return (f"参照系：关键预测（{dim} {a} 高于 {b}）未兑现，"
                    f"实际 {a} 组 IC {p['a值']}、{b} 组 IC {p['b值']}；"
                    "改为行业内相对构造（以 sector_mean 或 rank_sector 为参照），只改参照系。")
    ic = m.get("IC均值")
    if ic is not None and ic < 0:
        return (f"符号与门控：全期 IC {ic} 为负，与登记的方向约定相反；"
                "核对公式符号与门控方向后修正，只改符号与门控。")
    hp = {k: v for k, v in (m.get("各持有期IC") or {}).items() if v is not None}
    if hp:
        best = max(hp, key=hp.get)
        return (f"窗口：全期 IC {ic} 未达门槛，各持有期中 {best} 日期限 IC 最高"
                f"（{hp[best]}），把构造窗口向 {best} 日靠拢，只改窗口。")
    return ("组合方式：换组合方式——以时序均值平滑代替单日点值构造，"
            "只改组合方式，不改窗口与参照系。")

# ============================================================
# 假设锁定 + 因子内循环（唯一驱动模式）
# 阶段 A（每个新方向只走一次）：展开假设 → 文献链（检索、筛选、
# 全文抓取、优化）→ 登记校验 → 生成侧对抗 → 对抗后修订 → 锁定假设。
# 阶段 B（因子循环，总轮次上限 3，含首版）：每轮只重跑写公式 → 程序
# 检查 → 回测与程序检验 → 对抗与讲评；未过则程序组装修改要求（连同
# 检验侧对抗备忘录）喂回写公式 agent 改公式。假设在阶段 B 永不重开。
# 已有账本记录的旧方向不再处理，由 main 跳过。
# ============================================================
def run_fresh_loop(clue, wide, classics, cap_complexity, sectors, stats):
    direction = clue["direction"]
    if stats["done"] >= MAX_TOTAL_ATTEMPTS:
        return
    records = read_jsonl(RECORDS_PATH)
    entries = read_jsonl(EXP_PATH)
    exp_in = retrieve_exp(clue.get("category"), entries) if clue.get("category") else entries[:EXP_LIMIT]
    rej = rejected_summaries(clue.get("category"), records) if clue.get("category") else []
    rej_keys = [r for r in rej] if clue.get("category") else []

    # ---------- 阶段 A：假设只定一次 ----------
    t_attempt = time.time()
    snap_attempt = agents.usage_snapshot()
    hyps = agents.expand_hypotheses(clue, exp_in, rej, sectors=sectors, feedback=None)
    trace("展开候选", 方向=direction, 候选=hyps, 引用经验=[e["编号"] for e in exp_in])
    stats["candidates"] += len(hyps)
    locked, lit = None, []
    for hyp in hyps:
        hyp, hyp_lit = apply_literature(hyp)
        errs = validate_registration(hyp, exp_in, rej_keys, sectors=sectors)
        if errs:
            stats["rejected"] += 1
            trace("拒登", 方向=direction, 假设=hyp.get("hypothesis"), 原因=errs)
            print(f"假设拒登：{errs}")
            continue
        hyp["direction"] = direction
        attack = None
        try:
            attack = agents.attack_registration(hyp, calc.CLASSIC_FORMULAS, lit=hyp_lit)
        except Exception as e:
            trace("生成对抗失败", 方向=direction, 假设=hyp["hypothesis"], 错误=str(e))
        trace("生成对抗", 方向=direction, 假设=hyp["hypothesis"], 对抗=attack)
        if attack:
            hyp = revise_after_attack_step(hyp, attack, exp_in, rej_keys, sectors)
        locked, lit = hyp, hyp_lit
        trace("假设锁定", 方向=direction, 假设=hyp["hypothesis"])
        break
    if locked is None:
        trace("循环停止", 方向=direction, 原因="阶段 A 无合格登记")
        print(f"方向「{direction}」阶段 A 无合格登记，停止")
        return

    # ---------- 阶段 B：因子内循环 ----------
    revision = None
    prev_factor_values, prev_ic = None, None
    round_no = 0
    for round_no in range(1, 3 + 1):   # 总轮次上限 3，含首版
        if round_no > 1:
            if stats["done"] >= MAX_TOTAL_ATTEMPTS:
                return
            t_attempt = time.time()
            snap_attempt = agents.usage_snapshot()
        result = process_hypothesis(locked, wide, classics, cap_complexity,
                                    revision=revision, lit=lit)
        if isinstance(result, tuple):
            rec, review, status, _ = result
        else:
            rec, review, status = result, None, "已否决"
        cost = stamp_cost(rec, snap_attempt, t_attempt)
        trace("成本", 方向=direction, 假设=rec["假设"], **cost)
        rec["工具版本"] = calc.TOOLING_VERSION
        rec["轮次"] = round_no
        rec["假设锁定文本"] = locked["hypothesis"] if round_no == 1 else ""
        rec["修订类型"] = "无" if round_no == 1 else "因子"
        rec["修改要求"] = "" if revision is None else revision["修改要求"]
        rec["修改依据"] = ("" if revision is None else
                          "程序按数字组装的修改要求 + 检验侧对抗备忘录")
        append_jsonl(RECORDS_PATH, rec)
        save_experience(rec, review, status)
        stats["done"] += 1
        if rec.get("判定数字"):
            stats["backtested"] += 1
        if rec["结论"] == "无法表达":
            stats["inexpressible"] += 1
        stats["passed"] += 1 if rec["结论"] == "通过" else 0
        for p in (rec["预测核对"] or []):
            stats["pred_total"] += 1
            stats["pred_hit"] += 1 if p["兑现"] else 0
        print(f"方向「{direction}」第 {round_no} 轮：{locked['hypothesis'][:40]} → {rec['结论']}"
              + (f"（失效层 {rec['失效层']}）" if rec["失效层"] else ""))
        if rec["结论"] == "通过":
            trace("循环停止", 方向=direction, 轮次=round_no, 原因="本轮通过")
            return
        cur_values = calc.eval_formula(rec["公式"], wide) if rec.get("公式") else None
        cur_ic = (rec.get("判定数字") or {}).get("IC均值")
        if (round_no >= 2 and cur_values is not None and prev_factor_values is not None):
            corr = calc.consistency_corr(cur_values, prev_factor_values)
            improved = (cur_ic is not None and prev_ic is not None and cur_ic > prev_ic)
            if corr is not None and corr >= CONSISTENCY_MIN and not improved:
                trace("循环停止", 方向=direction, 轮次=round_no,
                      原因=f"无改进：新公式与上一轮因子一致性相关 {corr:.4f}，IC 未改善")
                print(f"方向「{direction}」第 {round_no} 轮无改进，循环停止")
                return
        prev_factor_values, prev_ic = cur_values, cur_ic
        if round_no == 3:
            break
        if stats["done"] >= MAX_TOTAL_ATTEMPTS:
            return
        revision = {"修改要求": build_revision_requirement(rec),
                    "上一版公式": rec.get("公式"),
                    "判定数字": rec.get("判定数字"),
                    "预测核对": rec.get("预测核对"),
                    "对抗备忘录": rec.get("检验侧对抗")}
    trace("循环停止", 方向=direction, 轮次=round_no, 原因="轮次达上限")

def main():
    t_start = time.time()
    snap0 = agents.usage_snapshot()
    wide = calc.load_wide()
    classics = calc.load_classics(wide)
    cap_complexity = COMPLEXITY_CAP
    sectors = set(calc.SECTOR_OF.values())
    print(f"复杂度上限 {cap_complexity}；已加载训练段数据")
    trace("实验开始", 初始线索数=len(read_jsonl(CLUES_PATH)), 复杂度上限=cap_complexity,
          总尝试上限=MAX_TOTAL_ATTEMPTS)
    stats = {"done": 0, "passed": 0, "pred_total": 0, "pred_hit": 0,
             "candidates": 0, "rejected": 0, "backtested": 0, "inexpressible": 0}
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
        # 新假设循环只处理尚无账本记录的新方向；有记录的旧方向跳过不处理。
        if any(r["方向"] == clue["direction"] for r in read_jsonl(RECORDS_PATH)):
            trace("跳过旧方向", 方向=clue["direction"], 原因="已有账本记录，不再处理")
            print(f"方向「{clue['direction']}」已有账本记录，跳过")
        else:
            run_fresh_loop(clue, wide, classics, cap_complexity, sectors, stats)
        processed.add(clue["direction"])

    tot = agents.usage_since(snap0)
    calls = tot["calls"]
    elapsed = round(time.time() - t_start, 1)
    total_cost = est_cost(tot["in"], tot["out"])
    done, passed = stats["done"], stats["passed"]
    bt_rate = (stats["backtested"] / done) if done else 0
    ix_rate = (stats["inexpressible"] / done) if done else 0
    rj_rate = (stats["rejected"] / stats["candidates"]) if stats["candidates"] else 0
    trace("实验结束", 完成尝试=done, 通过=passed, 模型调用=calls, 输入token=tot["in"],
          输出token=tot["out"], 估算成本USD=total_cost, 总用时秒=elapsed, 停止原因=stop_reason,
          完整回测率=round(bt_rate, 3), 无法表达率=round(ix_rate, 3), 拒登率=round(rj_rate, 3))
    print(f"\n本轮完成尝试 {done} 条，通过 {passed} 条；模型调用 {calls} 次；"
          f"用时 {elapsed:.0f} 秒；估算成本 ${total_cost:.3f}"
          f"（输入 {tot['in']} / 输出 {tot['out']} token，牌价估算）；停止原因：{stop_reason}")
    if done:
        print(f"首版存活率 {passed / done:.2f}；预测命中率 "
              f"{(stats['pred_hit'] / stats['pred_total']) if stats['pred_total'] else 0:.2f}；"
              f"单位算力产出 {passed / calls * 1000 if calls else 0:.1f} 个/千次调用")
        print(f"完整回测率 {bt_rate:.2f}；无法表达率 {ix_rate:.2f}；拒登率 {rj_rate:.2f}；"
              f"单位算力完整回测 {stats['backtested'] / calls * 1000 if calls else 0:.1f} 次/千次调用")

if __name__ == "__main__":
    main()
