/** Run: node scripts/check-coordinates.ts  (exits 1 on any failure) */
import { parseCoordinates } from '../src/lib/coordinates.ts';

const close = (a: number, b: number) => Math.abs(a - b) < 1e-3;
const ok: [string, number, number][] = [
  ['3.139, 101.687', 3.139, 101.687],
  ['3.139 101.687', 3.139, 101.687],
  ['-33.87;151.21', -33.87, 151.21],
  ['51.5074, -0.1278', 51.5074, -0.1278],
  ['3.139N 101.687E', 3.139, 101.687],
  ['3.139° N, 101.687° E', 3.139, 101.687],
  ['N3.139 E101.687', 3.139, 101.687],
  ['101.687E 3.139N', 3.139, 101.687],
  ['3°08\'20"N 101°41\'13"E', 3.13889, 101.68694],
  ['51°30′N 0°7′W', 51.5, -0.11667],
  ['33.87S 151.21E', -33.87, 151.21],
  ['lat 3.1 lon 101.6', 3.1, 101.6],
  ['101.687, 3.139', 3.139, 101.687], // lon first, unambiguous because 101 > 90
  ['(40.7128, -74.0060)', 40.7128, -74.006],
  ['95, 10', 10, 95], // 95 cannot be a latitude, so read as "lon, lat" (UI says so)
];
const bad = ['Kuala Lumpur', 'London', '95, 200', '10, 200', '3.1', '1 2 3', '-3N 10E', '3°70\'N 10E', 'asdfqwerzxcv', ''];

let fail = 0;
for (const [text, lat, lon] of ok) {
  const r = parseCoordinates(text);
  const pass = r !== null && close(r.lat, lat) && close(r.lon, lon);
  if (!pass) fail++;
  console.log(`${pass ? 'ok  ' : 'FAIL'} ${JSON.stringify(text).padEnd(28)} -> ${r ? `${r.lat.toFixed(4)}, ${r.lon.toFixed(4)}${r.swapped ? ' (swapped)' : ''}` : 'null'}`);
}
for (const text of bad) {
  const r = parseCoordinates(text);
  if (r !== null) fail++;
  console.log(`${r === null ? 'ok  ' : 'FAIL'} ${JSON.stringify(text).padEnd(28)} -> ${r ? `${r.lat}, ${r.lon}` : 'rejected'}`);
}
console.log(fail ? `${fail} failures` : 'all passed');
process.exit(fail ? 1 : 0);
