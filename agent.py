#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
agent.py —— 最小可用的 DeepSeek Agent 循环（方案 A：走官方 API）

原理：一个 while 循环
  1) 把「任务 + 历史消息 + 工具定义」发给模型
  2) 模型要么直接回答（结束），要么返回 tool_calls（要动手）
  3) 我们执行工具，把结果作为 role=tool 的消息塞回历史
  4) 回到 1，直到没有 tool_calls 或到达步数上限

工具集：
  run_bash(cmd)            在机器上执行 shell（沙箱内）
  read_file(path)          读文本文件
  write_file(path,content) 写文本文件
  http_get(url)            抓网页（返回正文前 8000 字）

用法：
  export DEEPSEEK_API_KEY=sk-xxx
  python3 agent.py "帮我把仓库里的 README 读出来，统计有多少个文件"

依赖：requests
"""
import json
import os
import subprocess
import sys
import textwrap
import urllib.request

API = "https://api.deepseek.com/chat/completions"
MODEL = os.environ.get("AGENT_MODEL", "deepseek-chat")
MAX_STEPS = int(os.environ.get("AGENT_MAX_STEPS", "12"))
MAX_TOOL_OUTPUT = 6000

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "run_bash",
            "description": "在工作目录执行一条 shell 命令，返回 stdout+stderr。用于查看文件、跑脚本、装包。",
            "parameters": {
                "type": "object",
                "properties": {"cmd": {"type": "string", "description": "要执行的命令"}},
                "required": ["cmd"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "读取一个文本文件的内容。",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "写入（覆盖）一个文本文件。父目录不存在会自动创建。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "http_get",
            "description": "GET 一个 URL，返回响应正文（截断到 8000 字符）。",
            "parameters": {
                "type": "object",
                "properties": {"url": {"type": "string"}},
                "required": ["url"],
            },
        },
    },
]


def clip(s: str, n: int = MAX_TOOL_OUTPUT) -> str:
    s = s if isinstance(s, str) else str(s)
    return s if len(s) <= n else s[:n] + f"\n...[截断，原长 {len(s)}]"


def call_tool(name: str, args: dict) -> str:
    try:
        if name == "run_bash":
            p = subprocess.run(
                args["cmd"], shell=True, capture_output=True, text=True, timeout=180
            )
            out = (p.stdout or "") + (p.stderr or "")
            return clip(f"[exit={p.returncode}]\n{out}")
        if name == "read_file":
            with open(args["path"], "r", encoding="utf-8", errors="replace") as f:
                return clip(f.read())
        if name == "write_file":
            path = args["path"]
            d = os.path.dirname(path)
            if d:
                os.makedirs(d, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(args["content"])
            return f"已写入 {path}（{len(args['content'])} 字节）"
        if name == "http_get":
            req = urllib.request.Request(args["url"], headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                body = r.read().decode("utf-8", "replace")
                return clip(f"[HTTP {r.status}]\n{body}")
        return f"未知工具: {name}"
    except subprocess.TimeoutExpired:
        return "[工具超时]"
    except Exception as e:
        return f"[工具报错] {type(e).__name__}: {e}"


def chat(messages, key):
    body = json.dumps(
        {"model": MODEL, "messages": messages, "tools": TOOLS, "temperature": 0.3}
    ).encode()
    req = urllib.request.Request(
        API,
        data=body,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.load(r)


def main():
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not key:
        sys.exit("缺 DEEPSEEK_API_KEY")
    task = " ".join(sys.argv[1:]).strip()
    if not task:
        sys.exit('用法: python3 agent.py "你的任务"')

    messages = [
        {
            "role": "system",
            "content": textwrap.dedent(
                """
                你是一个会动手的 Agent。目标是把任务做完，不是给建议。
                规则：
                - 需要看环境就调 run_bash，不要猜。
                - 一次只做一件明确的事，做完看结果再决定下一步。
                - 全部完成后，用两三句话汇报：做了什么、结果在哪、还有什么没做。
                - 不要输出过程性废话。
                """
            ).strip(),
        },
        {"role": "user", "content": task},
    ]

    for step in range(1, MAX_STEPS + 1):
        resp = chat(messages, key)
        msg = resp["choices"][0]["message"]
        messages.append(msg)

        calls = msg.get("tool_calls") or []
        if not calls:
            print(f"\n=== 第 {step} 步：完成 ===\n")
            print(msg.get("content") or "(空)")
            usage = resp.get("usage", {})
            print(
                f"\n[tokens] prompt={usage.get('prompt_tokens')} "
                f"completion={usage.get('completion_tokens')} "
                f"total={usage.get('total_tokens')}"
            )
            return

        for c in calls:
            name = c["function"]["name"]
            try:
                args = json.loads(c["function"].get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            print(f"\n--- 第 {step} 步 · 工具 {name} · {json.dumps(args, ensure_ascii=False)[:200]}")
            result = call_tool(name, args)
            print(f"    结果: {result[:300].replace(chr(10), ' ')}")
            messages.append(
                {"role": "tool", "tool_call_id": c["id"], "content": result}
            )

    print(f"\n[达到步数上限 {MAX_STEPS}，停止]")




    print("最后一条消息:", json.dumps(messages[-1], ensure_ascii=False)[:800])


if __name__ == "__main__":
    main()
