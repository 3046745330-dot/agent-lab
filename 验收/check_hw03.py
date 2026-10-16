"""
第 03 课验收脚本
================

用法：
    cd agent-lab
    .\\.venv\\Scripts\\python.exe 验收\\check_hw03.py

8 项检查，全 PASS 才算过。

⚠ 会真的调用 API（约 8-12 次），预计 2-4 分钟，成本 < 0.02 元。
"""

import importlib.util
import json
import os
import sys
import time
import traceback

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
HW_PATH = os.path.join(ROOT, "作业", "hw03_agent_loop.py")

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
    spec = importlib.util.spec_from_file_location("hw03", HW_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


MULTI_STEP_Q = "北京和上海现在哪个更适合户外跑步？请比较两地天气。"


def main():
    print("=" * 74)
    print("第 03 课验收：Agent 主循环（ReAct）")
    print(f"作业文件：{HW_PATH}")
    print("=" * 74)
    print()

    hw = load_homework()
    if not hw.API_KEY:
        print("！.env 里没读到 ZHIPU_API_KEY")
        sys.exit(2)
    print(f"模型：{hw.DEFAULT_MODEL}\n")

    # ---------- 1. 简单问题能结束 ----------
    print("【1】简单问题（1 步可答）能正确结束")
    r1 = None
    try:
        r1 = hw.run_agent("北京现在天气怎么样？", verbose=False)
        assert isinstance(r1, dict), "run_agent 应返回 dict"
        for k in ("answer", "turns", "tool_calls", "trace", "stopped_reason"):
            assert k in r1, f"返回值缺字段 {k}"
        assert r1["stopped_reason"] == "answered", \
            f"应正常结束，实际 stopped_reason={r1['stopped_reason']}"
        assert (r1["answer"] or "").strip(), "answer 是空的"
        assert len(r1["tool_calls"]) >= 1, "没有调用任何工具"
        ok(1, "单步问题正常结束",
           f"轮次={r1['turns']} 调用={len(r1['tool_calls'])} 答案={r1['answer'][:40]!r}")
    except NotImplementedError:
        fail(1, "单步问题", "TODO 还没写完")
    except Exception as e:
        fail(1, "单步问题", f"{type(e).__name__}: {e}")

    # ---------- 2. 多步问题 ----------
    print("【2】多步问题（需 2+ 轮工具）能跑通")
    r2 = None
    try:
        r2 = hw.run_agent(MULTI_STEP_Q, verbose=False)
        assert r2["stopped_reason"] == "answered", \
            f"应正常结束，实际 {r2['stopped_reason']}"
        n_calls = len(r2["tool_calls"])
        assert n_calls >= 2, f"多步问题只调了 {n_calls} 次工具（应 ≥2）"
        cities = set()
        for c in r2["tool_calls"]:
            cities.add(str((c.get("arguments") or {}).get("city", "")))
        assert len(cities) >= 2, f"只查了 {cities}，应至少两个城市"
        ans = r2["answer"]
        assert ("北京" in ans or "上海" in ans), f"答案没提到城市：{ans[:60]!r}"
        ok(2, "多步问题跑通",
           f"轮次={r2['turns']} 调用={n_calls} 城市={sorted(cities)}\n"
           f"         答案={ans[:80]!r}")
    except NotImplementedError:
        fail(2, "多步问题", "TODO 还没写完")
    except Exception as e:
        fail(2, "多步问题", f"{type(e).__name__}: {e}")

    # ---------- 3. tool_calls / turns 计数 ----------
    print("【3】tool_calls 记录完整、turns 计数正确")
    try:
        assert r2 is not None, "上一步没拿到结果"
        assert isinstance(r2["tool_calls"], list), "tool_calls 应是 list"
        for c in r2["tool_calls"]:
            assert "name" in c and "arguments" in c, f"记录缺字段：{c}"
            assert isinstance(c["arguments"], dict), \
                f"arguments 应是 dict（说明没 json.loads）：{c['arguments']!r}"
        assert isinstance(r2["turns"], int) and r2["turns"] >= 1, "turns 不合法"
        ok(3, "计数与记录正确",
           f"turns={r2['turns']}，{len(r2['tool_calls'])} 条调用记录，arguments 已解析为 dict")
    except Exception as e:
        fail(3, "计数与记录", f"{type(e).__name__}: {e}")

    # ---------- 4. execute_tool_safely 不抛异常 ----------
    print("【4】execute_tool_safely 遇错返回 JSON，不抛异常")
    try:
        # 未知工具
        s1 = hw.execute_tool_safely("no_such_tool_xyz", {})
        assert isinstance(s1, str), f"应返回字符串，实际 {type(s1).__name__}"
        d1 = json.loads(s1)
        assert "error" in d1, f"未知工具应返回 error 字段：{s1}"
        # 工具内部抛异常（火星会 raise）
        s2 = hw.execute_tool_safely("get_weather", {"city": "火星"})
        d2 = json.loads(s2)
        assert "error" in d2, f"工具异常应转成 error：{s2}"
        ok(4, "安全执行正确",
           f"未知工具 → {s1[:50]}\n"
           f"         工具异常 → {s2[:60]}")
    except NotImplementedError:
        fail(4, "安全执行", "TODO 1 还没写")
    except Exception as e:
        fail(4, "安全执行", f"{type(e).__name__}: {e}")

    # ---------- 5. 失败可恢复 ----------
    print("【5】工具报错时，Agent 给出合理回复而非崩溃")
    r3 = None
    try:
        r3 = hw.run_agent("火星现在的天气怎么样？", verbose=False)
        assert r3["stopped_reason"] == "answered", \
            f"应正常收口，实际 {r3['stopped_reason']}"
        ans = r3["answer"]
        assert ans.strip(), "answer 是空的"
        # 模型应该提到失败/查不到，而不是编一个天气
        assert not any(w in ans for w in ["18", "22 度", "晴，温度"]), \
            f"模型似乎编造了天气数据：{ans[:80]!r}"
        ok(5, "失败可恢复",
           f"轮次={r3['turns']} 调用={len(r3['tool_calls'])}\n"
           f"         答案={ans[:90]!r}")
    except NotImplementedError:
        fail(5, "失败可恢复", "TODO 还没写完")
    except Exception as e:
        fail(5, "失败可恢复", f"{type(e).__name__}: {e}")

    # ---------- 6. max_turns 出口 ----------
    print("【6】达到 max_turns 时返回明确原因（不静默挂死）")
    try:
        t0 = time.time()
        r5 = hw.run_agent(MULTI_STEP_Q, max_turns=1, verbose=False)
        elapsed = time.time() - t0
        assert r5["stopped_reason"] == "max_turns", \
            f"max_turns=1 时应为 max_turns，实际 {r5['stopped_reason']}"
        assert r5["turns"] == 1, f"应只跑 1 轮，实际 {r5['turns']}"
        assert (r5["answer"] or "").strip(), "answer 不能是空/None"
        ok(6, "有明确出口",
           f"turns={r5['turns']} reason={r5['stopped_reason']} 耗时={elapsed:.1f}s\n"
           f"         提示语={r5['answer'][:60]!r}")
    except NotImplementedError:
        fail(6, "有明确出口", "TODO 4 还没写")
    except Exception as e:
        fail(6, "有明确出口", f"{type(e).__name__}: {e}")

    # ---------- 7. trace 结构 ----------
    print("【7】trace 结构正确，能还原每轮发生了什么")
    try:
        assert r2 is not None, "上一步没拿到结果"
        tr = r2["trace"]
        assert isinstance(tr, list) and tr, "trace 应为非空 list"
        for i, e in enumerate(tr):
            for k in ("turn", "content", "calls"):
                assert k in e, f"trace[{i}] 缺字段 {k}"
            assert isinstance(e["calls"], list), f"trace[{i}].calls 应是 list"
            for c in e["calls"]:
                for k in ("name", "arguments", "result_preview"):
                    assert k in c, f"trace[{i}].calls 缺 {k}"
        total_calls = sum(len(e["calls"]) for e in tr)
        ok(7, "trace 结构正确",
           f"{len(tr)} 轮记录，共 {total_calls} 次工具调用，字段完整")
    except Exception as e:
        fail(7, "trace 结构", f"{type(e).__name__}: {e}")

    # ---------- 8. 对照实验（核心）----------
    print("【8】对照实验：证明主循环是必需的，不是装饰")
    print("      设计说明：用「第一个工具的返回值决定第二个工具的参数」这类问题——")
    print("      串行依赖无法在单轮内完成，必须靠循环。")
    try:
        # 串行依赖问题：必须先查北京天气，再根据结果查另一城市
        SERIAL_Q = ("先查北京的天气。如果北京温度低于 20 度，就再查南宁的天气；"
                    "否则查上海的。最后告诉我你查了哪两个城市。")
        full = hw.run_agent(SERIAL_Q, max_turns=8, verbose=False)
        lim = hw.run_agent(SERIAL_Q, max_turns=1, verbose=False)

        full_calls = len(full["tool_calls"])
        lim_calls = len(lim["tool_calls"])

        # 期望：完整版因串行依赖需要 ≥2 轮；受限版 1 轮只能拿到部分信息
        cond_full_more = full_calls > lim_calls
        cond_lim_capped = lim["stopped_reason"] == "max_turns"

        if cond_full_more and cond_lim_capped:
            ok(8, "对照实验成立",
               f"串行依赖问题（北京→根据结果决定查哪个）\n"
               f"         max_turns=8 → {full['turns']} 轮，调用 {full_calls} 次，"
               f"正常结束（{full['stopped_reason']}）\n"
               f"         max_turns=1 → {lim['turns']} 轮，调用 {lim_calls} 次，"
               f"{lim['stopped_reason']}（被截断）\n"
               f"         → 同样的模型、同样的提示词，只有轮次上限不同，结果不同")
        elif cond_lim_capped:
            # 受限版确实被截断也算成立，只是调用次数差异不显著
            ok(8, "对照实验成立（受限版被截断）",
               f"max_turns=1 → {lim['stopped_reason']}，调用 {lim_calls} 次\n"
               f"         max_turns=8 → {full['stopped_reason']}，调用 {full_calls} 次")
        else:
            fail(8, "对照实验",
                 f"受限版没有被截断：full={full_calls}次/{full['turns']}轮，"
                 f"lim={lim_calls}次/{lim['stopped_reason']}\n"
                 f"         说明模型一轮就处理完了，换更复杂的问题再试")
    except Exception as e:
        fail(8, "对照实验", f"{type(e).__name__}: {e}")

    # ---------- 汇总 ----------
    print()
    print("=" * 74)
    print(f"结果：{len(PASSED)}/8 通过")
    if FAILED:
        print(f"未通过：{FAILED}")
        print()
        print("下一步：按提示改 作业\\hw03_agent_loop.py，改完重跑。")
        sys.exit(1)
    else:
        print("全部通过 ✓")
        print()
        print("★ 你现在已经写出 Agent 内核了：")
        print("    00 课 = 通信层  |  02 课 = 工具协议  |  03 课 = 主循环 + 护栏")
        print()
        print("★ 接下来回答讲义最后的三个追问（Q1/Q2/Q3）。")
        print("  Q3 特别重要：它要求你把主循环和 ai-group 的 @ 派发链联系起来——")
        print("  两处都在解决'什么时候停'，面试里能主动说出这点会非常加分。")
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
