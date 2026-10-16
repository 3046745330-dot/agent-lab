# 第 02 课：Function Calling 原始协议

> **这一课是整条路线的分水岭。**
>
> 学完 00 课，你会调模型；学完这一课，你才能让模型**做事**。
> 你的 ai-group 里最值钱的那个实测结论（"模型看的是 tools 字段不是提示词"），
> 原理就在这一课。

---

## 一、先搞清楚 Function Calling 到底解决了什么

### 没有它的时候，大家怎么干？

在 Function Calling 出现之前，让模型调用外部能力靠**文本约定**。比如：

```
你是一个助手。如果需要查天气，请输出：
<call>get_weather({"city":"北京"})</call>
```

然后你写正则去解析 `<call>...</call>`。

**这有三个致命问题**：

| 问题 | 表现 |
|---|---|
| **格式不可靠** | 模型可能输出 `<call>`、`[call]`、`{"tool":...}`，你的正则永远不够用 |
| **没有约束** | 参数名写错、JSON 语法错、多输出一个括号——你得自己修 |
| **模型不认账** | 这是最坑的：**模型不认为自己"有工具"**，它会说"我无法直接查询天气" |

第三条你在 ai-group 里亲身体验过：

> 同一个 DeepSeek 模型，只给文本约定时它回「我无法直接在你的电脑上创建文件」，
> 并附上记事本/终端/PowerShell 三种手动操作方法。
> **即使把提示词改成明确写着「你确实能写文件，不要说无法创建」也不管用。**
> 而对照组（不声明 tools）它甚至吐出了 `<｜｜DSML｜｜ calls> <｜｜DSML｜｜ invoke name="write_file">`
> ——它本来就想调工具，只是没有工具可调，于是把调用当文本打出来了。

### Function Calling 的做法

**把工具定义放进请求的 `tools` 字段**。就这一个改动，三个问题全解决：

```
① 格式由模型厂商保证 —— 模型输出的是结构化 JSON，不是自由文本
② 参数由 schema 约束   —— 你声明了类型和必填项，模型必须遵守
③ 模型知道"我有工具"   —— 这是最关键的：tools 字段改变了模型的行为模式
```

> **记住这句话**：模型判断「我有没有工具」，看的是请求里的 `tools` 字段，不是提示词。

---

## 二、协议长什么样

### 2.1 请求侧：怎么声明工具

`tools` 是一个数组，每个元素描述一个工具：

```json
{
  "model": "glm-4-flash",
  "messages": [{"role": "user", "content": "北京今天多少度？"}],
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "get_weather",
        "description": "查询指定城市的当前天气",
        "parameters": {
          "type": "object",
          "properties": {
            "city": {
              "type": "string",
              "description": "城市名，例如：北京、上海"
            },
            "unit": {
              "type": "string",
              "enum": ["celsius", "fahrenheit"],
              "description": "温度单位，默认摄氏度"
            }
          },
          "required": ["city"]
        }
      }
    }
  ]
}
```

**逐字段说清楚**：

| 字段 | 作用 | 新手最容易错的地方 |
|---|---|---|
| `name` | 函数名 | 用英文+下划线，别用中文 |
| `description` | **给模型看的说明** | ⚠️ **这个字段决定了模型什么时候会调它**，写不好模型就不用 |
| `parameters` | JSON Schema 描述参数 | 必须 `"type": "object"` |
| `properties` | 每个参数的类型和说明 | 每个参数都要写 `description` |
| `enum` | 限定取值 | 有固定选项就用它，能大幅降低出错率 |
| `required` | 必填参数 | 别把所有参数都标必填 |

> **`description` 是最重要的字段**。模型不看你的代码，只看这段文字决定"要不要调、怎么调"。
> 写得含糊 → 该调的时候不调；写得清楚 → 一次就对。

### 2.2 响应侧：模型怎么"调"工具

当模型决定调工具时，响应的 `finish_reason` 变成 `tool_calls`，
并且 `message` 里多一个 `tool_calls` 数组：

```json
{
  "choices": [
    {
      "index": 0,
      "finish_reason": "tool_calls",
      "message": {
        "role": "assistant",
        "content": null,
        "tool_calls": [
          {
            "id": "call_abc123",
            "type": "function",
            "function": {
              "name": "get_weather",
              "arguments": "{\"city\": \"北京\", \"unit\": \"celsius\"}"
            }
          }
        ]
      }
    }
  ]
}
```

**三个必须注意的点**：

1. **`content` 可能是 `null`** —— 模型这轮不输出文本，只输出工具调用。
   你的代码如果写 `response["choices"][0]["message"]["content"]` 然后 `.strip()`，
   **这里会崩**。（00 课的 `get_content` 就需要加防御）

2. **`arguments` 是字符串，不是对象！**
   它是 JSON **序列化后**的字符串，你要自己 `json.loads()`。
   这是新手最常见的坑。

3. **`id` 是这次调用的凭据** —— 你要在回传结果时带上它，模型才知道这是对哪次调用的响应。

### 2.3 回传侧：把执行结果给模型

你本地执行完函数，要把结果作为一条 `role="tool"` 的消息追加进对话：

```json
{
  "messages": [
    {"role": "user", "content": "北京今天多少度？"},
    {
      "role": "assistant",
      "content": null,
      "tool_calls": [
        {"id": "call_abc123", "type": "function",
         "function": {"name": "get_weather", "arguments": "{\"city\":\"北京\"}"}}
      ]
    },
    {
      "role": "tool",
      "tool_call_id": "call_abc123",
      "content": "{\"city\":\"北京\",\"temp\":18,\"unit\":\"celsius\",\"condition\":\"晴\"}"
    }
  ]
}
```

**关键点**：

- `role` 是 `"tool"`
- **`tool_call_id` 必须等于之前那个 `id`** —— 这是配对机制
- `content` 通常是字符串（JSON 字符串最常见）

然后**再发一次请求**，模型就会基于工具结果生成自然语言回答。

---

## 三、完整流程图

```
用户问："北京今天多少度？"
    │
    ▼
[第 1 次请求]  messages=[user]  +  tools=[get_weather]
    │
    ▼
模型返回：finish_reason="tool_calls"
          tool_calls=[{id:"call_abc123", name:"get_weather", arguments:"{\"city\":\"北京\"}"}]
    │
    ▼
【你的代码】本地执行 get_weather(city="北京")  →  {"temp":18,"condition":"晴"}
    │
    ▼
[第 2 次请求]  messages=[user, assistant(tool_calls), tool(result)]
    │
    ▼
模型返回：finish_reason="stop"
          content="北京现在 18 度，晴天。"
```

**这就是 Agent 循环的最小形态**。第 03 课要做的，只是把这个流程套进 `while` 循环，
让它能连续调用多个工具。

---

## 五、最容易踩的 5 个坑

### 坑 0（本课实测踩到的）：**不是所有模型都支持工具调用**

这是我在写这一课的材料时**真的踩到的**，所以放在最前面。

我用 `glm-4-flash`（最便宜那档）配好 tools 跑验收，结果是：

```
【3】端到端  FAIL  没有触发任何工具调用 —— 检查 tools 声明
【8】对照    FAIL  带 tools 时也没调工具（0 次）
```

代码完全正确（就是本课的参考实现），但模型**根本不返回 `tool_calls`**。

我写了诊断脚本，把智谱几个模型挨个试了一遍：

| 模型 | 支持工具调用 | 是否思考型 | 结论 |
|---|---|---|---|
| `glm-4-flash` | ❌ 不返回 `tool_calls` | 否 | 能力不够 |
| `glm-4.5-flash` | ✅ 返回 | **是**（思考吃 max_tokens） | 要调大 max_tokens |
| **`glm-4-air`** | ✅ 返回 | **否** | ✅ **选它** |
| `glm-4-plus` / `glm-4.5` / `glm-4` | ✅ 返回 | 否 | 更贵，备用 |

### 这里其实踩了两个坑，不是一个

**坑 A：轻量档模型可能砍掉 function calling。**
`glm-4-flash` 和 `glm-4.5-flash` 名字很像、都便宜，但前者不支持工具调用。

**坑 B：思考型模型的 reasoning 会计入 `max_tokens`。**
我换成 `glm-4.5-flash` 后，第 02 课过了，但**第 00 课反而挂了 3 项**。
诊断发现：

```
max_tokens= 100  finish=length  content=  0字  reasoning=184字   ← 正文为空！
max_tokens= 200  finish=length  content= 23字  reasoning=313字   ← 还是被截断
max_tokens= 500  finish=stop    content= 46字  reasoning=357字   ← 这才正常
```

`glm-4.5-flash` 是**思考型模型**：它先生成一大段思考（`reasoning_content`），
再输出正文。**这两部分共享 `max_tokens` 预算。**
所以 `max_tokens=100` 时，100 个 token 全被思考吃掉了，`content` 是空字符串。

> ⚠️ 这个坑和你在 ai-group 里遇到的是同一个：
> `kimi-k2.6` 也是思考型，`max_tokens` 给 1500 正文为空，给 3000 才有正文。
> **同一个坑，你在两个不同的项目里踩了两次——说明这是通用规律，不是巧合。**

### 最后的选型

`glm-4-air`：**支持工具调用 + 非思考型**，两个条件都满足，且价格合理。
`.env` 里已改为它。

> **这个坑值钱的地方**：它教了一个真实的工程习惯——
> **当代码看起来完全正确但行为不对时，先怀疑"这个模型到底支不支持这个能力"，而不是怀疑自己的代码。**
>
> 怎么查？写个 30 行的最小复现脚本，把可疑的模型挨个跑一遍，控制变量。
> 上面那两张表就是这么来的。**不要靠猜，要靠测。**

> 💡 **面试可用的素材**：如果你被问"你踩过什么坑"，
> 这个例子比"我调通了一个 API"强得多——它体现了**归因能力**：
> 从"验收挂了"→"怀疑模型能力"→"写诊断脚本控制变量"→"定位到两个独立原因"→"选型"。

---

### 坑 1：`arguments` 是字符串不是对象

```python
# ❌ 错
city = tool_call["function"]["arguments"]["city"]   # TypeError

# ✅ 对
args = json.loads(tool_call["function"]["arguments"])
city = args["city"]
```

### 坑 2：`content` 可能是 `None`

模型只调工具不说话的轮次，`content` 是 `null`。
**你的 00 课 `get_content` 遇到这种响应会崩**——这是正常的，现在要加防御。

### 坑 3：忘记带 `tool_call_id`

回传结果时如果不带 `tool_call_id`，或者 id 对不上，
厂商会返回 400 错误。因为模型不知道这个结果对应哪次调用。

### 坑 4：以为一次只能调一个工具

`tool_calls` 是**数组**，模型可能一次要求调多个（并行工具调用）。
你必须遍历处理，不能只取 `[0]`。

### 坑 5：把 `description` 写成给人类看的

```python
# ❌ 太含糊，模型不知道该什么时候用
"description": "天气函数"

# ✅ 清楚说明用途、适用场景、返回什么
"description": "查询指定城市的实时天气，返回温度、天气状况。仅在用户询问天气时使用。"
```

---

## 五之二、坑 0 的延伸：怎么自己查模型能力

上面的诊断脚本只有 30 行，你也可以写。思路是**控制变量**：

```python
def probe(model):
    """用同一个请求测一个模型，只看它返不返回 tool_calls。"""
    body = {
        "model": model,
        "messages": [{"role": "user", "content": "北京今天天气怎么样？"}],
        "tools": TOOLS,          # 同一份工具声明
        "max_tokens": 200,
    }
    # ... 发请求，打印 finish_reason 和 tool_calls
```

**要点**：
- 唯一变量是 `model`，其他全部固定
- 看两个信号：`finish_reason` 是不是 `tool_calls`、`message.tool_calls` 有没有内容
- 遇到 HTTP 错误也要打出来（可能是模型不存在、或需要额外参数）

> **这个习惯比这一课的知识更重要**：
> 遇到"行为不符合预期"，先写最小复现 + 控制变量测一遍，
> 而不是在脑子里猜。**面试官最喜欢这种"我怎么定位问题"的叙述。**


---

## 五、你要写的三个函数

打开 `作业\hw02_function_calling.py`，填掉 TODO：

```python
def build_tools_schema() -> list:
    """返回工具声明数组，包含 get_weather 和 get_time 两个工具。"""

def parse_tool_calls(response: dict) -> list:
    """从响应里提取工具调用列表。
    返回 [{'id': str, 'name': str, 'arguments': dict}, ...]
    注意：arguments 要 json.loads 成 dict，解析失败要抛 ToolArgumentError。
    """

def execute_tool(name: str, arguments: dict) -> str:
    """执行工具，返回结果的 JSON 字符串。
    未注册的工具名抛 UnknownToolError。
    """
```

### 硬性约束

1. **只用标准库**（`json`/`urllib`/`os`），不装 `openai` SDK
2. **`get_weather` 和 `get_time` 用假数据实现**（别去调真实天气 API，那是另一件事）
3. **`parse_tool_calls` 必须处理 `arguments` 解析失败的情况**，抛自定义异常
4. **必须真的发请求**，不许 mock

---

## 六、验收标准

```powershell
cd C:\Users\yyy\Documents\deepseek-harness\default-workspace\agent-lab
.\.venv\Scripts\python.exe 验收\check_hw02.py
```

| # | 检查项 | 教你在意什么 |
|---|---|---|
| 1 | `build_tools_schema` 结构正确 | 你会写 JSON Schema |
| 2 | 工具声明里 `description` 非空且够长 | 你知道 description 是关键 |
| 3 | `parse_tool_calls` 能从真实响应提取调用 | 你会解析 `tool_calls` |
| 4 | `arguments` 被正确解析成 dict | 你知道它是字符串 |
| 5 | **端到端**：问天气 → 模型要求调工具 → 本地执行 → 回传 → 模型给自然语言答案 | 完整链路通了 |
| 6 | `parse_tool_calls` 对畸形 arguments 抛 `ToolArgumentError` | 错误处理 |
| 7 | `execute_tool` 对未知工具抛 `UnknownToolError` | 边界处理 |
| 8 | **对照组**：同样的提问，但**不传 tools**，模型不会返回 `tool_calls` | **证明 tools 字段才是关键** |

> **第 8 项是本课的灵魂。** 它用代码证明你 ai-group 里那个实测结论：
> 模型判断有没有工具，看的是 `tools` 字段，不是提示词。

---

## 七、课后追问（必须答得上来）

**Q1.** 为什么 `arguments` 是字符串而不是直接给对象？猜猜厂商为什么这么设计。

**Q2.** 如果模型一次返回 3 个 `tool_calls`，你的代码要怎么处理？执行顺序有讲究吗？

**Q3.** 模型返回了 `tool_calls`，但你本地执行工具**失败了**（比如天气 API 超时）。
   这时候应该怎么做？直接把异常抛出去吗？

> 提示 Q3：想想 ai-group 里"失败也要留痕"的原则。

---

## 八、卡住了怎么办

1. 先看报错（逐字看）
2. `print(json.dumps(response, ensure_ascii=False, indent=2))` —— 看响应到底长什么样
3. 超过 20 分钟，跟我说「卡在哪、报什么错、试过什么」
4. 实在写不出来看 `参考实现\hw02_ref.py`，**看完关掉自己重写**

---

**下一步**：这一课做完，你就具备写 Agent 主循环的全部前置知识了。开始吧。
