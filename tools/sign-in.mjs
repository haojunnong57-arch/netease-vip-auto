import { call } from './weapi.mjs';
const cookie = process.env.MUSIC_COOKIE;
if (!cookie) { console.error('缺 MUSIC_COOKIE'); process.exit(1); }
const before = await (await fetch('https://music.163.com/api/point/signed/get', { headers: { Cookie: cookie } })).json();
const res = await call(cookie, '/weapi/point/daily', { type: 0 });
const after = await (await fetch('https://music.163.com/api/point/signed/get', { headers: { Cookie: cookie } })).json();
console.log(JSON.stringify({ before, signResult: res, after }, null, 2).slice(0, 1200));
