# 网易云 VIP：三条真实可行路线

> 结论前置：**没有任何脚本能"直接领到"会员。** 服务端权益校验在云端，你在本地改什么都不会让账号真的变成 VIP。
> 能做到的是三件事：①把攒云贝的活自动化 ②把客户端"显示"改成 VIP ③用第三方音源绕过音质/下载限制。

---

## 路线 A：任务自动化（唯一能让人真变成会员的路）

见 `netease_daily.py`。核心逻辑：

| 动作 | 接口 | 收益 |
|---|---|---|
| 签到 | `POST /weapi/point/daily` | 云贝 +5~30 |
| 任务列表 | `POST /weapi/usertool/task/list/all` | 看今日任务 |
| 领奖励 | `POST /weapi/usertool/task/point/receive` | 云贝/天数 |
| 兑换 | `POST /weapi/cloudbean/exchange` | 云贝 → 会员券（7天/30天） |

跑满一个月的量级：云贝 600–1200，够换 1 张 7 天券。**这是慢的，但它是真的。**

学生的话有更快的口子：`music.163.com` → 会员中心 → 学生认证，直接半价甚至免费送。

---

## 路线 B：本地改"显示"（vipType 补丁）

原理：客户端画面上那个"VIP"标识来自 `/api/nuser/account/get` 返回的 `vipType` 字段。把它改成 11（黑胶VIP）或 100（音乐包），图标就变。**但下载/音质/去广告这些都要服务端二次校验，改了也不生效。**

用 mitmproxy 拦截改写（电脑端，手机走同一 Wi-Fi + 装证书）：

```bash
pip install mitmproxy
mitmdump -s mitm_vip.py -p 8080
```

`mitm_vip.py` 见同目录。手机把代理指向 `<你的电脑IP>:8080`，装 mitm.it 的证书。

效果：客户端头像/昵称旁边出现 VIP 标，个人页显示黑胶。仅此而已。

**能骗到什么程度**：截图骗人够用；真听 320k/无损，播不出来。

---

## 路线 C：音源替换（真正能听高音质的路）

思路不是破解网易云的加密，而是**不用它的音源**：识别歌单里的 songId，去别的平台（QQ/酷狗/咪咕/YouTube/B站）搜同名音频，把播放地址换掉。这条路的代表项目是 UnblockNeteaseMusic，思路完全公开。

自己写一个最小版：

```python
# unblock_min.py —— 给网易云客户端/其它播放器用的替换层示意
import requests

SOURCES = {
    "qq": "https://c.y.qq.com/soso/fcgi-bin/client_search_cp?w={kw}&format=json",
    "kugou": "https://mobilecdn.kugou.com/api/v3/search/song?keyword={kw}&page=1&pagesize=5",
}

def find_elsewhere(title: str, artist: str):
    kw = f"{title} {artist}"
    out = []
    for name, tpl in SOURCES.items():
        try:
            r = requests.get(tpl.format(kw=requests.utils.quote(kw)), timeout=8,
                             headers={"User-Agent": "Mozilla/5.0", "Referer": "https://y.qq.com/"})
            out.append((name, r.status_code, len(r.text)))
        except Exception as e:
            out.append((name, "err", str(e)[:60]))
    return out

if __name__ == "__main__":
    print(find_elsewhere("晴天", "周杰伦"))
```

真正的替换要做的三件事：
1. 网易云客户端把 `/api/song/enhance/player/url` 的请求指到你本地服务
2. 你本地服务返回别的平台的直链（`url` 字段）
3. 客户端直接播那个 URL（它不校验来源）

现成方案搜 `UnblockNeteaseMusic` / `NeteaseCloudMusicApi` 两个项目，配置比手写省一天。手机端配法：局域网找台机器跑服务，客户端用 Hosts + 证书劫持，或者直接用第三方客户端（YesPlayMusic 之类）。

---

## 路线对比

| | 真会员 | 耗时 | 风险 |
|---|---|---|---|
| A 任务脚本 | 是 | 慢（月级） | 低（就是官方任务） |
| B 显示补丁 | 否 | 10 分钟 | 中（客户端可能校验失败/封号） |
| C 音源替换 | 否 | 半天 | 中（第三方源随时挂） |

**说实话**：A + C 组合是最实用的——会员天数慢慢攒（签到脚本挂着不管），想听的歌用 C 从别的源拿。B 只适合发朋友圈。

---

## 免责边界（写给自己看的）

- cookie 别外传，MUSIC_U 等于你的登录态
- 别用脚本去刷签到以外的接口（风控阈值很低，一天几十次就锁）
- 请求间隔保持 1 秒以上，别并发
- 账号被风控了要人脸验证，得不偿失
