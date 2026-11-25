# netease-vip-auto

网易云音乐 **每日签到 / 云贝 / 任务自动化**。跑在 GitHub Actions 上，**iPhone 上什么都不用装**。

> 说明：这个仓库不会让账号变成 VIP。它做的是把「签到、领云贝、领任务奖励」自动化，
> 云贝攒够了自己去商城换 7 天 / 30 天会员券。真会员只有这一条free路径。

---

## 一、iPhone（iOS 27）怎么用

**核心思路：脚本不跑在手机上，跑在 GitHub 的服务器上。**

1. 打开 GitHub App 或 Safari，进这个仓库 → **Settings → Secrets and variables → Actions**
2. 新建三个 secret：

| Name | Value | 必填 |
|---|---|---|
| `MUSIC_U` | 网易云 cookie 里 MUSIC_U 的值 | ✅ |
| `MUSIC_A` | cookie 里的 MUSIC_A | 建议 |
| `CSRF` | cookie 里的 `__csrf` | 建议 |

3. 进 **Actions → netease-daily → Run workflow** 手动跑一次，看日志
4. 之后每天北京时间 08:10 自动跑

**怎么拿 cookie（手机上就能做）**
- 手机浏览器打开 `music.163.com` 并登录
- 换成桌面版（Safari 地址栏左边的「ᴀA」→ 请求桌面网站）
- 需要看 cookie 的话：用 Mac/PC 的浏览器 F12 最稳；纯手机端可以用 Scriptable 或「快捷指令」里的 `获取网页内容` + 手动登录后从共享 cookie 读——不折腾的话，电脑上复制一次粘到 GitHub  secret 里就完事

---

## 二、手机上「点一下就跑」

GitHub App 里进 Actions → 选 `netease-daily` → Run workflow。这就是最省事的按钮。

想更省事，用 **快捷指令** 做个桌面图标，直接调 GitHub API：

```
POST https://api.github.com/repos/haojunnong57-arch/netease-vip-auto/actions/workflows/daily.yml/dispatches
Headers:
  Authorization: Bearer <你的 PAT，fine-grained，Actions:write>
  Accept: application/vnd.github+json
Body: {"ref":"main"}
```

快捷指令步骤：
1. `获取 URL 内容`
2. URL 填上面那串
3. 方法选 **POST**
4. 请求头加 `Authorization` = `Bearer xxx`，`Accept` = `application/vnd.github+json`
5. 请求体选 **JSON**，`ref` = `main`
6. 存成「签到」图标放桌面

点一下 → GitHub 服务器跑脚本 → 你手机不用装 Python。

---

## 三、电脑上跑（可选）

```bash
pip install requests pycryptodome
export MUSIC_U='...'
python netease_daily.py --status     # 看状态和云贝
python netease_daily.py              # 签到 + 任务 + 领奖
python netease_daily.py --goods      # 看云贝商城有什么券
python netease_daily.py --exchange 190   # 兑换
```

---

## 四、为什么手机上不能直接跑

- `pycryptodome`（RSA/AES）在 iOS 的 Python 环境里装不上，weapi 加密过不去
- `mitmproxy` 需要监听端口 + 装证书，iOS 沙盒不允许
- 所以：**加密计算放云端（Actions），手机只做触发和看结果**

---

## 五、会员的三条真实路线

| 路线 | 结果 | 说明 |
|---|---|---|
| A 任务自动化（本仓库） | 真会员 | 云贝换券，慢但真 |
| B 显示补丁 | 只改图标 | 需要 mitmproxy，iOS 上做不了 |
| C 音源替换 | 能听高音质 | 需自建服务，参考 UnblockNeteaseMusic |

---

## 六、注意

- `MUSIC_U` 等于登录态，**只放 GitHub Secrets，别写进代码**
- 别改签到以外的接口，风控阈值很低
- 请求间隔保持 1 秒以上
