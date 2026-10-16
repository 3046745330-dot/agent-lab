"""
第 00 课 参考实现
=================

⚠ 规则：卡住 20 分钟以上才看这个。
   看完之后**关掉它，自己从头重写一遍**。抄一遍等于没做。

对照点（看的时候注意这几处，它们是本课的全部知识点）：
  - build_request: 四个字段，一个不多一个不少
  - chat: 手动拼 header、手动 encode/decode、手动 catch HTTPError
  - get_content: choices 是数组，必须 [0]
  - get_usage: 直接搬 usage，不自己算
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


class ChatAPIError(Exception):
    def __init__(self, status: int, body: str):
        self.status = status
        self.body = body
        super().__init__(f"Chat API 调用失败 HTTP {status}: {body}")


# ---------- TODO 1 ----------
def build_request(messages: list, model: str = None,
                  max_tokens: int = 100, temperature: float = 0.7) -> dict:
    return {
        "model": model or DEFAULT_MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }


# ---------- TODO 2 ----------
def chat(messages: list, model: str = None,
         max_tokens: int = 100, temperature: float = 0.7) -> dict:
    body_dict = build_request(messages, model, max_tokens, temperature)
    data = json.dumps(body_dict, ensure_ascii=False).encode("utf-8")

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
        # HTTPError 本身也是响应对象，读它才有真正的原因
        err_body = e.read().decode("utf-8", errors="replace")
        raise ChatAPIError(status=e.code, body=err_body) from e
    except urllib.error.URLError as e:
        raise ChatAPIError(status=0, body=f"网络层失败: {e.reason}") from e

    return json.loads(raw)


# ---------- TODO 3 ----------
def get_content(response: dict) -> str:
    return response["choices"][0]["message"]["content"]


# ---------- TODO 4 ----------
def get_usage(response: dict) -> dict:
    u = response["usage"]
    return {
        "prompt_tokens": u["prompt_tokens"],
        "completion_tokens": u["completion_tokens"],
        "total_tokens": u["total_tokens"],
    }


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")

    r1 = chat([{"role": "user", "content": "用一句话解释什么是无状态。"}])
    a1 = get_content(r1)
    print("模型说：", a1)
    print("用量：", get_usage(r1))

    history = [
        {"role": "user", "content": "用一句话解释什么是无状态。"},
        {"role": "assistant", "content": a1},
        {"role": "user", "content": "那我刚才问的是什么？"},
    ]
    r2 = chat(history)
    print("模型说：", get_content(r2))
    print("用量：", get_usage(r2))
    print()
    print(">>> 对比两次 prompt_tokens：第二次明显更大 —— 因为历史被重发了。")
