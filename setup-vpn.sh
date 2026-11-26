#!/usr/bin/env bash
# setup-vpn.sh —— 在任意 Debian/Ubuntu VPS（香港/东京/新加坡）上一键起双协议节点
# 用法：
#   1) 上传到服务器：scp setup-vpn.sh root@IP:/root/
#   2) 执行：bash setup-vpn.sh
#   3) 脚本末尾会打印客户端需要的全部参数，复制到 Shadowrocket / NekoBox 即可
#
# 提供两个入口（任选其一，也可以都用）：
#   · Shadowsocks-2022  TCP   —— 稳定、省电、抗封一般
#   · Hysteria2        UDP   —— 抗丢包强、移动网络更快，用自签证书
#
# 只装 sing-box 一个二进制，不带面板，资源占用 ~40MB

set -euo pipefail

echo "=============================================="
echo " 双协议节点一键部署 (sing-box)"
echo "=============================================="

# ---------- 基础 ----------
if [ "$(id -u)" != "0" ]; then echo "请用 root 运行：sudo bash $0"; exit 1; fi
apt-get update -qq
apt-get install -y -qq curl wget openssl qrencode jq >/dev/null 2>&1

ARCH=$(uname -m)
case "$ARCH" in
  x86_64) SB_ARCH="amd64" ;;
  aarch64|arm64) SB_ARCH="arm64" ;;
  *) echo "不支持的架构: $ARCH"; exit 1 ;;
esac

# ---------- 装 sing-box ----------
SB_VER="1.10.7"
if ! command -v sing-box >/dev/null 2>&1; then
  echo "[1/5] 下载 sing-box ${SB_VER} ..."
  curl -fsSL --retry 3 -o /tmp/sb.tar.gz \
    "https://github.com/SagerNet/sing-box/releases/download/v${SB_VER}/sing-box-${SB_VER}-linux-${SB_ARCH}.tar.gz"
  tar -xzf /tmp/sb.tar.gz -C /tmp
  install -m755 "/tmp/sing-box-${SB_VER}-linux-${SB_ARCH}/sing-box" /usr/local/bin/sing-box
fi
sing-box version | head -1

# ---------- 生成参数 ----------
IP=$(curl -s4 --max-time 8 ifconfig.me || curl -s4 --max-time 8 ip.sb || echo "SERVER_IP")
SS_PORT=8443
HY_PORT=8444
SS_PASS=$(openssl rand -base64 18 | tr -d '/+=' | head -c 22)
HY_PASS=$(openssl rand -base64 18 | tr -d '/+=' | head -c 22)
UUID=$(cat /proc/sys/kernel/random/uuid)

echo "[2/5] 生成自签证书（Hysteria2 用）..."
mkdir -p /etc/sing-box
openssl req -x509 -nodes -newkey ec:<(openssl ecparam -name prime256v1) \
  -keyout /etc/sing-box/key.pem -out /etc/sing-box/cert.pem \
  -days 3650 -subj "/CN=${IP}" >/dev/null 2>&1

# ---------- 配置 ----------
echo "[3/5] 写配置..."
cat > /etc/sing-box/config.json <<JSON
{
  "log": { "level": "warn" },
  "inbounds": [
    {
      "type": "shadowsocks",
      "listen": "::",
      "listen_port": ${SS_PORT},
      "method": "2022-blake3-aes-128-gcm",
      "password": "${SS_PASS}"
    },
    {
      "type": "hysteria2",
      "listen": "::",
      "listen_port": ${HY_PORT},
      "users": [ { "password": "${HY_PASS}" } ],
      "masquerade": "https://www.bing.com",
      "tls": {
        "enabled": true,
        "server_name": "${IP}",
        "alpn": ["h3"],
        "certificate_path": "/etc/sing-box/cert.pem",
        "key_path": "/etc/sing-box/key.pem"
      }
    }
  ],
  "outbounds": [ { "type": "direct" } ]
}
JSON

# ---------- 服务 ----------
echo "[4/5] 注册 systemd 服务..."
cat > /etc/systemd/system/sing-box.service <<EOF
[Unit]
Description=sing-box
After=network.target

[Service]
ExecStart=/usr/local/bin/sing-box run -c /etc/sing-box/config.json
Restart=always
RestartSec=3
LimitNOFILE=1048576

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --now sing-box >/dev/null 2>&1
sleep 2
systemctl is-active sing-box

# ---------- 放行 ----------
if command -v ufw >/dev/null 2>&1; then
  ufw allow ${SS_PORT}/tcp >/dev/null 2>&1 || true
  ufw allow ${HY_PORT}/udp >/dev/null 2>&1 || true
fi
if command -v firewall-cmd >/dev/null 2>&1; then
  firewall-cmd --add-port=${SS_PORT}/tcp --permanent >/dev/null 2>&1 || true
  firewall-cmd --add-port=${HY_PORT}/udp --permanent >/dev/null 2>&1 || true
  firewall-cmd --reload >/dev/null 2>&1 || true
fi
echo "提示：云厂商的「安全组」也要单独放行 ${SS_PORT}/tcp 和 ${HY_PORT}/udp"

# ---------- 输出 ----------
echo "[5/5] 完成"
echo
echo "================= 客户端参数 =================="
echo "服务器 IP : ${IP}"
echo
echo "【协议 1】Shadowsocks-2022（TCP，推荐先用这个）"
echo "  类型   : Shadowsocks"
echo "  地址   : ${IP}"
echo "  端口   : ${SS_PORT}"
echo "  加密   : 2022-blake3-aes-128-gcm"
echo "  密码   : ${SS_PASS}"
echo
echo "【协议 2】Hysteria2（UDP，弱网/移动数据更好）"
echo "  类型   : Hysteria2"
echo "  地址   : ${IP}"
echo "  端口   : ${HY_PORT}"
echo "  密码   : ${HY_PASS}"
echo "  SNI    : ${IP}   （允许不安全/跳过证书校验 = 开）"
echo "  混淆   : 关（masquerade 已指向 bing）"
echo
echo "【一键导入链接】"
SS_LINK="ss://$(printf '2022-blake3-aes-128-gcm:%s' "$SS_PASS" | base64 -w0)@${IP}:${SS_PORT}#Liuzhou-SS"
HY_LINK="hysteria2://${HY_PASS}@${IP}:${HY_PORT}/?insecure=1&sni=${IP}#Liuzhou-HY2"
echo "  ${SS_LINK}"
echo "  ${HY_LINK}"
echo
echo "  二维码（手机扫）："
command -v qrencode >/dev/null && qrencode -t ANSIUTF8 "$SS_LINK"
echo "=============================================="
echo "日志：journalctl -u sing-box -f"
echo "配置：/etc/sing-box/config.json"
