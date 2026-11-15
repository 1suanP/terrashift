/**
 * Parse typed coordinates, latitude first. Accepts for example:
 *   3.139, 101.687        3.139 101.687        -33.87;151.21
 *   3.139N 101.687E       3.139° N, 101.687° E  N3.139 E101.687
 *   3°08'20"N 101°41'13"E 51°30′N 0°7′W       lat 3.1 lon 101.6
 * Returns null when the text is not a coordinate pair or is out of range.
 */
export interface ParsedCoordinates {
  lat: number;
  lon: number;
  swapped: boolean; // true when the text looked like "lon, lat" and was flipped
}

interface Part {
  value: number;
  hemi: 'N' | 'S' | 'E' | 'W' | null;
}

const NUM = String.raw`[+-]?\d+(?:\.\d+)?`;
const PART = new RegExp(
  String.raw`^\s*([NSEW])?\s*(${NUM})\s*(?:[°º˚d]\s*(?:(\d+(?:\.\d+)?)\s*['′’m]\s*(?:(\d+(?:\.\d+)?)\s*(?:["″”]|'')?\s*)?)?)?\s*([NSEW])?\s*$`,
  'i',
);

const parsePart = (text: string): Part | null => {
  const m = PART.exec(text);
  if (!m) return null;
  const [, pre, deg, min, sec, post] = m;
  if (pre && post) return null;
  const minutes = min ? Number(min) : 0;
  const seconds = sec ? Number(sec) : 0;
  if (minutes >= 60 || seconds >= 60) return null;
  let value = Math.abs(Number(deg)) + minutes / 60 + seconds / 3600;
  if (deg.trim().startsWith('-')) value = -value;
  const hemi = ((pre || post || '').toUpperCase() || null) as Part['hemi'];
  if (hemi && deg.trim().startsWith('-')) return null; // "-3N" is contradictory
  if (hemi === 'S' || hemi === 'W') value = -value;
  return { value, hemi };
};

/** Split into exactly two coordinate parts. */
const splitParts = (text: string): [string, string] | null => {
  const cleaned = text
    .trim()
    .replace(/\b(lat(itude)?|lon(gitude)?|lng)\s*[:=]?\s*/gi, ' ')
    .replace(/[()[\]]/g, ' ')
    .trim();
  for (const sep of [/\s*[,;/]\s*/, /(?<=[NSEW])\s+(?=[-+\dNSEW])/i]) {
    const parts = cleaned.split(sep).filter(Boolean);
    if (parts.length === 2) return [parts[0], parts[1]];
  }
  // plain whitespace: "3.139 101.687" or "3 08 N 101 41 E" is not supported, keep it simple
  const ws = cleaned.split(/\s+/).filter(Boolean);
  if (ws.length === 2) return [ws[0], ws[1]];
  return null;
};

export const parseCoordinates = (text: string): ParsedCoordinates | null => {
  if (!/\d/.test(text) || text.length > 60) return null;
  const parts = splitParts(text);
  if (!parts) return null;
  const a = parsePart(parts[0]);
  const b = parsePart(parts[1]);
  if (!a || !b) return null;

  // Hemisphere letters decide the order when present
  if ((a.hemi === 'E' || a.hemi === 'W') && (b.hemi === 'N' || b.hemi === 'S' || b.hemi === null)) {
    return valid(b.value, a.value, true);
  }
  if (a.hemi === 'N' || a.hemi === 'S' || b.hemi === 'E' || b.hemi === 'W') return valid(a.value, b.value, false);
  if (Math.abs(a.value) > 90 && Math.abs(b.value) <= 90) return valid(b.value, a.value, true);
  return valid(a.value, b.value, false);
};

const valid = (lat: number, lon: number, swapped: boolean): ParsedCoordinates | null => {
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) return null;
  if (Math.abs(lat) > 90 || Math.abs(lon) > 180) return null;
  return { lat, lon: lon === 180 ? 180 : lon, swapped };
};
