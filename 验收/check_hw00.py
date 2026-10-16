"""
第 00 课验收脚本
================

用法：
    cd agent-lab
    C:\\Users\\yyy\\Documents\\deepseek-harness\\default-workspace\\.venv\\Scripts\\python.exe 验收\\check_hw00.py

它会把 作业/hw00_http_call.py 导入进来，逐项检查 8 条。
全 PASS 才算过。任何一条 FAIL，下面会告诉你差在哪。

⚠ 这个脚本会真的调用 API（约 6 次，flash 模型，总成本 < 0.001 元）。
"""

import importlib.util
import json
import os
import sys
import traceback

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
HW_PATH = os.path.normpath(os.path.join(HERE, "..", "作业", "hw00_http_call.py"))

PASSED, FAILED = [], []


def ok(n, title, detail=""):
    PASSED.append(n)
    print(f"  [PASS] {n}. {title}" + (f"\n         {detail}" if detail else ""))


def fail(n, title, detail=""):
    FAILED.append(n)
    print(f"  [FAIL] {n}. {title}" + (f"\n         {detail}" if detail else ""))


def load_homework():
    if not os.path.exists(HW_PATH):
        print(f"找不到作业文件：{HW_PATH}")
        sys.exit(2)
    spec = importlib.util.spec_from_file_location("hw00", HW_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    print("=" * 68)
    print("第 00 课验收：裸 HTTP 调用 Chat API")
    print(f"作业文件：{HW_PATH}")
    print("=" * 68)
    print()

    hw = load_homework()

    if not hw.API_KEY:
        print("！.env 里没读到 ZHIPU_API_KEY，检查 agent-lab\\.env")
        sys.exit(2)

    print(f"模型：{hw.DEFAULT_MODEL}")
    print(f"地址：{hw.API_URL}")
    print()

    # ---------- 1. build_request 结构 ----------
    print("【1】build_request 返回结构正确")
    try:
        body = hw.build_request([{"role": "user", "content": "hi"}])
        assert isinstance(body, dict), f"应返回 dict，实际 {type(body).__name__}"
        for k in ("model", "messages", "max_tokens", "temperature"):
            assert k in body, f"缺少字段 {k}"
        assert body["model"] == hw.DEFAULT_MODEL, "model 传 None 时应回落到 DEFAULT_MODEL"
        assert isinstance(body["messages"], list) and len(body["messages"]) == 1
        assert body["messages"][0]["content"] == "hi", "messages 被改动了"
        ok(1, "结构正确", f"字段 = {sorted(body.keys())}")
    except NotImplementedError:
        fail(1, "结构正确", "TODO 1 还没写（build_request 抛了 NotImplementedError）")
    except Exception as e:
        fail(1, "结构正确", f"{type(e).__name__}: {e}")

    # ---------- 2. chat 真的能拿到响应 ----------
    print("【2】chat 真的发出请求并拿到响应")
    r1 = None
    try:
        r1 = hw.chat([{"role": "user", "content": "回答一个字：好"}], temperature=0)
        assert isinstance(r1, dict), f"应返回 dict，实际 {type(r1).__name__}"
        assert "choices" in r1, "响应里没有 choices 字段 —— 你返回的是原始文本吗？"
        ok(2, "请求发出并解析成功", f"顶层字段 = {sorted(r1.keys())[:6]}")
    except NotImplementedError:
        fail(2, "请求发出并解析成功", "TODO 2 还没写（chat 抛了 NotImplementedError）")
    except Exception as e:
        fail(2, "请求发出并解析成功", f"{type(e).__name__}: {e}")

    # ---------- 3. get_content ----------
    print("【3】get_content 取出非空文本")
    content1 = None
    if r1 is None:
        fail(3, "取出文本", "跳过：上一步没拿到响应")
    else:
        try:
            content1 = hw.get_content(r1)
            assert isinstance(content1, str), f"应返回 str，实际 {type(content1).__name__}"
            assert content1.strip(), "返回了空字符串"
            ok(3, "取出文本", f"内容 = {content1[:40]!r}")
        except NotImplementedError:
            fail(3, "取出文本", "TODO 3 还没写")
        except Exception as e:
            fail(3, "取出文本", f"{type(e).__name__}: {e}")

    # ---------- 4. get_usage ----------
    print("【4】get_usage 三个 token 字段都是正整数")
    if r1 is None:
        fail(4, "解析用量", "跳过：没拿到响应")
    else:
        try:
            u = hw.get_usage(r1)
            assert isinstance(u, dict), f"应返回 dict，实际 {type(u).__name__}"
            for k in ("prompt_tokens", "completion_tokens", "total_tokens"):
                assert k in u, f"缺少 {k}"
                assert isinstance(u[k], int) and u[k] > 0, f"{k} 应为正整数，实际 {u[k]!r}"
            assert u["total_tokens"] == u["prompt_tokens"] + u["completion_tokens"], \
                "total 不等于 prompt + completion，你是不是猜的数？"
            ok(4, "解析用量", f"prompt={u['prompt_tokens']} completion={u['completion_tokens']} total={u['total_tokens']}")
        except NotImplementedError:
            fail(4, "解析用量", "TODO 4 还没写")
        except Exception as e:
            fail(4, "解析用量", f"{type(e).__name__}: {e}")

    # ---------- 5. 无状态验证 ----------
    print("【5】无状态验证：同一个问题问两次，第二次照样能答")
    print("      （如果服务器记得你，第二次就不需要重发内容了）")
    if r1 is None:
        fail(5, "无状态验证", "跳过：没拿到响应")
    else:
        try:
            r2 = hw.chat([{"role": "user", "content": "回答一个字：好"}], temperature=0)
            c2 = hw.get_content(r2)
            assert c2.strip(), "第二次请求返回空内容"
            u2 = hw.get_usage(r2)
            u1 = hw.get_usage(r1)
            # 同样的输入，prompt_tokens 应该几乎一样（±2 容差，有的厂商会算上特殊 token）
            diff = abs(u2["prompt_tokens"] - u1["prompt_tokens"])
            assert diff <= 2, f"两次相同输入的 prompt_tokens 差 {diff}，异常"
            ok(5, "无状态验证通过",
               f"两次 prompt_tokens = {u1['prompt_tokens']} / {u2['prompt_tokens']}（相同输入 → 相同大小，服务器没替你存东西）")
        except Exception as e:
            fail(5, "无状态验证", f"{type(e).__name__}: {e}")

    # ---------- 6. 历史验证：记忆是客户端的事 ----------
    print("【6】历史验证：把上一轮塞进 messages，它就'记得'")
    print("      （这是本课的灵魂：证明'记忆'完全由客户端负责）")
    SECRET = "20230123"
    try:
        # 第一轮：只告诉它一个事实
        turn1 = [{"role": "user", "content": f"记住这个数字：{SECRET}。只回复'好的'。"}]
        a1 = hw.get_content(hw.chat(turn1, temperature=0))

        # 第二轮：把第一轮完整塞回去，再问
        history = turn1 + [
            {"role": "assistant", "content": a1},
            {"role": "user", "content": "我刚才让你记住的数字是多少？只回答数字。"},
        ]
        a2 = hw.get_content(hw.chat(history, temperature=0))

        # 第三轮（对照组）：不带历史，直接问 —— 它应该不知道
        a3 = hw.get_content(hw.chat(
            [{"role": "user", "content": "我刚才让你记住的数字是多少？不知道就说'不知道'。"}],
            temperature=0))

        assert SECRET in a2, f"带上历史它也没答对：{a2[:80]!r}"
        ok(6, "历史验证通过",
           f"带历史 → {a2[:30]!r}（答对）\n         不带历史 → {a3[:30]!r}（它不知道）\n         "
           f"→ 结论：'记忆'是你每次重发历史造出来的，不是模型自带的")
    except Exception as e:
        fail(6, "历史验证", f"{type(e).__name__}: {e}")

    # ---------- 7. 错误路径 ----------
    print("【7】错误路径：用不存在的模型名，必须抛 ChatAPIError")
    try:
        hw.chat([{"role": "user", "content": "hi"}], model="this-model-does-not-exist-9999")
        fail(7, "错误处理", "没有抛异常 —— 你吞掉了错误？")
    except hw.ChatAPIError as e:
        assert e.status >= 400, f"status 应为错误码，实际 {e.status}"
        assert e.body and len(e.body) > 5, "body 是空的 —— 你把最有用的调试信息丢了"
        ok(7, "错误处理正确", f"status={e.status} body={e.body[:70]!r}")
    except NotImplementedError:
        fail(7, "错误处理", "TODO 2 还没写")
    except Exception as e:
        fail(7, "错误处理",
             f"抛的是 {type(e).__name__} 而不是 ChatAPIError。\n"
             f"         提示：urlopen 非 2xx 时抛 urllib.error.HTTPError，你要 catch 它再转成 ChatAPIError。\n"
             f"         原始错误：{e}")

    # ---------- 8. 错误信息里带状态码 ----------
    print("【8】错误信息里带上了状态码和响应体")
    try:
        hw.chat([{"role": "user", "content": "hi"}], model="this-model-does-not-exist-9999")
        fail(8, "错误信息完整", "没抛异常")
    except hw.ChatAPIError as e:
        msg = str(e)
        has_status = str(e.status) in msg
        has_body = len(msg) > len(str(e.status)) + 10
        if has_status and has_body:
            ok(8, "错误信息完整", f"str(e) = {msg[:80]!r}")
        else:
            fail(8, "错误信息完整",
                 f"异常信息里缺东西。status 在信息里？{has_status}；带了 body？{has_body}")
    except Exception:
        fail(8, "错误信息完整", "跳过：上一步没抛 ChatAPIError")

    # ---------- 汇总 ----------
    print()
    print("=" * 68)
    total = 8
    print(f"结果：{len(PASSED)}/{total} 通过")
    if FAILED:
        print(f"未通过：{FAILED}")
        print()
        print("下一步：按上面的提示改 作业\\hw00_http_call.py，改完重跑本脚本。")
        print("卡住超过 20 分钟就把报错贴给我，我给提示不给答案。")
        sys.exit(1)
    else:
        print("全部通过 ✓")
        print()
        print("接下来回答讲义最后的三个追问（Q1/Q2/Q3），那才是真正学会的标志。")
        sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        print()
        print("验收脚本自己炸了（说明作业模块加载阶段就出错了）：")
        traceback.print_exc()
        sys.exit(2)
