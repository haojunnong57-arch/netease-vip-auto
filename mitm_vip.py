"""
mitm_vip.py —— 让网易云客户端把会员"显示"成到 2033-12-31

不改变服务端事实：到期时间、权益签名都在云端。
作用范围：只影响经过这个代理的这一台设备上的显示。

iOS 用法（iPhone 自己跑不了 mitmproxy，但可以当客户端）：
  1) 在一台电脑 / 树莓派 / 云服务器上跑：
        pip install mitmproxy
        mitmdump -s mitm_vip.py -p 8080 --set confdir=~/.mitmproxy
  2) 生成 CA：浏览器访问 http://<代理机IP>:8080/mitm.it 下载描述文件
  3) iPhone：设置 → 通用 → VPN与设备管理 → 安装描述文件
             设置 → 通用 → 关于本机 → 证书信任设置 → 打开 mitmproxy 的开关
  4) iPhone：设置 → Wi-Fi → 当前网络 → 配置代理 → 手动
             server = <代理机IP>, port = 8080
  5) 打开网易云，进"我的"，看会员卡片

注意：网易云 App 对证书有校验（SSL Pinning 的松紧随版本变）。
如果连不上网，先关掉代理确认网络正常，再试 PC 客户端（PC 版没有 pinning）。
"""
import json
import time

from mitmproxy import http

TARGET_HOSTS = ("music.163.com", "interface.music.163.com", "client.music.163.com")
VIP_TYPE = 11                     # 11 = 黑胶VIP
EXPIRE_MS = 1993353600000         # 2033-02-28 00:00:00 UTC (毫秒)
EXPIRE_STR = "2033-02-28"


def _patch(obj):
    if isinstance(obj, dict):
        for k, v in list(obj.items()):
            if k == "vipType":
                obj[k] = VIP_TYPE
            elif k in ("expireTime", "vipExpireTime", "expiretime", "vipExpire"):
                # 毫秒时间戳
                if isinstance(v, (int, float)):
                    obj[k] = EXPIRE_MS
            elif k == "expireTimeStr":
                obj[k] = EXPIRE_STR
            elif k == "associator":
                if isinstance(v, dict):
                    v["vipCode"] = 100
                    v["expireTime"] = EXPIRE_MS
                    if "rights" in v:
                        v["rights"] = True
                    if "isSign" in v:
                        v["isSign"] = True
                _patch(v)
            elif k == "vipRights":
                if isinstance(v, dict):
                    v["redVipAnnualCount"] = 10
                    v["redVipLevel"] = 10
                    for r in v.get("musicPackage", {}).get("vipCode", []) if isinstance(v.get("musicPackage"), dict) else []:
                        pass
                _patch(v)
            else:
                _patch(v)
    elif isinstance(obj, list):
        for item in obj:
            _patch(item)


def response(flow: http.HTTPFlow) -> None:
    if not any(h in flow.request.pretty_host for h in TARGET_HOSTS):
        return
    ctype = flow.response.headers.get("content-type", "")
    if "json" not in ctype:
        return
    try:
        data = json.loads(flow.response.get_text())
    except Exception:
        return
    before = json.dumps(data, sort_keys=True, ensure_ascii=False)
    _patch(data)
    after = json.dumps(data, sort_keys=True, ensure_ascii=False)
    if before != after:
        flow.response.set_text(json.dumps(data, ensure_ascii=False))
        print(f"[patched] {flow.request.method} {flow.request.path}")


def load(l):
    print(f"[mitm_vip] 已加载，目标到期时间 {EXPIRE_STR}，启动于 {time.strftime('%Y-%m-%d %H:%M:%S')}")
