// weapi 加密 + 调用（Node 版，给本机用）
import crypto from 'node:crypto';

const MOD = BigInt('0x00e0b509f6259df8642dbc35662901477df22677ec152b5ff68ace615bb7b725152b3ab17a876aea8a5aa76d2e417629ec4ee341f56135fccf695280104e0312ecbda92557c93870114af6c9d05c4f7f0c3685b7a46bee255932575cce10b424d813cfe4875d3e82047b97ddef52741d546b8e289dc6935b3ece0462db0a22b8e7');
const PUB = BigInt('0x010001');
const NONCE = Buffer.from('0CoJUm6Qyw8W8jud');
const IV = Buffer.from('0102030405060708');

const aes = (key, data) => {
  const c = crypto.createCipheriv('aes-128-cbc', key, IV);
  return Buffer.concat([c.update(data), c.final()]).toString('base64');
};
const modpow = (b, e, m) => { let r = 1n; b %= m; while (e > 0n) { if (e & 1n) r = r * b % m; b = b * b % m; e >>= 1n; } return r; };

export function weapi(payload) {
  const text = JSON.stringify(payload);
  const key2 = Array.from({ length: 16 }, () => 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'[Math.floor(Math.random() * 62)]).join('');
  const p1 = aes(NONCE, Buffer.from(text));
  const p2 = aes(Buffer.from(key2), Buffer.from(p1));
  const rev = key2.split('').reverse().join('');
  const encSecKey = modpow(BigInt('0x' + Buffer.from(rev).toString('hex')), PUB, MOD).toString(16).padStart(256, '0');
  return new URLSearchParams({ params: p2, encSecKey });
}

export async function call(cookie, path, payload = {}) {
  const csrf = (cookie.match(/__csrf=([^;]+)/) || [])[1] || '';
  const body = weapi({ ...payload, csrf_token: csrf });
  const r = await fetch('https://music.163.com' + path + '?csrf_token=' + csrf, {
    method: 'POST',
    headers: { Cookie: cookie, 'Content-Type': 'application/x-www-form-urlencoded', Referer: 'https://music.163.com/', 'User-Agent': 'Mozilla/5.0' },
    body,
  });
  const t = await r.text();
  try { return { status: r.status, json: JSON.parse(t) }; } catch { return { status: r.status, text: t.slice(0, 300) }; }
}
