"""
第 02 课 参考实现
==================

⚠ 规则：卡住 20 分钟以上才看这个。看完关掉，自己重写一遍。

对照点（本课全部知识点）：
  - build_tools_schema: description 写具体，enum 用来约束取值
  - parse_tool_calls:   arguments 是 JSON **字符串**，要 loads；
                        必须遍历整个数组（可能多个）；畸形要抛异常
  - execute_tool:       返回 JSON 字符串不是 dict；未知工具抛异常
"""

import json
import os
import urllib.error
import urllib.request

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


class ChatAPIError(Exception):
    def __init__(self, status: int, body: str):
        self.status = status
        self.body = body
        super().__init__(f"Chat API 调用失败 HTTP {status}: {body}")


class ToolArgumentError(Exception):
    pass


class UnknownToolError(Exception):
    pass


def chat(messages: list, tools: list = None, model: str = None,
         max_tokens: int = 200, temperature: float = 0.7) -> dict:
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
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        raise ChatAPIError(status=e.code, body=e.read().decode("utf-8", errors="replace")) from e
    except urllib.error.URLError as e:
        raise ChatAPIError(status=0, body=f"网络层失败: {e.reason}") from e
    return json.loads(raw)


# ---------- TODO 1 ----------
def build_tools_schema() -> list:
    return [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": (
                    "查询指定城市的实时天气，返回温度、天气状况和湿度。"
                    "仅当用户询问天气、气温、下雨、冷热等天气相关问题时使用。"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "city": {
                            "type": "string",
                            "description": "城市名称，例如：北京、上海、南宁",
                        },
                        "unit": {
                            "type": "string",
                            "enum": ["celsius", "fahrenheit"],
                            "description": "温度单位，默认摄氏度 celsius",
                        },
                    },
                    "required": ["city"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_time",
                "description": (
                    "查询指定城市的当前日期和时间。"
                    "仅当用户询问时间、日期、几点了等问题时使用。"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "city": {
                            "type": "string",
                            "description": "城市名称，例如：北京、上海、南宁",
                        }
                    },
                    "required": ["city"],
                },
            },
        },
    ]


# ---------- TODO 2 ----------
def parse_tool_calls(response: dict) -> list:
    try:
        message = response["choices"][0]["message"]
    except (KeyError, IndexError) as exc:
        raise ToolArgumentError(f"响应结构异常: {exc}") from exc

    raw_calls = message.get("tool_calls") or []
    if not raw_calls:
        return []

    result = []
    for rc in raw_calls:                       # 必须遍历，不能只取 [0]
        fn = rc.get("function") or {}
        name = fn.get("name")
        if not name:
            raise ToolArgumentError(f"工具调用缺少 name 字段: {rc!r}")

        raw_args = fn.get("arguments")
        if raw_args is None:
            args = {}
        elif isinstance(raw_args, dict):
            args = raw_args                   # 少数厂商直接给对象，容错
        else:
            try:
                args = json.loads(raw_args)   # ← 核心：它是字符串
            except (json.JSONDecodeError, TypeError) as exc:
                raise ToolArgumentError(
                    f"arguments 不是合法 JSON: {raw_args!r}"
                ) from exc
        if not isinstance(args, dict):
            raise ToolArgumentError(f"arguments 解析后不是对象: {args!r}")

        result.append({
            "id": rc.get("id", ""),
            "name": name,
            "arguments": args,
        })
    return result


# ---------- TODO 3 ----------
def execute_tool(name: str, arguments: dict) -> str:
    if name == "get_weather":
        city = (arguments or {}).get("city", "")
        data = _WEATHER_DB.get(city)
        if data is None:
            return json.dumps({"error": f"未知城市: {city}"}, ensure_ascii=False)
        return json.dumps(data, ensure_ascii=False)

    if name == "get_time":
        city = (arguments or {}).get("city", "")
        t = _TIME_DB.get(city)
        if t is None:
            return json.dumps({"error": f"未知城市: {city}"}, ensure_ascii=False)
        return json.dumps({"city": city, "time": t}, ensure_ascii=False)

    raise UnknownToolError(f"未注册的工具: {name}")


def run_tool_loop(question: str, use_tools: bool = True, verbose: bool = True) -> dict:
    messages = [{"role": "user", "content": question}]
    tools = build_tools_schema() if use_tools else None
    all_calls = []
    rounds = 0
    for _ in range(5):
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
            messages.append({"role": "tool", "tool_call_id": c["id"], "content": result})
    return {"answer": "(超过 5 轮未收敛)", "tool_calls": all_calls, "rounds": rounds}


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    print("实验 A：带 tools")
    r = run_tool_loop("北京今天天气怎么样？")
    print(f"\n回答：{r['answer']}")
    print(f"工具调用 {len(r['tool_calls'])} 次，{r['rounds']} 轮")
    print("\n实验 B：不带 tools")
    r2 = run_tool_loop("北京今天天气怎么样？", use_tools=False)
    print(f"\n回答：{r2['answer']}")
    print(f"工具调用 {len(r2['tool_calls'])} 次，{r2['rounds']} 轮")
