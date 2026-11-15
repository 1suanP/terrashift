/**
 * Colour scales for the data layers on the globe, plus grid helpers.
 * Every layer is painted from real NASA grids (see backend /api/maps).
 */
import type { MapGrid } from '../services/api';

export interface Stop {
  value: number;
  rgb: [number, number, number];
  alpha: number;
}

export interface Palette {
  key: string;
  title: string; // legend title
  short: string; // layer menu label
  units: string;
  stops: Stop[];
  ticks: number[];
  /** values below the first stop are drawn transparent (e.g. no rain) */
  clearBelow: boolean;
  note?: string;
  decimals: number;
}

const s = (value: number, hex: string, alpha: number): Stop => ({
  value,
  rgb: [parseInt(hex.slice(1, 3), 16), parseInt(hex.slice(3, 5), 16), parseInt(hex.slice(5, 7), 16)],
  alpha,
});

export const PALETTES: Record<string, Palette> = {
  'GPM_3IMERGM/precipitation': {
    key: 'GPM_3IMERGM/precipitation',
    title: 'Monthly mean precipitation',
    short: 'Precipitation',
    units: 'mm/day',
    clearBelow: true,
    decimals: 1,
    stops: [
      s(0.5, '#2864d2', 0), s(1, '#286ee1', 0.16), s(3, '#1e96ff', 0.42), s(6, '#00cde6', 0.66),
      s(10, '#37d278', 0.78), s(15, '#b9e13c', 0.84), s(20, '#fad732', 0.9),
    ],
    ticks: [1, 3, 6, 10, 15, 20],
  },
  'M2TMNXSLV/T2M': {
    key: 'M2TMNXSLV/T2M',
    title: 'Monthly mean air temperature (2 m)',
    short: 'Temperature',
    units: '°C',
    clearBelow: false,
    decimals: 1,
    stops: [
      s(-40, '#2a1d6e', 0.72), s(-25, '#2f57c4', 0.72), s(-10, '#4aa6e3', 0.7), s(0, '#a6dff0', 0.66),
      s(10, '#e9e7a0', 0.66), s(20, '#f6b45a', 0.7), s(30, '#e2572f', 0.74), s(40, '#9b1630', 0.78),
    ],
    ticks: [-40, -20, 0, 20, 40],
  },
  'M2TMNXLND/GWETTOP': {
    key: 'M2TMNXLND/GWETTOP',
    title: 'Topsoil moisture (% of saturation)',
    short: 'Soil moisture (topsoil)',
    units: '%',
    clearBelow: false,
    decimals: 0,
    note: 'MERRA-2 land model. Land only.',
    stops: [
      s(0, '#7a4b22', 0.8), s(15, '#b07c3d', 0.8), s(30, '#dcc27a', 0.78), s(45, '#a9d48a', 0.78),
      s(60, '#4fb79a', 0.8), s(80, '#2a83b5', 0.82), s(100, '#1d4f9c', 0.84),
    ],
    ticks: [0, 20, 40, 60, 80, 100],
  },
  'M2TMNXLND/GWETROOT': {
    key: 'M2TMNXLND/GWETROOT',
    title: 'Root-zone soil moisture (% of saturation)',
    short: 'Soil moisture (root zone)',
    units: '%',
    clearBelow: false,
    decimals: 0,
    note: 'Deeper soil changes slowly; in this model it stays near 20–45% even under deserts.',
    stops: [
      s(0, '#7a4b22', 0.8), s(15, '#b07c3d', 0.8), s(30, '#dcc27a', 0.78), s(45, '#a9d48a', 0.78),
      s(60, '#4fb79a', 0.8), s(80, '#2a83b5', 0.82), s(100, '#1d4f9c', 0.84),
    ],
    ticks: [0, 20, 40, 60, 80, 100],
  },
  'M2TMNXFLX/EVAP': {
    key: 'M2TMNXFLX/EVAP',
    title: 'Monthly mean evaporation',
    short: 'Evaporation',
    units: 'mm/day',
    clearBelow: true,
    decimals: 2,
    stops: [
      s(0.2, '#2c1f5c', 0), s(1, '#47308f', 0.42), s(2, '#7a45b8', 0.6), s(3.5, '#bf5fb4', 0.72),
      s(5, '#f08a86', 0.8), s(6.5, '#fbbf7c', 0.85), s(8, '#fff0b3', 0.9),
    ],
    ticks: [1, 2, 4, 6, 8],
  },
};

export const colorFor = (palette: Palette, v: number): [number, number, number, number] => {
  const st = palette.stops;
  if (!Number.isFinite(v)) return [0, 0, 0, 0];
  if (v <= st[0].value) return palette.clearBelow ? [0, 0, 0, 0] : [...st[0].rgb, st[0].alpha];
  const last = st[st.length - 1];
  if (v >= last.value) return [...last.rgb, last.alpha];
  for (let i = 1; i < st.length; i++) {
    if (v <= st[i].value) {
      const a = st[i - 1];
      const b = st[i];
      const t = (v - a.value) / (b.value - a.value);
      return [
        a.rgb[0] + (b.rgb[0] - a.rgb[0]) * t,
        a.rgb[1] + (b.rgb[1] - a.rgb[1]) * t,
        a.rgb[2] + (b.rgb[2] - a.rgb[2]) * t,
        a.alpha + (b.alpha - a.alpha) * t,
      ];
    }
  }
  return [0, 0, 0, 0];
};

/** CSS gradient spanning the legend ticks. */
export const legendGradient = (p: Palette) => {
  const lo = p.ticks[0];
  const hi = p.ticks[p.ticks.length - 1];
  const parts: string[] = [];
  for (let i = 0; i <= 12; i++) {
    const v = lo + ((hi - lo) * i) / 12;
    const [r, g, b] = colorFor(p, Math.max(v, p.clearBelow ? p.stops[1].value : v));
    parts.push(`rgb(${Math.round(r)},${Math.round(g)},${Math.round(b)}) ${((i / 12) * 100).toFixed(0)}%`);
  }
  return `linear-gradient(90deg, ${parts.join(', ')})`;
};

/** Paint a grid (rows south → north) into an equirectangular canvas (north at top, 180°W at left). */
export const paintGrid = (grid: MapGrid, canvas: HTMLCanvasElement, palette: Palette) => {
  canvas.width = grid.lon_count;
  canvas.height = grid.lat_count;
  const ctx = canvas.getContext('2d');
  if (!ctx) return;
  const img = ctx.createImageData(grid.lon_count, grid.lat_count);
  for (let i = 0; i < grid.lat_count; i++) {
    const y = grid.lat_count - 1 - i;
    for (let j = 0; j < grid.lon_count; j++) {
      const v = grid.values[i * grid.lon_count + j];
      if (v === null) continue;
      const o = (y * grid.lon_count + j) * 4;
      const [r, g, b, a] = colorFor(palette, v);
      img.data[o] = r;
      img.data[o + 1] = g;
      img.data[o + 2] = b;
      img.data[o + 3] = a * 255;
    }
  }
  ctx.putImageData(img, 0, 0);
};

/** Nearest grid cell (longitude wraps), or null outside the grid / no data. */
export const sampleGrid = (grid: MapGrid, lat: number, lon: number): number | null => {
  const i = Math.round((lat - grid.lat_start) / grid.lat_step);
  let j = Math.round((lon - grid.lon_start) / grid.lon_step);
  if (i < 0 || i >= grid.lat_count) return null;
  j = ((j % grid.lon_count) + grid.lon_count) % grid.lon_count;
  return grid.values[i * grid.lon_count + j];
};

/** Area-weighted mean over the cells inside a box (empty cells skipped). */
export const meanInBox = (
  grid: MapGrid,
  box: { min_lat: number; max_lat: number; min_lon: number; max_lon: number },
): number | null => {
  const i0 = Math.max(0, Math.ceil((box.min_lat - grid.lat_start) / grid.lat_step));
  const i1 = Math.min(grid.lat_count - 1, Math.floor((box.max_lat - grid.lat_start) / grid.lat_step));
  const j0 = Math.max(0, Math.ceil((box.min_lon - grid.lon_start) / grid.lon_step));
  const j1 = Math.min(grid.lon_count - 1, Math.floor((box.max_lon - grid.lon_start) / grid.lon_step));
  let sum = 0;
  let n = 0;
  for (let i = i0; i <= i1; i++) {
    const w = Math.cos(((grid.lat_start + i * grid.lat_step) * Math.PI) / 180);
    for (let j = j0; j <= j1; j++) {
      const v = grid.values[i * grid.lon_count + j];
      if (v !== null) {
        sum += v * w;
        n += w;
      }
    }
  }
  return n > 0 ? sum / n : sampleGrid(grid, (box.min_lat + box.max_lat) / 2, (box.min_lon + box.max_lon) / 2);
};

export const MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
