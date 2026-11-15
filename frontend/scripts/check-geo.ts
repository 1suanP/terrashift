/**
 * Sanity check: the lat/lon math in src/lib/geo.ts must match three.js SphereGeometry
 * UVs (which place the equirectangular Earth texture). Run: node scripts/check-geo.ts
 */
import * as THREE from 'three';
import { boxAroundPoint, latLonToVector3, vector3ToLatLon } from '../src/lib/geo.ts';

let worst = 0;
const sphere = new THREE.SphereGeometry(1, 72, 36);
const pos = sphere.getAttribute('position');
const uv = sphere.getAttribute('uv');
for (let i = 0; i < pos.count; i++) {
  const v = new THREE.Vector3().fromBufferAttribute(pos, i);
  const lat = uv.getY(i) * 180 - 90;
  const lon = uv.getX(i) * 360 - 180;
  if (Math.abs(lat) > 89.9) continue; // longitude undefined at the poles
  const back = latLonToVector3(lat, lon);
  worst = Math.max(worst, back.distanceTo(v));
  const ll = vector3ToLatLon(v);
  const dLon = Math.abs(((ll.lon - lon + 540) % 360) - 180);
  worst = Math.max(worst, Math.abs(ll.lat - lat) / 90, dLon / 180);
}
console.log(`max mismatch vs SphereGeometry UVs: ${worst.toExponential(2)}`);

const cases: [string, number, number][] = [['San Francisco', 37.77, -122.42], ['Manaus', -3.1, -60], ['Tokyo', 35.68, 139.69], ['Sydney', -33.87, 151.21]];
for (const [name, lat, lon] of cases) {
  const r = vector3ToLatLon(latLonToVector3(lat, lon));
  console.log(`${name.padEnd(14)} ${lat},${lon} -> ${r.lat.toFixed(4)},${r.lon.toFixed(4)}`);
}
console.log('box near pole', JSON.stringify(boxAroundPoint({ lat: 89.9, lon: 179.9 }, 'M2TMNXSLV')));
if (worst > 1e-5) process.exit(1);
