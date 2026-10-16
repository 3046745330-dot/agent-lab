"""
第 02 课作业：Function Calling 原始协议
==========================================

目标：不借助任何 SDK，手写 tools 声明、解析 tool_calls、回传执行结果。

规则：
  1. 只准用标准库：json / os / urllib.request / urllib.error
  2. 必须真的发 HTTP 请求，不许 mock、不许写死假数据
  3. 三个 TODO 全部填完

讲义：../讲义/02-FunctionCalling.md
验收：python ../验收/check_hw02.py
"""

import json
import os
import urllib.error
import urllib.request

# ============================================================
# 样板代码（已替你写好）：.env 读取 + 两个假工具的实现
# ============================================================

_ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env")


def _load_env(path: str) -> dict:
    env = {}
    if not os.path.exists(path):
        return env
    with open(path, "r", encoding="utf-8") as f:
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
DEFAULT_MODEL = _ENV.get("ZHIPU_MODEL", "glm-4-flash")


# ------------------------------------------------------------
# 两个假工具的"后端数据"。
# 注意：这是故意的假数据 —— 本课学的是协议，不是接真实天气 API。
# ------------------------------------------------------------
_WEATHER_DB = {
    "北京": {"city": "北京", "temp": 18, "unit": "celsius", "condition": "晴", "humidity": 40},
    "上海": {"city": "上海", "temp": 22, "unit": "celsius", "condition": "多云", "humidity": 65},
    "南宁": {"city": "南宁", "temp": 28, "unit": "celsius", "condition": "小雨", "humidity": 80},
}

_TIME_DB = {
    "北京": "2026-10-16 14:30:00",
    "上海": "2026-10-16 14:30:00",
    "南宁": "2026-10-16 14:30:00",
}


# ============================================================
# 异常类（已写好，你要在 TODO 里用它们）
# ============================================================
class ChatAPIError(Exception):
    """HTTP 层失败。"""

    def __init__(self, status: int, body: str):
        self.status = status
        self.body = body
        super().__init__(f"Chat API 调用失败 HTTP {status}: {body}")


class ToolArgumentError(Exception):
    """模型给的 arguments 不是合法 JSON，或缺少必填参数。"""


class UnknownToolError(Exception):
    """模型请求了一个没注册的工具名。"""


# ============================================================
# 底层 HTTP（从 00 课搬过来，已替你写好，不用重写）
# ============================================================
def chat(messages: list, tools: list = None, model: str = None,
         max_tokens: int = 200, temperature: float = 0.7) -> dict:
    """发一次请求。tools 传 None 时不带 tools 字段。

    ⚠️ 注意这个签名里的 tools 参数 —— 第 8 项验收就是靠它做对照实验的。
    """
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
        API_URL,
        data=data,
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        raise ChatAPIError(status=e.code, body=e.read().decode("utf-8", errors="replace")) from e
    except urllib.error.URLError as e:
        raise ChatAPIError(status=0, body=f"网络层失败: {e.reason}") from e
    return json.loads(raw)


# ============================================================
# TODO 1 —— 声明工具
# ============================================================
def build_tools_schema() -> list:
    """返回 tools 数组，包含两个工具：get_weather 和 get_time。

    每个工具的格式：
        {
          "type": "function",
          "function": {
            "name": "工具名",
            "description": "给模型看的说明（关键！写清楚什么时候用）",
            "parameters": {
              "type": "object",
              "properties": {
                "参数名": {"type": "string", "description": "参数说明"}
              },
              "required": ["必填参数名"]
            }
          }
        }

    要求：
      - get_weather：参数 city（必填），返回该城市天气
      - get_time：参数 city（必填），返回该城市当前时间
      - **description 必须写得足够具体**，让模型知道什么时候该用这个工具
        （验收会检查 description 长度 ≥ 10 字，且不能是空话）

    讲义第二节 2.1。
    """
    # TODO 1: 在这里写你的实现
    raise NotImplementedError("TODO 1 还没写")


# ============================================================
# TODO 2 —— 解析模型返回的工具调用
# ============================================================
def parse_tool_calls(response: dict) -> list:
    """从响应里提取工具调用，返回统一格式的列表：

        [{"id": "call_abc", "name": "get_weather", "arguments": {"city": "北京"}}, ...]

    要求：
      1. 如果响应里没有 tool_calls（比如 finish_reason="stop"），返回 **空列表**
      2. arguments 是 **JSON 字符串**，必须 json.loads 成 dict
         —— 这是本课最大的坑，直接当 dict 用会 TypeError
      3. 如果 arguments 不是合法 JSON → 抛 ToolArgumentError
      4. 如果某个调用缺 name → 抛 ToolArgumentError
      5. **必须遍历整个 tool_calls 数组**（模型可能一次要求调多个工具，
         只取 [0] 是错的）

    讲义第二节 2.2 + 第四节坑 1、坑 4。
    """
    # TODO 2: 在这里写你的实现
    raise NotImplementedError("TODO 2 还没写")


# ============================================================
# TODO 3 —— 执行工具
# ============================================================
def execute_tool(name: str, arguments: dict) -> str:
    """执行工具，返回**结果的 JSON 字符串**。

    已注册的工具：
      - "get_weather"：从 _WEATHER_DB 查。city 不在库里时返回
        {"error": "未知城市: xxx"} 的 JSON 字符串（不抛异常）
      - "get_time"：从 _TIME_DB 查，同样处理未知城市

    要求：
      1. 未注册的工具名 → 抛 UnknownToolError
      2. 返回值必须是 **JSON 字符串**（不是 dict）
         —— 因为回传给模型时 content 字段要求字符串
      3. 用 json.dumps(..., ensure_ascii=False) 保证中文不被转义成 \\uXXXX

    讲义第二节 2.3。
    """
    # TODO 3: 在这里写你的实现
    raise NotImplementedError("TODO 3 还没写")


# ============================================================
# 工具循环（已替你写好，填完 TODO 后可直接跑）
# ============================================================
def run_tool_loop(question: str, use_tools: bool = True, verbose: bool = True) -> dict:
    """跑一轮完整的工具调用回路，返回 {"answer": str, "tool_calls": list, "rounds": int}。

    流程：问 → 模型要求调工具 → 本地执行 → 回传 → 模型给最终答案
    """
    messages = [{"role": "user", "content": question}]
    tools = build_tools_schema() if use_tools else None
    all_calls = []
    rounds = 0

    for _ in range(5):  # 最多 5 轮，防止死循环
        rounds += 1
        resp = chat(messages, tools=tools)
        choice = resp["choices"][0]
        msg = choice["message"]
        finish = choice.get("finish_reason")

        if verbose:
            print(f"  [第 {rounds} 轮] finish_reason={finish}")

        if finish != "tool_calls":
            return {"answer": msg.get("content") or "", "tool_calls": all_calls, "rounds": rounds}

        calls = parse_tool_calls(resp)
        all_calls.extend(calls)

        # 把 assistant 这条（含 tool_calls）原样塞回历史 —— 必须塞，否则模型不知道上下文
        messages.append({
            "role": "assistant",
            "content": msg.get("content"),
            "tool_calls": msg["tool_calls"],
        })

        for c in calls:
            if verbose:
                print(f"           → 调用 {c['name']}({c['arguments']})")
            result = execute_tool(c["name"], c["arguments"])
            if verbose:
                print(f"           ← 返回 {result}")
            messages.append({
                "role": "tool",
                "tool_call_id": c["id"],   # ⚠️ 必须配对
                "content": result,
            })

    return {"answer": "(超过 5 轮未收敛)", "tool_calls": all_calls, "rounds": rounds}


# ============================================================
# 自测
# ============================================================
if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")

    print("=" * 66)
    print("实验 A：带 tools 字段，问天气")
    print("=" * 66)
    r = run_tool_loop("北京今天天气怎么样？")
    print(f"\n最终回答：{r['answer']}")
    print(f"调用了 {len(r['tool_calls'])} 次工具，共 {r['rounds']} 轮")

    print()
    print("=" * 66)
    print("实验 B（对照组）：不传 tools 字段，问同样的问题")
    print("=" * 66)
    r2 = run_tool_loop("北京今天天气怎么样？", use_tools=False)
    print(f"\n最终回答：{r2['answer']}")
    print(f"调用了 {len(r2['tool_calls'])} 次工具，共 {r2['rounds']} 轮")

    print()
    print(">>> 对比两个实验的 tool_calls 数量。")
    print(">>> 实验 A 会调工具，实验 B 不会 —— 尽管问题一模一样、提示词一模一样。")
    print(">>> 这就是本课的核心结论。")
