"""
第 03 课 参考实现
==================

⚠ 规则：卡住 20 分钟以上才看这个。看完关掉，自己重写一遍。

对照点（本课全部知识点）：
  - execute_tool_safely: try/except Exception 兜住一切，错误转 JSON
  - needs_more_tools:    判断 tool_calls，异常时保守返回 False
  - build_trace_entry:   每轮可见（调试 + 面试证据）
  - run_agent:           原样回灌 assistant、JSON 解析 arguments、
                         max_turns 有明确出口
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request

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
    pass


def chat(messages: list, tools: list = None, model: str = None,
         max_tokens: int = 600, temperature: float = 0.7) -> dict:
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


_WEATHER = {
    "北京": {"city": "北京", "temp": 18, "condition": "晴", "aqi": 55},
    "上海": {"city": "上海", "temp": 22, "condition": "多云", "aqi": 42},
    "南宁": {"city": "南宁", "temp": 28, "condition": "小雨", "aqi": 38},
}
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
                "properties": {"city": {"type": "string", "description": "城市名称"}},
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
                "properties": {"city": {"type": "string", "description": "城市名称"}},
                "required": ["city"],
            },
        },
    },
]


def _dispatch(name: str, arguments: dict) -> dict:
    if name == "get_weather":
        return _get_weather((arguments or {}).get("city", ""))
    if name == "get_time":
        return _get_time((arguments or {}).get("city", ""))
    raise UnknownToolError(f"未注册的工具: {name}")


# ---------- TODO 1 ----------
def execute_tool_safely(name: str, arguments: dict) -> str:
    try:
        result = _dispatch(name, arguments)
        return json.dumps(result, ensure_ascii=False)
    except UnknownToolError as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)
    except Exception as e:
        # 兜住一切：工具内部抛的任何异常都变成"观察结果"
        return json.dumps(
            {"error": f"工具 {name} 执行失败: {type(e).__name__}: {e}"},
            ensure_ascii=False,
        )


# ---------- TODO 2 ----------
def needs_more_tools(response: dict) -> bool:
    try:
        choices = response.get("choices") or []
        if not choices:
            return False
        msg = choices[0].get("message") or {}
        calls = msg.get("tool_calls")
        return bool(calls)
    except Exception:
        return False          # 结构异常时保守收口


# ---------- TODO 3 ----------
def build_trace_entry(turn: int, msg: dict, results: list) -> dict:
    calls = []
    for r in results:
        preview = str(r.get("result", ""))[:80]
        calls.append({
            "name": r.get("name", ""),
            "arguments": r.get("arguments", {}),
            "result_preview": preview,
        })
    return {
        "turn": turn,
        "content": (msg.get("content") or "").strip(),
        "calls": calls,
    }


# ---------- TODO 4 ----------
def run_agent(question: str, max_turns: int = 8, verbose: bool = True) -> dict:
    messages = [{"role": "user", "content": question}]
    all_calls = []
    trace = []

    for turn in range(1, max_turns + 1):
        resp = chat(messages, tools=TOOLS_SCHEMA)
        msg = resp["choices"][0]["message"]

        # 出口：不再需要工具
        if not needs_more_tools(resp):
            if verbose:
                print(f"  [第 {turn} 轮] 模型给出最终答案，结束")
            content = (msg.get("content") or "").strip()
            return {
                "answer": content or "(模型没有返回内容)",
                "turns": turn,
                "tool_calls": all_calls,
                "trace": trace,
                "stopped_reason": "answered",
            }

        if verbose:
            print(f"  [第 {turn} 轮] 模型请求调用 {len(msg['tool_calls'])} 个工具")

        # 关键：原样塞回 assistant（含 content 与 tool_calls）
        messages.append({
            "role": "assistant",
            "content": msg.get("content"),
            "tool_calls": msg["tool_calls"],
        })

        results = []
        for call in msg["tool_calls"]:
            fn = call.get("function") or {}
            name = fn.get("name", "")
            raw_args = fn.get("arguments")
            # arguments 是 JSON 字符串
            try:
                args = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
            except (json.JSONDecodeError, TypeError):
                args = {}
            if not isinstance(args, dict):
                args = {}

            result = execute_tool_safely(name, args)

            if verbose:
                print(f"           → {name}({args})")
                print(f"           ← {result[:70]}")

            messages.append({
                "role": "tool",
                "tool_call_id": call.get("id", ""),
                "content": result,
            })
            all_calls.append({"name": name, "arguments": args})
            results.append({"name": name, "arguments": args, "result": result})

        trace.append(build_trace_entry(turn, msg, results))

    # 用尽轮次：必须有明确出口，不能静默
    return {
        "answer": f"(达到最大轮次 {max_turns} 仍未得出最终答案，已中止以免无限循环)",
        "turns": max_turns,
        "tool_calls": all_calls,
        "trace": trace,
        "stopped_reason": "max_turns",
    }


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")

    print("实验 A：单步问题")
    r = run_agent("北京现在天气怎么样？")
    print(f"\n答案：{r['answer'][:120]}")
    print(f"轮次={r['turns']} 调用={len(r['tool_calls'])} 原因={r['stopped_reason']}")

    print("\n实验 B：多步问题")
    r2 = run_agent("北京和上海现在哪个更适合户外跑步？请比较两地的天气。")
    print(f"\n答案：{r2['answer'][:200]}")
    print(f"轮次={r2['turns']} 调用={len(r2['tool_calls'])} 原因={r2['stopped_reason']}")

    print("\n实验 C：工具失败（火星）")
    r3 = run_agent("火星现在的天气怎么样？")
    print(f"\n答案：{r3['answer'][:200]}")
    print(f"轮次={r3['turns']} 原因={r3['stopped_reason']}")

    print("\n实验 D：对照 max_turns=1")
    r4 = run_agent("北京和上海现在哪个更适合户外跑步？请比较两地的天气。", max_turns=1)
    print(f"\n答案：{r4['answer'][:150]}")
    print(f"轮次={r4['turns']} 原因={r4['stopped_reason']}")
