"""
第 02 课验收脚本
================

用法：
    cd agent-lab
    .\\.venv\\Scripts\\python.exe 验收\\check_hw02.py

8 项检查，全 PASS 才算过。

⚠ 会真的调用 API（约 4-5 次，flash 模型，成本 < 0.001 元）。
"""

import importlib.util
import json
import os
import sys
import traceback

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
HW_PATH = os.path.normpath(os.path.join(HERE, "..", "作业", "hw02_function_calling.py"))

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
    spec = importlib.util.spec_from_file_location("hw02", HW_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    print("=" * 70)
    print("第 02 课验收：Function Calling 原始协议")
    print(f"作业文件：{HW_PATH}")
    print("=" * 70)
    print()

    hw = load_homework()
    if not hw.API_KEY:
        print("！.env 里没读到 ZHIPU_API_KEY")
        sys.exit(2)
    print(f"模型：{hw.DEFAULT_MODEL}\n")

    # ---------- 1. build_tools_schema 结构 ----------
    print("【1】build_tools_schema 结构正确")
    schema = None
    try:
        schema = hw.build_tools_schema()
        assert isinstance(schema, list), f"应返回 list，实际 {type(schema).__name__}"
        assert len(schema) >= 2, f"至少要有 2 个工具，实际 {len(schema)} 个"
        names = set()
        for t in schema:
            assert t.get("type") == "function", "每个工具的 type 必须是 'function'"
            fn = t.get("function") or {}
            assert fn.get("name"), "工具缺少 name"
            assert fn.get("parameters", {}).get("type") == "object", \
                f"{fn.get('name')}: parameters.type 必须是 'object'"
            names.add(fn["name"])
        assert "get_weather" in names, f"缺少 get_weather，实际有 {names}"
        assert "get_time" in names, f"缺少 get_time，实际有 {names}"
        ok(1, "结构正确", f"工具 = {sorted(names)}")
    except NotImplementedError:
        fail(1, "结构正确", "TODO 1 还没写")
    except Exception as e:
        fail(1, "结构正确", f"{type(e).__name__}: {e}")

    # ---------- 2. description 质量 ----------
    print("【2】工具 description 写得够具体（模型靠它决定何时调用）")
    try:
        bad = []
        for t in schema or []:
            fn = t["function"]
            desc = (fn.get("description") or "").strip()
            if len(desc) < 10:
                bad.append(f"{fn.get('name')}: description 只有 {len(desc)} 字")
            # 检查参数也有 description
            for pname, p in (fn.get("parameters", {}).get("properties") or {}).items():
                if len((p.get("description") or "").strip()) < 2:
                    bad.append(f"{fn.get('name')}.{pname}: 参数缺 description")
        if bad:
            fail(2, "description 质量", "；".join(bad))
        else:
            total = sum(len(t["function"]["description"]) for t in schema)
            ok(2, "description 质量合格", f"两个工具共 {total} 字说明")
    except Exception as e:
        fail(2, "description 质量", f"{type(e).__name__}: {e}")

    # ---------- 3+4. 端到端 + arguments 解析 ----------
    print("【3】端到端：问天气 → 模型要求调工具 → 本地执行 → 回传 → 自然语言回答")
    loop_result = None
    try:
        loop_result = hw.run_tool_loop("北京今天天气怎么样？", use_tools=True, verbose=False)
        assert isinstance(loop_result, dict), "run_tool_loop 应返回 dict"
        calls = loop_result.get("tool_calls") or []
        assert len(calls) >= 1, "没有触发任何工具调用 —— 检查 tools 声明"
        assert calls[0]["name"] == "get_weather", f"调错了工具：{calls[0]['name']}"
        assert isinstance(calls[0]["arguments"], dict), "arguments 应该是 dict"
        assert calls[0]["arguments"].get("city"), "arguments 里没有 city"
        answer = loop_result.get("answer") or ""
        assert answer.strip(), "最终回答是空的"
        ok(3, "端到端通了",
           f"调用 {len(calls)} 次，{loop_result['rounds']} 轮\n"
           f"         arguments = {calls[0]['arguments']}\n"
           f"         最终回答 = {answer[:60]!r}")
    except NotImplementedError:
        fail(3, "端到端", "TODO 还没写完")
    except Exception as e:
        fail(3, "端到端", f"{type(e).__name__}: {e}")

    print("【4】arguments 被正确解析成 dict（它是 JSON 字符串，不是对象）")
    if loop_result and loop_result.get("tool_calls"):
        c = loop_result["tool_calls"][0]
        if isinstance(c["arguments"], dict) and "city" in c["arguments"]:
            ok(4, "arguments 解析正确", f"类型 {type(c['arguments']).__name__}，内容 {c['arguments']}")
        else:
            fail(4, "arguments 解析正确", f"得到 {c['arguments']!r}")
    else:
        fail(4, "arguments 解析正确", "跳过：第 3 项没通过")

    # ---------- 5. 畸形 arguments 抛异常 ----------
    print("【5】畸形 arguments 抛 ToolArgumentError")
    try:
        fake = {"choices": [{"finish_reason": "tool_calls", "message": {
            "role": "assistant", "content": None,
            "tool_calls": [{"id": "x", "type": "function",
                            "function": {"name": "get_weather", "arguments": "{这不是JSON"}}]}}]}
        try:
            hw.parse_tool_calls(fake)
            fail(5, "畸形 arguments", "没有抛异常 —— 你把错误吞掉了？")
        except hw.ToolArgumentError:
            ok(5, "畸形 arguments 正确抛异常")
        except Exception as e:
            fail(5, "畸形 arguments", f"抛的是 {type(e).__name__}，应该是 ToolArgumentError")
    except NotImplementedError:
        fail(5, "畸形 arguments", "TODO 2 还没写")
    except Exception as e:
        fail(5, "畸形 arguments", f"{type(e).__name__}: {e}")

    # ---------- 6. 无 tool_calls 时返回空列表 ----------
    print("【6】没有 tool_calls 时返回空列表（而不是报错）")
    try:
        plain = {"choices": [{"finish_reason": "stop", "message": {
            "role": "assistant", "content": "你好"}}]}
        r = hw.parse_tool_calls(plain)
        assert r == [], f"应返回 []，实际 {r!r}"
        ok(6, "空列表处理正确")
    except NotImplementedError:
        fail(6, "空列表处理", "TODO 2 还没写")
    except Exception as e:
        fail(6, "空列表处理", f"{type(e).__name__}: {e}")

    # ---------- 7. 未知工具抛异常 ----------
    print("【7】execute_tool 对未知工具抛 UnknownToolError")
    try:
        try:
            hw.execute_tool("nonexistent_tool_xyz", {})
            fail(7, "未知工具", "没有抛异常")
        except hw.UnknownToolError:
            ok(7, "未知工具正确抛异常")
        except Exception as e:
            fail(7, "未知工具", f"抛的是 {type(e).__name__}，应该是 UnknownToolError")
    except NotImplementedError:
        fail(7, "未知工具", "TODO 3 还没写")
    except Exception as e:
        fail(7, "未知工具", f"{type(e).__name__}: {e}")

    # ---------- 8. 对照组：不传 tools ----------
    print("【8】对照组：同样的问题，不传 tools 字段 → 模型不会调工具")
    print("      （这是本课的核心结论：模型看的是 tools 字段，不是提示词）")
    try:
        r2 = hw.run_tool_loop("北京今天天气怎么样？", use_tools=False, verbose=False)
        n2 = len(r2.get("tool_calls") or [])
        n1 = len((loop_result or {}).get("tool_calls") or [])
        if n2 == 0 and n1 > 0:
            ok(8, "对照实验成功",
               f"带 tools → 调用 {n1} 次工具\n"
               f"         不带 tools → 调用 {n2} 次工具\n"
               f"         同一模型、同一问题、同一提示词，唯一变量是 tools 字段")
        elif n2 > 0:
            fail(8, "对照实验", f"不带 tools 竟然也调了 {n2} 次工具，异常")
        else:
            fail(8, "对照实验", f"带 tools 时也没调工具（{n1} 次），先修第 3 项")
    except NotImplementedError:
        fail(8, "对照实验", "TODO 还没写完")
    except Exception as e:
        fail(8, "对照实验", f"{type(e).__name__}: {e}")

    # ---------- 汇总 ----------
    print()
    print("=" * 70)
    print(f"结果：{len(PASSED)}/8 通过")
    if FAILED:
        print(f"未通过：{FAILED}")
        print()
        print("下一步：按提示改 作业\\hw02_function_calling.py，改完重跑。")
        print("卡住超过 20 分钟把报错贴给我，我给提示不给答案。")
        sys.exit(1)
    else:
        print("全部通过 ✓")
        print()
        print("接下来回答讲义最后的三个追问（Q1/Q2/Q3）。")
        sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        print()
        print("验收脚本自己炸了：")
        traceback.print_exc()
        sys.exit(2)
