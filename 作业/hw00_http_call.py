"""
第 00 课作业：裸 HTTP 调用 Chat API
=====================================

目标：不借助任何 SDK，用标准库把一个请求发出去、把响应解析回来。

规则：
  1. 只准用标准库：urllib.request / json / os / urllib.error
  2. 必须真的发 HTTP 请求，不许 mock、不许写死假数据
  3. 四个 TODO 全部填完

讲义：../讲义/00-HTTP与ChatAPI.md
验收：python ../验收/check_hw00.py
"""

import json
import os
import urllib.error
import urllib.request

# ============================================================
# 下面这段（.env 读取 + 常量）是样板代码，已经替你写好了。
# 它做的事：从同目录的 .env 文件里读出 API key 和地址。
# 不用 pip install python-dotenv，手写 8 行就够。
# ============================================================

_ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env")


def _load_env(path: str) -> dict:
    """读 .env，返回 {KEY: VALUE}。忽略空行和 # 开头的注释。"""
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
    """API 调用失败。必须带上 HTTP 状态码和响应体原文。

    用法：raise ChatAPIError(status=401, body='{"error": {...}}')
    """

    def __init__(self, status: int, body: str):
        self.status = status
        self.body = body
        super().__init__(f"Chat API 调用失败 HTTP {status}: {body}")


# ============================================================
# TODO 1  —— 组装请求体
# ============================================================
def build_request(messages: list, model: str = None,
                  max_tokens: int = 100, temperature: float = 0.7) -> dict:
    """把参数组装成要 POST 过去的 JSON body（一个 dict）。

    提示：
      - model 传 None 时用 DEFAULT_MODEL
      - 必须包含 4 个键：model / messages / max_tokens / temperature
      - messages 原样放进"messages"键，不要改它的结构
      - 返回的是 dict，不是字符串（序列化成 JSON 是 chat() 的事）

    讲义第二节"一次请求的完整解剖"。
    """
    # TODO 1: 在这里写你的实现
    raise NotImplementedError("TODO 1 还没写")


# ============================================================
# TODO 2  —— 真的发出去
# ============================================================
def chat(messages: list, model: str = None,
         max_tokens: int = 100, temperature: float = 0.7) -> dict:
    """发一次 HTTP POST，返回解析后的完整响应 dict。

    步骤提示：
      1. body_dict = build_request(...)          # 复用 TODO 1
      2. json.dumps(body_dict).encode("utf-8")   # dict -> bytes
      3. 构造 urllib.request.Request(url, data=..., headers={...}, method="POST")
         headers 至少要有两个：Authorization 和 Content-Type
         Authorization 的值格式是 "Bearer <你的key>"
      4. urllib.request.urlopen(req, timeout=...) 发出去
      5. 读回来的是 bytes，要 .decode("utf-8") 再用 json.loads() 变回 dict
      6. 返回那个 dict

    错误处理（重点！）：
      - urlopen 在非 2xx 时会抛 urllib.error.HTTPError
      - HTTPError 对象本身是个"响应"，用 e.read().decode("utf-8") 能拿到错误体
      - 把状态码和错误体一起包进 ChatAPIError 抛出去
        （不要只抛 HTTPError —— 那样你就丢掉了最有用的调试信息）

    讲义第四节"错误处理：错误体才是宝藏"。
    """
    # TODO 2: 在这里写你的实现
    raise NotImplementedError("TODO 2 还没写")


# ============================================================
# TODO 3  —— 从响应里取出模型说的话
# ============================================================
def get_content(response: dict) -> str:
    """返回 choices[0].message.content 这个字符串。

    注意 choices 是个数组，即使只有一个元素也要写 [0]。
    讲义第三节"一次响应的完整解剖"。
    """
    # TODO 3: 在这里写你的实现
    raise NotImplementedError("TODO 3 还没写")


# ============================================================
# TODO 4  —— 取出 token 用量
# ============================================================
def get_usage(response: dict) -> dict:
    """返回 {'prompt_tokens': int, 'completion_tokens': int, 'total_tokens': int}

    这三个数就是钱。讲义第三节。
    """
    # TODO 4: 在这里写你的实现
    raise NotImplementedError("TODO 4 还没写")


# ============================================================
# 自测：填完 TODO 后直接运行这个文件
#   python hw00_http_call.py
# ============================================================
if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")  # Windows 控制台默认 gbk，会乱码

    print("=" * 60)
    print("第 1 次请求：只问一个问题")
    print("=" * 60)

    r1 = chat([{"role": "user", "content": "用一句话解释什么是无状态。"}])
    answer1 = get_content(r1)
    print("模型说：", answer1)
    print("用量：", get_usage(r1))

    print()
    print("=" * 60)
    print("第 2 次请求：把第 1 轮的问答塞进历史，再问一个新的")
    print("=" * 60)

    history = [
        {"role": "user", "content": "用一句话解释什么是无状态。"},
        {"role": "assistant", "content": answer1},          # ← 把上一轮的答案塞回去
        {"role": "user", "content": "那我刚才问的是什么？"},
    ]
    r2 = chat(history)
    print("模型说：", get_content(r2))
    print("用量：", get_usage(r2))

    print()
    print(">>> 对比两次的 prompt_tokens，你发现了什么？")
    print(">>> 这就是'记忆'的全部秘密。")
