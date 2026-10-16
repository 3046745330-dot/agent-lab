# 第 00 课：裸 HTTP 调用 Chat API

> **这一课不教 Agent，只教一件事：你和模型之间到底传了什么。**
> 学完你会明白，为什么"记忆"、"上下文"、"token 爆炸"这些词是同一个问题的不同侧面。

---

## 一、先接受一个残酷的事实

大部分人以为的：

```
我 ──"你好"──> 大模型（它记得我们聊过什么）──"你好"──> 我
我 ──"我叫小明"──> 大模型（它记住了）──"好的"──> 我
我 ──"我叫什么"──> 大模型（它记得）──"小明"──> 我
```

**真实情况：**

```
第1次请求，我发过去的完整内容：
    [{"role":"user","content":"你好"}]

第2次请求，我发过去的完整内容：
    [{"role":"user","content":"你好"},
     {"role":"assistant","content":"你好！"},
     {"role":"user","content":"我叫小明"}]

第3次请求，我发过去的完整内容：
    [{"role":"user","content":"你好"},
     {"role":"assistant","content":"你好！"},
     {"role":"user","content":"我叫小明"},
     {"role":"assistant","content":"好的"},
     {"role":"user","content":"我叫什么"}]
```

**服务器不存任何东西。它是一个无状态的函数。**

所谓"它记得我"，是你（或某个框架）**每次都把整段历史重新发了一遍**。

### 这个事实一口气解释了 5 件事

| 现象 | 原因 |
|---|---|
| 对话越长越贵 | 每次请求都重发全部历史，token 随轮数线性增长 |
| 聊到一半它"忘事" | 历史被截断了，或被摘要压缩了 |
| 有"上下文窗口"这个限制 | 一次请求能塞进去的 token 有上限 |
| 为什么要搞 RAG | 塞不下全部知识，只能每次检索最相关的片段塞进去 |
| "Agent 记忆"是个要自己写的模块 | 因为压根没人替你记 |

> **记住这句话：LLM API 是无状态的纯函数。所有"记忆"都是客户端的事。**
> 你毕设里的"记忆模块"，本质就是"怎么决定这次发哪些历史过去"。

---

## 二、一次请求的完整解剖

API 调用**不是魔法，就是一个 HTTP POST**。用 `curl` 就能调：

```bash
curl https://open.bigmodel.cn/api/paas/v4/chat/completions \
  -H "Authorization: Bearer $ZHIPU_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "glm-4-flash",
    "messages": [{"role": "user", "content": "你好"}],
    "max_tokens": 100,
    "temperature": 0.7
  }'
```

三部分，就这么多：

```
① URL          https://open.bigmodel.cn/api/paas/v4/chat/completions
② Headers      Authorization: Bearer <你的key>   ← 身份
               Content-Type: application/json   ← 我说的是 JSON
③ Body(JSON)   {
                 "model": "glm-4-flash",       ← 用哪个模型
                 "messages": [...],            ← 对话内容（核心！）
                 "max_tokens": 100,            ← 最多生成多少 token
                 "temperature": 0.7            ← 随机性 0~1
               }
```

### 逐字段说清楚

**`model`** — 模型名。同一个厂商有几十个模型，价格差 100 倍。`flash`/`turbo` 后缀 = 便宜快，`pro`/`max` = 贵且强。

**`messages`** — 这是唯一重要的字段。它是一个**数组**，每个元素有 `role` 和 `content`：

| role | 谁说的 | 用途 |
|---|---|---|
| `system` | 系统/开发者 | 给模型定人设和规则，**永远放第一个** |
| `user` | 用户 | 用户说的话 |
| `assistant` | 模型 | 模型之前说过的话（你把它塞回历史用） |

`system` 的角色很关键——**这是你能对模型施加控制的地方**。你毕设里"让 Agent 扮演校园助手"就是靠它。

**`max_tokens`** — 最多生成多少 token。注意是**生成**的，不包括你发过去的。设小了话说到一半被切断，设大了万一它抽风长篇大论你就多花钱。

**`temperature`** — 0 到 1（有些厂商到 2）。0 = 几乎每次都一样，适合抽取/分类；1 = 天马行空，适合创作。**要可复现的评测就必须调成 0。**

---

## 三、一次响应的完整解剖

```json
{
  "id": "8838...",
  "model": "glm-4-flash",
  "created": 1729000000,
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "你好！有什么我可以帮你的吗？"
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 12,
    "completion_tokens": 15,
    "total_tokens": 27
  }
}
```

你只需要关心三处：

- **`choices[0].message.content`** — 模型说的话。**99% 的时候你就要这个。**
- **`choices[0].finish_reason`** — 为什么停了。`stop`=正常说完，`length`=被 `max_tokens` 截断，`tool_calls`=它想调工具（第 02 课的主角）
- **`usage`** — 花了多少 token。**这就是钱。** `prompt_tokens` 是你发过去的，`completion_tokens` 是它生成的。看第 7 课的账单就靠它

> 注意 `choices` 是**数组**——因为可以一次要多个候选答案（`n` 参数）。默认 1 个，但结构还是数组，所以必须写 `choices[0]`。

---

## 四、错误处理：错误体才是宝藏

新手最常见的翻车：key 填错了，程序抛一个 `HTTP Error 401` 就完事了，**你完全不知道发生了什么**。

真相是：**API 在错误响应体里写清楚了原因**，但很多 HTTP 库不读它。

```
HTTP 401 Unauthorized
Body: {"error": {"code": "1002", "message": "Authorization Token 无效，请检查"}}
                    ↑ 这句话才是你需要的
```

所以本课要求你写一个自定义异常 `ChatAPIError`，**必须把 HTTP 状态码和响应体原文都带上**：

```python
raise ChatAPIError(status=401, body='{"error": {"message": "Authorization Token 无效"}}')
```

这个习惯值钱。以后你在毕设里调 Agent 调到半夜，就是靠这个一眼看出"哦，是我 key 过期了"而不是"程序炸了"。

---

## 五、你要写的四个函数

打开 `作业\hw00_http_call.py`，把 4 个 TODO 填掉：

```python
def build_request(messages, model=None, max_tokens=100, temperature=0.7) -> dict:
    """组装请求体。返回一个 dict，不含 URL 和 header。"""

def chat(messages, model=None, max_tokens=100, temperature=0.7) -> dict:
    """发请求，返回解析后的完整响应 dict。非 2xx 抛 ChatAPIError。"""

def get_content(response: dict) -> str:
    """从响应里取出模型说的话（字符串）。"""

def get_usage(response: dict) -> dict:
    """取出 token 用量，返回 {'prompt_tokens':int, 'completion_tokens':int, 'total_tokens':int}"""
```

### 硬性约束

1. **只用标准库**（`urllib.request`、`json`、`os`）。不装 `requests`、不装 `openai`。
   > 为什么？因为用 SDK 你会以为"调模型"是个函数调用。用 urllib 你会看到**它就是 HTTP**。看清这一层，后面所有框架你都看得穿。
2. **必须真的发出去**，不许 mock、不许 return 假数据。
3. **`ChatAPIError` 必须带上 status 和 body**。

`.env` 的读取和常量我已经替你写好了（那是样板代码，不值得你花时间）。

---

## 六、验收标准

```powershell
cd C:\Users\yyy\Documents\deepseek-harness\default-workspace\agent-lab
C:\Users\yyy\Documents\deepseek-harness\default-workspace\.venv\Scripts\python.exe 验收\check_hw00.py
```

脚本会检查 8 项，全 PASS 才算过：

| # | 检查项 | 教你在意什么 |
|---|---|---|
| 1 | `build_request` 返回结构正确 | 你真的知道要发什么过去 |
| 2 | `chat` 真的发出请求并拿到响应 | 端到端通了 |
| 3 | `get_content` 取出非空文本 | 你会解析响应 |
| 4 | `get_usage` 三个 token 字段都是正整数 | 你开始在意成本 |
| 5 | **无状态验证**：连发两次相同请求，第二次仍能正确回答 | **服务器不记你** |
| 6 | **历史验证**：把上一轮答案塞进 messages 再问，它"记得" | **记忆是客户端的事** |
| 7 | 错误路径：用假模型名调用抛 `ChatAPIError` | 错误处理 |
| 8 | 错误信息里带上了状态码 | 错误体是宝藏 |

**第 5、6 项是本课的灵魂。** 它们用代码证明第一节那个"残酷事实"。

---

## 七、课后追问（必须答得上来，这就是面试）

做完作业后，我要问你这三个问题。**答不上来就回去重读讲义。**

**Q1.** 你和模型聊了 20 轮，第 21 轮时你发过去的 `messages` 数组里有多少个元素？大概花了多少 token？如果第 21 轮和第 1 轮的价格一样吗？

**Q2.** `temperature=0` 和 `temperature=1` 分别用在什么场景？如果你要给 Agent 做"同一个问题跑 100 次看通过率"的评测，你选哪个？为什么？

**Q3.** 你的 Agent 要支持"用户问校园卡余额"，需要调用一个查余额的工具。用本课学的东西，你能想到怎么实现吗？（提示：`finish_reason` 有个值叫 `tool_calls`）

---

## 八、卡住了怎么办

**20 分钟内卡住是正常的，那正是学习发生的地方。** 请遵守：

1. 先看报错信息（真的看，逐字看）
2. 打印中间变量（`print(request_body)` 看发出去的是什么）
3. 用 `curl` 手动发一次，对比你的代码发的有什么不同
4. **超过 20 分钟**，跟我说"卡在哪一步、报什么错、你试过什么"，我给你提示——**但不会直接给答案**
5. 实在写不出来，看 `参考实现\hw00_ref.py`。看完**关掉，自己重写一遍**

---

**下一步**：读到这里就可以动手了。开始吧。
