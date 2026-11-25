"""
mitm_vip.py —— mitmproxy 插件：把网易云接口里的 vipType 改成 11（黑胶 VIP）

用法:
    mitmdump -s mitm_vip.py -p 8080
    # 手机 WiFi 代理指向 <电脑IP>:8080，浏览器访问 mitm.it 装证书
    # 网易云 App 对证书校验较严；PC 客户端更容易生效

效果:
    - /api/nuser/account/get 返回的 profile.vipType -> 11
    - /api/v1/user/detail 等接口里的 vipType -> 11
    - 个人页/头像旁出现 VIP 标识

不能做的:
    - 不能解锁 320k/无损（服务端按权益签名，改返回没用）
    - 不能解锁付费下载
    - 不能去广告（广告位是另一个接口）

强刷注意: 改得太狠（比如把 level 也拉到 10、把 expireTime 拉到 2099）
容易触发客户端本地校验失败，表现为"个人信息加载失败"。只改 vipType 最稳。
"""
import json
from mitmproxy import http

TARGET_HOSTS = ("music.163.com", "interface.music.163.com", "client.music.163.com")
VIP_TYPE = 11  # 11 = 黑胶VIP, 100 = 音乐包, 0 = 普通


def _patch_obj(obj):
    """递归找 vipType 字段并替换"""
    if isinstance(obj, dict):
        for k, v in list(obj.items()):
            if k == "vipType":
                obj[k] = VIP_TYPE
            elif k in ("vipRights", "associator", "musicPackage"):
                # 这几个子对象里也有标识位
                if isinstance(v, dict):
                    if "vipCode" in v:
                        v["vipCode"] = 100
                    if "rights" in v:
                        v["rights"] = True
                    if "isSign" in v:
                        v["isSign"] = True
                _patch_obj(v)
            else:
                _patch_obj(v)
    elif isinstance(obj, list):
        for item in obj:
            _patch_obj(item)


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
    before = json.dumps(data, ensure_ascii=False)
    _patch_obj(data)
    after = json.dumps(data, ensure_ascii=False)
    if before != after:
        flow.response.set_text(after)
        print(f"[patched] {flow.request.method} {flow.request.path}")
