import { call } from './weapi.mjs';
const cookie = process.env.MUSIC_COOKIE;
const tests = [
  ['/weapi/w/point/daily', {type:0}],
  ['/weapi/point/daily', {type:0}],
  ['/weapi/usertool/task/point/receive', {taskId: '3889300'}],
  ['/weapi/w/usertool/task/point/receive', {taskId: '3889300'}],
];
for (const [p, b] of tests) {
  const r = await call(cookie, p, b);
  console.log(p, '->', JSON.stringify(r).slice(0, 220));
  await new Promise(s=>setTimeout(s,1200));
}
