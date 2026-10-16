"""
第 03 课作业：Agent 主循环（ReAct）
=====================================

目标：写出 Agent 的最小内核 —— 让模型自己决定什么时候停。

规则：
  1. 只准用标准库
  2. execute_tool_safely 绝不抛异常（失败转成 JSON 错误字符串）
  3. run_agent 必须有出口，不能静默挂死
  4. 四个 TODO 全部填完

讲义：../讲义/03-Agent主循环.md
验收：python ../验收/check_hw03.py
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request

# ============================================================
# 样板代码：环境 + HTTP + 工具实现（都已写好）
# ============================================================

_ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env")


def _load_env(path: str) -> dict:
    env = {}
    if not os.path.exists(path):
        return env
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


_ENV = _load_env(_ENV_PATH)

API_KEY = _ENV.get("ZHIPU_API_KEY", "")
API_URL = _ENV.get("ZHIPU_BASE", "")
DEFAULT_MODEL = _ENV.get("ZHIPU_MODEL", "glm-4-air")


class ChatAPIError(Exception):
    def __init__(self, status: int, body: str):
        self.status = status
        self.body = body
        super().__init__(f"Chat API 调用失败 HTTP {status}: {body}")


class UnknownToolError(Exception):
    """模型请求了未注册的工具。"""


def chat(messages: list, tools: list = None, model: str = None,
         max_tokens: int = 600, temperature: float = 0.7) -> dict:
    """发一次请求（已写好，02 课同款）。"""
    body = {
        "model": model or DEFAULT_MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if tools:
        body["tools"] = tools
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        API_URL, data=data,
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise ChatAPIError(e.code, e.read().decode("utf-8", errors="replace")) from e
    except urllib.error.URLError as e:
        raise ChatAPIError(0, f"网络层失败: {e.reason}") from e


# ------------------------------------------------------------
# 工具实现（已写好，供 execute_tool_safely 调用）
# ------------------------------------------------------------
_WEATHER = {
    "北京": {"city": "北京", "temp": 18, "condition": "晴", "aqi": 55},
    "上海": {"city": "上海", "temp": 22, "condition": "多云", "aqi": 42},
    "南宁": {"city": "南宁", "temp": 28, "condition": "小雨", "aqi": 38},
}

# 故意保留一个"会失败的"城市，用于测试失败恢复
_FAIL_CITY = "火星"


def _get_weather(city: str) -> dict:
    if city == _FAIL_CITY:
        raise RuntimeError(f"无法获取「{city}」的天气数据（该城市不在服务范围内）")
    data = _WEATHER.get(city)
    if data is None:
        return {"error": f"未知城市: {city}"}
    return data


def _get_time(city: str) -> dict:
    return {"city": city, "time": time.strftime("%Y-%m-%d %H:%M:%S")}


TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "查询指定城市的实时天气，返回温度、天气状况和空气质量。仅当用户询问天气时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "城市名称，例如：北京、上海、南宁"}
                },
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_time",
            "description": "查询指定城市的当前日期和时间。仅当用户询问时间、日期时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "城市名称"}
                },
                "required": ["city"],
            },
        },
    },
]


def _dispatch(name: str, arguments: dict) -> dict:
    """按名字分发到具体工具。未知工具抛 UnknownToolError。"""
    if name == "get_weather":
        return _get_weather((arguments or {}).get("city", ""))
    if name == "get_time":
        return _get_time((arguments or {}).get("city", ""))
    raise UnknownToolError(f"未注册的工具: {name}")


# ============================================================
# TODO 1 —— 安全执行工具（绝不抛异常）
# ============================================================
def execute_tool_safely(name: str, arguments: dict) -> str:
    """执行工具，**任何异常都转成 JSON 错误字符串**，绝不向外抛。

    要求：
      1. 成功 → 返回 json.dumps(结果, ensure_ascii=False)
      2. 任何异常（含 UnknownToolError、RuntimeError）→ 返回
         json.dumps({"error": "<可读的错误说明>"}, ensure_ascii=False)
      3. **绝对不能让异常逃出去** —— 这是本课的核心护栏

    为什么这样做（讲义第四节 · 护栏 2）：
      把失败当作"观察结果"喂回给模型，模型才有机会自救
      （换参数、换工具、或直接告诉用户失败了）。
      抛异常 = 模型永远没有机会自救。

    提示：用 try/except Exception 兜住一切；错误信息里带上工具名更好调试。

    讲义第四节 · 护栏 2
    """
    # TODO 1: 在这里写你的实现
    raise NotImplementedError("TODO 1 还没写")


# ============================================================
# TODO 2 —— 判断循环出口
# ============================================================
def needs_more_tools(response: dict) -> bool:
    """模型是否还想调工具？True=继续循环，False=可以结束了。

    要求：
      1. 取 response["choices"][0]["message"]
      2. message 里有非空 tool_calls → 返回 True
      3. 否则返回 False
      4. 响应结构异常（缺键、choices 为空）时，**返回 False**（保守收口）

    为什么用 tool_calls 而不是 finish_reason（讲义第三节）：
      finish_reason 有些厂商取值不规范；tool_calls 是结构化的，更可靠。

    讲义第三节 · 出口条件
    """
    # TODO 2: 在这里写你的实现
    raise NotImplementedError("TODO 2 还没写")


# ============================================================
# TODO 3 —— 记录一轮的 trace
# ============================================================
def build_trace_entry(turn: int, msg: dict, results: list) -> dict:
    """把一轮的过程记成 trace 条目。

    返回：
        {
            "turn": int,
            "content": str,          # 模型这轮的思考（可能为空串）
            "calls": [               # 这轮调了哪些工具
                {"name":..., "arguments": dict, "result_preview": str},
                ...
            ],
        }

    为什么要有 trace（讲义第七节第 7 项）：
      Agent 出错时，光看最终答案是没法定位问题的 ——
      你不知道它是"没调工具"还是"调错了工具"还是"调对了但没用好结果"。
      trace 让每一步都可见。面试时这也是能拿出来的证据。

    提示：result_preview 取结果字符串前 80 字即可，别把整个结果塞进去。
    """
    # TODO 3: 在这里写你的实现
    raise NotImplementedError("TODO 3 还没写")


# ============================================================
# TODO 4 —— 主循环
# ============================================================
def run_agent(question: str, max_turns: int = 8, verbose: bool = True) -> dict:
    """跑 Agent 主循环。

    流程（讲义第三节）：
      1. messages = [{"role":"user","content":question}]
      2. 循环 最多 max_turns 次：
         a. resp = chat(messages, tools=TOOLS_SCHEMA)
         b. msg = resp["choices"][0]["message"]
         c. 如果 not needs_more_tools(resp) → 结束，stopped_reason="answered"
         d. 把 msg **原样**塞回 messages（含 content 与 tool_calls，一个都不能丢！）
         e. 对 msg["tool_calls"] 里每个调用：
              - 解析 arguments（它是 JSON 字符串，要 json.loads）
              - result = execute_tool_safely(name, args)
              - messages.append({"role":"tool","tool_call_id":id,"content":result})
              - 记进本轮 results
         f. 把本轮记进 trace
      3. 循环用尽 → stopped_reason="max_turns"

    返回：
        {
            "answer": str,          # 最终答案（max_turns 时给明确提示，不能是 None）
            "turns": int,           # 实际跑了几轮
            "tool_calls": list,     # 所有工具调用（累加，元素含 name/arguments）
            "trace": list,          # 每轮的 build_trace_entry 结果
            "stopped_reason": str,  # "answered" | "max_turns"
        }

    ⚠️ 三个易错点（讲义第三节）：
      - 出口条件用 needs_more_tools，不是 finish_reason
      - assistant 那条要**原样**塞回，content 为 None 也要带 tool_calls
      - arguments 是 **JSON 字符串**，必须 json.loads 成 dict

    ⚠️ 必须有出口：达到 max_turns 时返回明确原因，绝不静默挂死（讲义第四节 · 护栏 1）
    """
    # TODO 4: 在这里写你的实现
    raise NotImplementedError("TODO 4 还没写")


# ============================================================
# 自测
# ============================================================
if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")

    print("=" * 70)
    print("实验 A：单步问题（应 1-2 轮结束）")
    print("=" * 70)
    r = run_agent("北京现在天气怎么样？")
    print(f"\n答案：{r['answer'][:120]}")
    print(f"轮次={r['turns']}  工具调用={len(r['tool_calls'])}  "
          f"结束原因={r['stopped_reason']}")

    print()
    print("=" * 70)
    print("实验 B：多步问题（需要多轮工具）")
    print("=" * 70)
    r2 = run_agent("北京和上海现在哪个更适合户外跑步？请比较两地的天气。")
    print(f"\n答案：{r2['answer'][:200]}")
    print(f"轮次={r2['turns']}  工具调用={len(r2['tool_calls'])}  "
          f"结束原因={r2['stopped_reason']}")

    print()
    print("=" * 70)
    print("实验 C：工具会失败的问题（测试失败恢复）")
    print("=" * 70)
    r3 = run_agent("火星现在的天气怎么样？")
    print(f"\n答案：{r3['answer'][:200]}")
    print(f"轮次={r3['turns']}  结束原因={r3['stopped_reason']}")
    print("\n>>> 注意：工具报错了，但 Agent 没有崩溃 —— 它拿到了错误信息并给出了回复。")
    print(">>> 这就是「失败也要回灌」的价值。")

    print()
    print("=" * 70)
    print("实验 D：对照 —— max_turns=1（循环被限制死）")
    print("=" * 70)
    r4 = run_agent("北京和上海现在哪个更适合户外跑步？请比较两地的天气。", max_turns=1)
    print(f"\n答案：{r4['answer'][:150]}")
    print(f"轮次={r4['turns']}  结束原因={r4['stopped_reason']}")
    print("\n>>> 对比实验 B 和 D：同一问题，轮次上限不同，结果质量天差地别。")
    print(">>> 这就是主循环的意义。")
