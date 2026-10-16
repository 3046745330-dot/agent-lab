# 第 03 课：Agent 主循环（ReAct）

> **前两课你在做"调用"和"工具"。这一课，你要让模型自己决定什么时候停。**
>
> 学完这一课，你就写出了 Agent 的最小内核。剩下的都是给它加零件。

---

## 一、先看一个反直觉的事实

02 课你已经写出了能调工具的代码。但那时候**循环的轮次是你写死的**：

```python
for _ in range(5):        # ← 最多 5 轮，你定的
    ...
```

**真正的问题来了**：你怎么知道该跑 3 轮还是 6 轮？

- 简单问题（"北京天气"）→ 1 轮就够
- 复杂问题（"对比北京和上海天气，哪个更适合跑步"）→ 可能要 4 轮
- 死循环（工具一直失败，模型一直重试）→ 永远不够

**答案是：不要你决定，让模型决定。**

模型什么时候说"我答完了"，你就什么时候停。这个"由模型自己判断是否结束"的机制，就是 Agent 和"调 API"的分界线。

---

## 二、ReAct 的核心：三条消息的角色

Agent 主循环看起来复杂，其实只有**三种消息**在轮转：

```
Thought（思考）  → 模型说"我该干什么"
Action（行动）   → 模型请求调某个工具
Observation（观察）→ 你返回工具的执行结果
        ↓
    回到 Thought（基于新信息再想）
        ↓
    ...直到模型说"我答完了"
```

对应到消息角色：

| ReAct 概念 | 消息 role | 谁产生 |
|---|---|---|
| Thought | `assistant`（可能同时带 `tool_calls`） | 模型 |
| Action | `assistant.tool_calls` | 模型 |
| Observation | `tool` | **你的代码** |
| 最终答案 | `assistant`（`finish_reason=stop`） | 模型 |

**关键理解**：所谓"Agent 会思考"，落地就是——**把工具结果塞回消息数组，再问一次模型。**

就这么朴素。没有任何魔法。

---

## 三、循环的骨架

```python
messages = [{"role": "user", "content": 问题}]

while True:
    resp = chat(messages, tools=TOOLS)
    msg = resp["choices"][0]["message"]

    # 【出口】模型不再要求调工具 → 它答完了
    if not msg.get("tool_calls"):
        return msg["content"]

    # 【继续】模型要调工具
    messages.append(msg)                      # 1. 把模型的请求记进历史
    for call in msg["tool_calls"]:
        result = execute_tool(call)            # 2. 本地执行
        messages.append({                      # 3. 结果塞回历史
            "role": "tool",
            "tool_call_id": call["id"],
            "content": result,
        })
    # 回到 while 顶部，再问一次
```

**注意三个细节，它们是初学者最常错的**：

1. **出口条件是 `not tool_calls`**，不是 `finish_reason == "stop"`。
   两者通常一致，但前者更稳（有些厂商 `finish_reason` 取值不规范）。

2. **第 1 步不能省**：必须把 `assistant` 那条（含 `tool_calls`）原样塞回历史。
   否则模型不知道"我刚请求过工具"，会重复请求 → 死循环。

3. **`tool_call_id` 必须配对**。这是 02 课讲过的，这里再强调一次。

---

## 四、光有循环是不够的：三个必须加的护栏

写出上面的循环只需 15 行。但**能跑**和**能用**的差距，全在护栏上：

### 护栏 1：最大轮次（防死循环）

```python
MAX_TURNS = 8
for turn in range(MAX_TURNS):
    ...
else:
    return "(达到最大轮次仍未结束)"     # 有出口，不静默挂死
```

**为什么必须有**：工具一直失败时，模型会一遍遍重试。没有上限就是无限烧钱。

### 护栏 2：失败也要回灌（不能抛异常走人）

工具执行失败时，**不要把异常抛出去**。要把失败信息作为 `tool` 消息喂回去：

```python
try:
    result = execute_tool(name, args)
except Exception as e:
    result = json.dumps({"error": str(e)})   # ← 失败当作"观察结果"
```

**为什么**：模型看到"这个工具报错了"，可能换个参数、换个工具，或者直接告诉用户。
**如果你抛异常，模型永远没有机会自救。**

> 这个思想你在 ai-group 里已经用过了：
> 「失败对纪要可见」—— 失败的成员留一条带 error 的消息，
> 而不是让整轮讨论崩掉。**同一个原则。**

### 护栏 3：中途的 thought 不能丢

有些模型在 `content` 里写思考（"我需要先查天气，再比较"），同时带 `tool_calls`。
**这条 `content` 也要塞回历史**，否则模型下一轮会"忘记自己想过什么"。

```python
messages.append({
    "role": "assistant",
    "content": msg.get("content"),        # ← 可能不是 None，别丢
    "tool_calls": msg["tool_calls"],
})
```

---

## 五、完整流程图

```
用户提问
   │
   ▼
┌──────────────────────────────────────────┐
│  while turn < MAX_TURNS                  │
│                                          │
│   请求模型（带 tools）                    │
│        │                                 │
│        ├─ 有 tool_calls？                │
│        │    ├─ 否 → return content ✓出口 │
│        │    └─ 是 ↓                      │
│        │                                 │
│   把 assistant(tool_calls) 塞回历史       │
│        │                                 │
│   逐个执行工具（失败也不抛，转成 error）   │
│        │                                 │
│   把 tool(result) 塞回历史                │
│        │                                 │
│   turn += 1                              │
└──────────────────────────────────────────┘
   │
   ▼
达到上限 → 返回明确提示（不静默）
```

---

## 六、你要写的四个部分

打开 `作业\hw03_agent_loop.py`：

```python
def run_agent(question: str, max_turns: int = 8, verbose: bool = True) -> dict:
    """跑 Agent 主循环。

    返回 {
        "answer": str,          最终答案
        "turns": int,           实际轮次
        "tool_calls": list,     所有工具调用记录
        "trace": list,          每轮发生了什么（用于调试）
        "stopped_reason": str,  "answered" | "max_turns"
    }
    """

def execute_tool_safely(name: str, arguments: dict) -> str:
    """执行工具，**任何异常都转成 JSON 错误字符串**，绝不向外抛。
    """

def needs_more_tools(response: dict) -> bool:
    """判断模型是否还想调工具（即循环的出口条件）。
    """

def build_trace_entry(turn: int, msg: dict, results: list) -> dict:
    """把一轮的过程记成 trace 条目（调试和面试都用得上）。
    """
```

### 硬性约束

1. **只准用标准库**
2. **`execute_tool_safely` 绝不抛异常** —— 任何错误都变成 `{"error": "..."}` 字符串
3. **`run_agent` 必须有出口** —— 达到 `max_turns` 时返回明确的 `stopped_reason`，不能静默挂死
4. **必须记录 trace** —— 每轮请求了什么、调了什么、得到什么
5. **`assistant` 的 content 不能丢**（即使它同时有 tool_calls）

---

## 七、验收标准

```powershell
cd C:\Users\yyy\Documents\deepseek-harness\default-workspace\agent-lab
.\.venv\Scripts\python.exe 验收\check_hw03.py
```

| # | 检查项 | 教你在意什么 |
|---|---|---|
| 1 | 简单问题（1 步可答）能正确结束 | 出口条件对 |
| 2 | **多步问题**（需 2+ 轮工具）能跑通 | 循环真的在转 |
| 3 | `tool_calls` 记录完整，`turns` 计数正确 | 可观测性 |
| 4 | `execute_tool_safely` 遇错返回 JSON 而不抛 | 护栏 2 |
| 5 | 工具故意报错时，Agent 能给出合理回复而非崩溃 | **失败可恢复** |
| 6 | 达到 `max_turns` 时返回明确原因 | 护栏 1 |
| 7 | `trace` 结构正确，能还原每轮发生了什么 | 调试能力 |
| 8 | **对比实验**：同一个多步问题，`max_turns=1` 会失败，`max_turns=8` 会成功 | **证明循环的必要性** |

> **第 8 项是本课的灵魂**：它用数据证明"主循环不是装饰，而是必需"。
> 这和你 rag-qa 里的 baseline 对比是同一个方法论——
> **改动前后要有数字对比。**

---

## 八、课后追问

**Q1.** 我把 `max_turns` 设成 100，会有什么后果？（提示：想想成本和死循环）

**Q2.** 如果模型连续 3 轮都在调**同一个**工具、传**同样的**参数，说明发生了什么？
   你会怎么处理？

**Q3.** 这个循环和你在 ai-group 里做的「@ 派发链」有什么共同点？
   （提示：都在解决"什么时候停"）

> Q3 是重点 —— 它要求你把两个项目联系起来。
> **面试里如果能主动说出"这两处的设计思想是一样的"，会非常加分。**

---

## 九、这一课做完，你就有了 Agent 内核

回头看：

| 课 | 你写的 | 对应 Agent 的什么 |
|---|---|---|
| 00 | 裸 HTTP 调用 | 与模型的通信层 |
| 02 | Function Calling | 工具协议 |
| **03** | **主循环 + 护栏** | **Agent 内核** |

**这三块加起来，就是毕设里"规划-执行-反思"的最小实现。**
后面的 RAG、记忆、降级，都是往这个内核上加零件。

---

**下一步**：开始写吧。卡住 20 分钟以上再问我。
