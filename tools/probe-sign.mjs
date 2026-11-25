const cookie = process.env.MUSIC_COOKIE;
const csrf = (cookie.match(/__csrf=([^;]+)/)||[])[1] || '';
const H = { Cookie: cookie, Referer: 'https://music.163.com/', 'User-Agent': 'Mozilla/5.0', 'Content-Type': 'application/x-www-form-urlencoded' };
const tries = [
  ['POST', '/api/point/daily', 'type=0&csrf_token=' + csrf],
  ['POST', '/api/point/daily', ''],
  ['POST', '/weapi/point/daily', null],   // 需要加密，跳过
  ['GET',  '/api/point/daily?type=0', null],
  ['POST', '/api/point/spring/sign', 'csrf_token=' + csrf],
];
for (const [m, p, body] of tries) {
  try {
    if (body === null) { console.log(m, p, '-> skip(needs weapi)'); continue; }
    const r = await fetch('https://music.163.com' + p, { method: m, headers: H, body: m === 'POST' ? body : undefined });
    const t = await r.text();
    console.log(m, p, r.status, t.slice(0, 200).replace(/\n/g, ' '));
  } catch (e) { console.log(m, p, 'ERR', String(e).slice(0, 100)); }
  await new Promise(r => setTimeout(r, 800));
}
