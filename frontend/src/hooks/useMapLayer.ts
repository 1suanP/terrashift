/**
 * Loads one year of real NASA monthly maps for a globe data layer, paints them with
 * the layer's palette, and drives the time slider / animation. Months NASA has not
 * published are never shown. Painted months are cached per layer, so switching
 * layers back and forth is instant.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import apiService from '../services/api';
import type { MapGrid } from '../services/api';
import type { Palette } from '../lib/colorScales';
import { paintGrid } from '../lib/colorScales';

export type LayerStatus = 'idle' | 'finding' | 'loading' | 'ready' | 'empty' | 'error';

const CONCURRENCY = 3;
const FRAME_MS = 1100;

interface Painted {
  grid: MapGrid;
  canvas: HTMLCanvasElement;
}

export function useMapLayer(layerKey: string | null, palette: Palette | null, enabled: boolean, firstYear: number, lastYear: number) {
  const [year, setYearState] = useState<number | null>(null);
  const [months, setMonths] = useState<number[]>([]);
  const [painted, setPainted] = useState<Record<number, Painted>>({});
  const [failed, setFailed] = useState<Record<number, string>>({});
  const [month, setMonth] = useState<number | null>(null);
  const [playing, setPlaying] = useState(false);
  const [status, setStatus] = useState<LayerStatus>('idle');
  const [error, setError] = useState('');
  const generation = useRef(0);
  const cache = useRef(new Map<string, Painted>());

  // The first time any layer is shown, start at the most recent year with data.
  useEffect(() => {
    if (!enabled || !layerKey || year !== null) return;
    let cancelled = false;
    (async () => {
      try {
        let y = lastYear;
        let found = await apiService.getMapMonths(layerKey, y);
        if (found.length === 0 && y - 1 >= firstYear) {
          y -= 1;
          found = await apiService.getMapMonths(layerKey, y);
        }
        if (!cancelled) setYearState(y);
      } catch {
        if (!cancelled) {
          setStatus('error');
          setError('Could not reach NASA to list available months. Check that the backend is running.');
        }
      }
    })();
    return () => { cancelled = true; };
  }, [enabled, layerKey, year, lastYear, firstYear]);

  // Load every published month of the selected year for this layer (latest first).
  useEffect(() => {
    if (!enabled || !layerKey || !palette || year === null) return;
    const gen = ++generation.current;
    const yearForRun = year;
    (async () => {
      setPainted({});
      setFailed({});
      setPlaying(false);
      setStatus('finding');
      setError('');
      let available: number[];
      try {
        available = await apiService.getMapMonths(layerKey, yearForRun);
      } catch {
        if (gen === generation.current) {
          setStatus('error');
          setError('Could not list the months NASA has published for this year.');
        }
        return;
      }
      if (gen !== generation.current) return;
      setMonths(available);
      if (available.length === 0) {
        setStatus('empty');
        setMonth(null);
        return;
      }
      setMonth((m) => (m !== null && available.includes(m) ? m : available[available.length - 1]));
      const cached: Record<number, Painted> = {};
      for (const m of available) {
        const hit = cache.current.get(`${layerKey}|${yearForRun}|${m}`);
        if (hit) cached[m] = hit;
      }
      setPainted(cached);
      const queue = [...available].reverse().filter((m) => !cached[m]);
      if (queue.length === 0) {
        setStatus('ready');
        return;
      }
      setStatus('loading');
      const worker = async () => {
        while (queue.length && gen === generation.current) {
          const m = queue.shift()!;
          try {
            const grid = await apiService.getMap(layerKey, yearForRun, m);
            if (gen !== generation.current) return;
            const canvas = document.createElement('canvas');
            paintGrid(grid, canvas, palette);
            const entry = { grid, canvas };
            cache.current.set(`${layerKey}|${yearForRun}|${m}`, entry);
            setPainted((p) => ({ ...p, [m]: entry }));
          } catch (e: unknown) {
            const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
            if (gen === generation.current) setFailed((f) => ({ ...f, [m]: detail || 'Download failed' }));
          }
        }
      };
      await Promise.all(Array.from({ length: CONCURRENCY }, worker));
      if (gen === generation.current) setStatus('ready');
    })();
  }, [enabled, layerKey, palette, year]);

  // Animation: step through loaded months in order, looping.
  useEffect(() => {
    if (!playing || !enabled) return;
    const id = window.setInterval(() => {
      setMonth((current) => {
        const loaded = months.filter((m) => painted[m]);
        if (loaded.length < 2) return current;
        const i = current === null ? -1 : loaded.indexOf(current);
        return loaded[(i + 1) % loaded.length];
      });
    }, FRAME_MS);
    return () => window.clearInterval(id);
  }, [playing, enabled, months, painted]);

  const setYear = useCallback((y: number) => {
    if (y < firstYear || y > lastYear) return;
    setYearState(y);
  }, [firstYear, lastYear]);

  const current = month !== null ? painted[month] : undefined;
  const grids: Record<number, MapGrid> = {};
  for (const [m, p] of Object.entries(painted)) grids[Number(m)] = p.grid;

  return {
    year, setYear, firstYear, lastYear,
    months, month, setMonth,
    grids, failed,
    grid: current?.grid ?? null,
    canvas: current?.canvas ?? null,
    loadedCount: Object.keys(painted).length,
    playing: playing && enabled, setPlaying,
    status, error,
  };
}

export type MapLayerState = ReturnType<typeof useMapLayer>;
