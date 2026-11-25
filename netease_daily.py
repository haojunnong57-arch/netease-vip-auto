#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
netease_daily.py —— 网易云音乐会员自动化（签到 / 云贝 / 任务 / 兑换）

路径说明：会员不是"破解"出来的，是攒出来的。网易云给会员的实际免费口子有四个：
  1. 每日签到 → 云贝，云贝商城可兑会员天数（7 天/30 天券）
  2. 每日任务（听歌、评论、分享）→ 云贝 + 会员天数
  3. 新用户/活动任务 → 直接送 VIP 天数
  4. 学生认证 → 免费/半价
本脚本把 1、2 全自动化，跑满一个月够换一次 7 天券；顺手把"领取任务奖励"也做掉。

依赖:
    pip install requests pycryptodome

配置:
    export MUSIC_U='你的 MUSIC_U cookie 值'      # 必须
    export MUSIC_A='你的 MUSIC_A cookie 值'      # 建议一起给
    export CSRF='你的 __csrf 值'                  # 有就给，没有留空

拿 cookie 的办法:
    浏览器登录 music.163.com → F12 → Application → Cookies → music.163.com
    复制 MUSIC_U / MUSIC_A / __csrf 三个值
    （手机 App 的 token 是另一个体系，不要混用）

用法:
    python3 netease_daily.py            # 签到 + 跑任务 + 领奖励
    python3 netease_daily.py --status   # 只看当前状态和云贝余额
    python3 netease_daily.py --exchange 190    # 用云贝兑换会员（goodsId 见下方表）
"""
import os
import sys
import json
import time
import random
import string
import base64
import argparse

import requests
from Crypto.Cipher import AES

# ---------------------------------------------------------------- weapi 加密
MODULUS = (
    "00e0b509f6259df8642dbc35662901477df22677ec152b5ff68ace615bb7b7251"
    "52b3ab17a876aea8a5aa76d2e417629ec4ee341f56135fccf695280104e0312ec"
    "bda92557c93870114af6c9d05c4f7f0c3685b7a46bee255932575cce10b424d8"
    "13cfe4875d3e82047b97ddef52741d546b8e289dc6935b3ece0462db0a22b8e7"
)
PUBKEY = "010001"
NONCE = b"0CoJUm6Qyw8W8jud"
IV = b"0102030405060708"


def _aes(text: bytes, key: bytes) -> bytes:
    pad = 16 - len(text) % 16
    text = text + bytes([pad]) * pad
    return base64.b64encode(AES.new(key, AES.MODE_CBC, IV).encrypt(text))


def _rsa(text: bytes) -> str:
    rev = text[::-1]
    rs = pow(int(rev.hex(), 16), int(PUBKEY, 16), int(MODULUS, 16))
    return format(rs, "x").zfill(256)


def weapi(payload: dict) -> dict:
    text = json.dumps(payload, separators=(",", ":")).encode()
    sec = "".join(random.choices(string.ascii_letters + string.digits, k=16)).encode()
    params = _aes(_aes(text, NONCE), sec).decode()
    enc = _rsa(sec)
    return {"params": params, "encSecKey": enc}


# ---------------------------------------------------------------- 会话
class Client:
    BASE = "https://music.163.com"

    def __init__(self):
        self.s = requests.Session()
        self.s.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
                ),
                "Referer": "https://music.163.com/",
                "Origin": "https://music.163.com",
            }
        )
        music_u = os.environ.get("MUSIC_U", "").strip()
        if not music_u:
            sys.exit("缺 MUSIC_U，先看文件开头说明怎么拿 cookie")
        self.s.cookies.set("MUSIC_U", music_u, domain=".music.163.com")
        if os.environ.get("MUSIC_A", "").strip():
            self.s.cookies.set("MUSIC_A", os.environ["MUSIC_A"].strip(), domain=".music.163.com")
        self.csrf = os.environ.get("CSRF", "").strip()

    def post(self, path: str, payload: dict | None = None) -> dict:
        payload = dict(payload or {})
        payload.setdefault("csrf_token", self.csrf)
        url = f"{self.BASE}{path}"
        r = self.s.post(url, data=weapi(payload), timeout=15)
        r.raise_for_status()
        return r.json()

    def get(self, path: str, params: dict | None = None) -> dict:
        url = f"{self.BASE}{path}"
        r = self.s.get(url, params=params or {}, timeout=15)
        r.raise_for_status()
        return r.json()

    # ---------------- 状态
    def account(self) -> dict:
        data = self.get("/api/nuser/account/get")
        p = (data or {}).get("profile") or {}
        return {
            "nickname": p.get("nickname"),
            "userId": p.get("userId"),
            "vipType": p.get("vipType"),
            "level": p.get("level"),
        }

    def cloudbean(self) -> dict:
        data = self.get("/api/point/signed/get")
        return data

    # ---------------- 签到
    def sign_in(self) -> dict:
        return self.post("/weapi/point/daily")

    # ---------------- 任务
    def task_list(self) -> dict:
        return self.post("/weapi/usertool/task/list/all", {"csrf_token": self.csrf})

    def claim(self, task_id: str | int) -> dict:
        return self.post(
            "/weapi/usertool/task/point/receive",
            {"taskId": str(task_id), "csrf_token": self.csrf},
        )

    # ---------------- 听歌上报（做"听歌任务"用；不做也无妨）
    def report_listen(self, song_id: int, play_ts: int | None = None) -> dict:
        now = play_ts or int(time.time() * 1000)
        return self.post(
            "/weapi/feedback/weblog",
            {
                "logs": json.dumps(
                    [
                        {
                            "action": "play",
                            "json": {
                                "id": song_id,
                                "type": "song",
                                "mainsite": "1",
                                "mainsite": "1",
                                "download": "0",
                                "vipType": "0",
                            },
                            "time": now,
                        }
                    ]
                )
            },
        )

    # ---------------- 云贝兑换会员
    # 云贝商城常见 goodsId（会变，用 --goods 查实时列表最稳）：
    #   190  会员 7 天券
    #   191  会员 30 天券
    #   195  黑胶 VIP 7 天
    def goods_list(self) -> dict:
        return self.post("/weapi/cloudbean/goods/list", {"csrf_token": self.csrf})

    def exchange(self, goods_id: int, num: int = 1) -> dict:
        return self.post(
            "/weapi/cloudbean/exchange",
            {"goodsId": str(goods_id), "num": str(num), "csrf_token": self.csrf},
        )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--status", action="store_true", help="只看状态")
    ap.add_argument("--exchange", type=int, default=0, help="云贝兑换的 goodsId")
    ap.add_argument("--goods", action="store_true", help="列出云贝商城商品")
    args = ap.parse_args()

    c = Client()

    acc = c.account()
    if not acc.get("userId"):
        sys.exit("登录态无效，MUSIC_U 过期了，重新拿一次")

    print(f"账号: {acc['nickname']}  uid={acc['userId']}  vipType={acc['vipType']}  lv={acc['level']}")
    print(f"云贝: {json.dumps(c.cloudbean(), ensure_ascii=False)[:300]}")

    if args.status:
        return

    if args.goods:
        print(json.dumps(c.goods_list(), ensure_ascii=False, indent=2)[:3000])
        return

    if args.exchange:
        print("兑换结果:", json.dumps(c.exchange(args.exchange), ensure_ascii=False))
        return

    print("\n== 签到 ==")
    print(json.dumps(c.sign_in(), ensure_ascii=False))
    time.sleep(1.2)

    print("\n== 任务列表 ==")
    tasks = c.task_list()
    print(json.dumps(tasks, ensure_ascii=False)[:1200])
    time.sleep(1.0)

    print("\n== 领取可领奖励 ==")
    try:
        for item in (tasks.get("data") or {}).get("list") or []:
            tid = item.get("taskId")
            done = item.get("status") in (2, "2", True)
            got = item.get("rewarded") in (1, "1", True)
            if tid and done and not got:
                print(f"  task {tid} ->", json.dumps(c.claim(tid), ensure_ascii=False))
                time.sleep(1.5)
    except Exception as e:
        print("  领取阶段出错:", e)

    print("\n完成。云贝到 1000 左右去 --goods 看有没有会员券，再 --exchange <goodsId> 兑。")


if __name__ == "__main__":
    main()
