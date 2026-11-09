# hypothesis_agent.py — 假设 Agent（想）
# 职责：依据数据说明与已试假设清单，成批提出假设。
# 模型只填量、经济逻辑、机制类别三项；假设句由程序按固定句式拼装。
# 本文件不计算数字；去重由程序按拼装后的假设句文本完全相同执行。

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

# ============================================================
# 材料：数据说明与机制类别（与 spec 一致，是给模型的输入）
# ============================================================
DATA_DOC = """数据为日频行情，覆盖 2000-2016 年美股（含已退市股票）。
可用字段：open、high、low、close（均为复权价）、volume（成交股数）、mktcap（总市值，千美元）、mktret（当日市场收益率，全体股票相同）。
量可以是全市场口径，也可以是行业内相对口径（每只股票有 GICS 行业分类），还可以相对市场基准（如与市场收益的相关、相对市场的强弱）；一段时间内的频率、占比类量同样可表达（如上涨天数占比）。
假设必须能用上述字段表达，并能通过历史数据检验。"""

MECHANISMS = ["反转", "动量", "量价", "波动率", "流动性", "日内隔夜", "规模", "其他"]

# 已占满的经典机制：全部条目源于已发表文献（公式与出处见 classic-factor-inspiration-2026-11-09.md）
# 用途是划界不是引路：只给机制句作地图，标出已有成熟因子的方向，要求在其之外构造。
# 不给公式——给公式会被模型照抄（2026-11-09 验收跑实测：8/14 条与经典相关 ≥ 0.86）。
# 公式在程序一侧（calc.CLASSIC_FORMULAS），仅作相关性参照，假设 Agent 不接触。
MECHANISM_NOTES = """短期过度反应后均值回复
多年期过度反应在随后数年反转
过去的赢家在随后数月继续跑赢（信息扩散慢、反应不足）
接近历史高点的股票被锚定低估、利好反应不足
涨幅由许多小步累积而成时反应不足、趋势更持久；由少数大跳构成时反应迅速
异常放量是注意力冲击，提高股票可见性与后续需求
低换手赢家的动量寿命更长，高换手赢家反转更快
高波动股票被彩票偏好与套利限制压价
出现过极端单日大涨的股票被彩票偏好高估
受杠杆约束的资金抢购高 Beta，使高 Beta 被高估、低 Beta 被低估
单位成交额的价格冲击越大、流动性越差，预期收益越高
换手低的股票流动性差且被忽视，预期收益更高
隔夜分量携带持续的信息流；隔夜与日内是两类投资者的拉锯，各自时段内延续、跨时段反转
日内涨幅多由日内追价构成，对后续收益形成反向压力
小市值股票被忽视且流动性差，平均收益更高
个股收益在相同日历月份跨年重复出现"""

# ============================================================
# 调用模型：DeepSeek 接口（OpenAI 兼容），key 从环境变量读
# ============================================================
def call_model(messages):
    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        raise RuntimeError("未设置环境变量 DEEPSEEK_API_KEY，无法调用模型")
    body = json.dumps({
        "model": os.environ.get("DEEPSEEK_MODEL", "deepseek-chat"),
        "messages": messages,
        "temperature": 0.9,
    }).encode("utf-8")
    # 网络瞬时故障（断连、超时）自动重试；临时重定向在单次尝试内跟随到底
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {key}"}
    url = "https://api.deepseek.com/chat/completions"
    last_err = None
    for wait in (0, 5, 15, 30, 60):
        if wait:
            time.sleep(wait)
        try:
            current = url
            for _hop in range(6):
                req = urllib.request.Request(current, data=body, headers=headers)
                try:
                    with urllib.request.urlopen(req, timeout=300) as resp:
                        data = json.loads(resp.read().decode("utf-8"))
                    return data["choices"][0]["message"]["content"]
                except urllib.error.HTTPError as e:
                    if e.code in (301, 302, 307, 308) and e.headers.get("Location"):
                        current = urllib.parse.urljoin(current, e.headers["Location"])
                        continue
                    raise
            raise RuntimeError("重定向次数过多")
        except Exception as e:
            last_err = e
    raise RuntimeError(f"模型接口调用失败（已重试）：{last_err}")

def _extract_json_array(text):
    start = text.find("[")
    end = text.rfind("]")
    if start < 0 or end <= start:
        raise ValueError("输出中找不到 JSON 数组")
    return json.loads(text[start:end + 1])

# ============================================================
# 提出：一批假设，模型填量、经济逻辑、机制类别，程序拼装假设句
# ============================================================
SYSTEM = """你是一名因子研究员，任务是成批提出可用历史数据检验的因子假设。
只输出一个 JSON 数组，不要任何其他文字。数组每条含三项：
{"quantity": "量", "logic": "经济逻辑", "mechanism": "机制类别"}
mechanism 只能取给定清单中的一个。
quantity 是已定向的名词短语，带回望窗口（如“过去 20 日累计收益”）：它必须让“该量越大的股票，未来收益越高”成立；方向写进量本身，如反转类写“过去 20 日累计收益的相反数”。quantity 只写量本身，不写未来期限、分组或检验方式——那些由程序统一决定。"""

def propose(tried, batch=8, format_retries=2):
    """tried 为已试假设内容列表。返回假设字典列表（已去重、已校验）。
    模型输出格式重试达上限仍不合要求时抛 RuntimeError（本轮应停止）。"""
    tried_text = "\n".join(f"- {t}" for t in tried) if tried else "（无）"
    user = f"""{DATA_DOC}

机制类别清单：{'、'.join(MECHANISMS)}

已占满的经典机制（只有机制，没有公式；这张地图只用来划界——不要提与这些机制的标准构造相近的量，去地图之外构造：换信息来源、换参照对象、换组合方式）：
{MECHANISM_NOTES}

已试假设清单（不得重复提出）：
{tried_text}

请提出 {batch} 条新假设。"""
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]
    last_err = None
    for _ in range(format_retries + 1):
        text = call_model(messages)
        try:
            items = _extract_json_array(text)
            break
        except (ValueError, json.JSONDecodeError) as e:
            last_err = e
            messages = messages + [
                {"role": "assistant", "content": text},
                {"role": "user", "content": f"上次输出不是合法的 JSON 数组（{e}）。请只输出一个 JSON 数组，不要任何其他文字。"},
            ]
    else:
        raise RuntimeError(f"模型输出格式重试达上限：{last_err}")

    seen = set(tried)
    out = []
    for it in items:
        if not isinstance(it, dict):
            continue
        qty, logic, mech = it.get("quantity"), it.get("logic"), it.get("mechanism")
        if not (isinstance(qty, str) and qty.strip()):
            continue
        if not (isinstance(logic, str) and logic.strip()):
            continue
        if mech not in MECHANISMS:
            continue
        hyp = f"{qty.strip()}越大的股票，未来收益越高"
        if hyp in seen:
            continue
        seen.add(hyp)
        out.append({"hypothesis": hyp, "quantity": qty.strip(), "logic": logic, "mechanism": mech})
    return out

# ============================================================
# 自检（块三验收）：直接运行本文件时执行
# ============================================================
if __name__ == "__main__":
    try:
        batch = propose(["过去 5 日跌幅越大的股票，未来收益越高"], batch=8)
        print(f"提出 {len(batch)} 条：")
        for b in batch:
            print("-", b["mechanism"], "|", b["hypothesis"])
    except RuntimeError as e:
        print("无法执行真实模型验收：", e)
