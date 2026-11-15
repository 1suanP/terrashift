/**
 * Geographic helpers shared by the globe and the panels.
 *
 * The globe uses three.js SphereGeometry UV mapping with an equirectangular texture
 * whose left edge is 180°W, so:
 *   phi   = (lon + 180)° , theta = (90 - lat)°
 *   x = -cos(phi)·sin(theta),  y = cos(theta),  z = sin(phi)·sin(theta)
 */
import * as THREE from 'three';

export interface LatLon {
  lat: number;
  lon: number;
}

export interface BBox {
  min_lat: number;
  max_lat: number;
  min_lon: number;
  max_lon: number;
}

const DEG = Math.PI / 180;

export const latLonToVector3 = (lat: number, lon: number, radius = 1): THREE.Vector3 => {
  const phi = (lon + 180) * DEG;
  const theta = (90 - lat) * DEG;
  return new THREE.Vector3(
    -radius * Math.cos(phi) * Math.sin(theta),
    radius * Math.cos(theta),
    radius * Math.sin(phi) * Math.sin(theta),
  );
};

export const vector3ToLatLon = (p: THREE.Vector3): LatLon => {
  const n = p.clone().normalize();
  const lat = Math.asin(THREE.MathUtils.clamp(n.y, -1, 1)) / DEG;
  const phiDeg = Math.atan2(n.z, -n.x) / DEG;
  const lon = ((phiDeg - 180 + 540) % 360) - 180;
  return { lat, lon };
};

export const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));

/** Box spanning two dragged corners. Dragging across the dateline is not supported. */
export const boxFromCorners = (a: LatLon, b: LatLon): BBox => ({
  min_lat: Math.min(a.lat, b.lat),
  max_lat: Math.max(a.lat, b.lat),
  min_lon: Math.min(a.lon, b.lon),
  max_lon: Math.max(a.lon, b.lon),
});

/**
 * Small box around a clicked point, big enough to contain at least one grid cell of
 * the dataset (GPM 0.1°, MERRA-2 0.5° × 0.625°).
 */
export const boxAroundPoint = (p: LatLon, datasetKey: string): BBox => {
  const half = datasetKey === 'GPM_3IMERGM' ? 0.25 : 0.5;
  return {
    min_lat: clamp(p.lat - half, -90, 90 - 2 * half),
    max_lat: clamp(p.lat + half, -90 + 2 * half, 90),
    min_lon: clamp(p.lon - half, -180, 180 - 2 * half),
    max_lon: clamp(p.lon + half, -180 + 2 * half, 180),
  };
};

export const boxCenter = (b: BBox): LatLon => ({
  lat: (b.min_lat + b.max_lat) / 2,
  lon: (b.min_lon + b.max_lon) / 2,
});

export const boxSpan = (b: BBox) => Math.max(b.max_lat - b.min_lat, (b.max_lon - b.min_lon) * Math.cos(boxCenter(b).lat * DEG));

export const formatLat = (lat: number) => `${Math.abs(lat).toFixed(2)}°${lat >= 0 ? 'N' : 'S'}`;
export const formatLon = (lon: number) => `${Math.abs(lon).toFixed(2)}°${lon >= 0 ? 'E' : 'W'}`;
export const formatLatLon = (p: LatLon) => `${formatLat(p.lat)}, ${formatLon(p.lon)}`;
export const formatBox = (b: BBox) =>
  `${formatLat(b.min_lat)} – ${formatLat(b.max_lat)}, ${formatLon(b.min_lon)} – ${formatLon(b.max_lon)}`;
