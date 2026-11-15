/**
 * Runs the existing backend trend pipeline (/api/analysis/run) and keeps the result.
 * Identical requests are answered from a session cache.
 */
import { useCallback, useRef, useState } from 'react';
import apiService from '../services/api';
import type { AnalysisRequest, AnalysisResult } from '../services/api';

export type TrendState =
  | { status: 'idle' }
  | { status: 'loading'; key: string; startedAt: number; estimateSeconds: number }
  | { status: 'done'; key: string; request: AnalysisRequest; result: AnalysisResult }
  | { status: 'error'; key: string; message: string };

export const requestKey = (r: AnalysisRequest) =>
  [r.dataset_key, r.variable_id, r.min_lat, r.max_lat, r.min_lon, r.max_lon, r.time_range_start, r.time_range_end, r.use_anomalies]
    .map((v) => (typeof v === 'number' ? v.toFixed(3) : String(v)))
    .join('|');

const friendlyError = (detail: string): string => {
  if (/valid data points|empty subset|no data|zero grid cells/i.test(detail)) {
    return 'There is no valid data for this variable at this place. Some variables only exist over land or only over water. Try a nearby point or a larger region.';
  }
  if (/timeout|did not respond/i.test(detail)) {
    return 'NASA took too long to respond. Try a shorter time period, then try again.';
  }
  if (/credentials|Earthdata Login/i.test(detail)) {
    return 'The backend could not log in to NASA Earthdata. Check the username and password in backend/.env.';
  }
  return detail;
};

export function useTrendAnalysis(onComplete?: () => void) {
  const [state, setState] = useState<TrendState>({ status: 'idle' });
  const cache = useRef(new Map<string, AnalysisResult>());
  const latest = useRef('');

  const run = useCallback(async (request: AnalysisRequest, estimateSeconds: number) => {
    const key = requestKey(request);
    latest.current = key;
    const hit = cache.current.get(key);
    if (hit) {
      setState({ status: 'done', key, request, result: hit });
      return;
    }
    setState({ status: 'loading', key, startedAt: Date.now(), estimateSeconds });
    try {
      const { analysis_id } = await apiService.runAnalysis(request);
      const result = await apiService.getAnalysisResult(analysis_id);
      cache.current.set(key, result);
      if (latest.current === key) setState({ status: 'done', key, request, result });
      onComplete?.();
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } }; message?: string; code?: string };
      const detail = err.response?.data?.detail || (err.code === 'ECONNABORTED' ? 'timeout' : err.message) || 'Analysis failed';
      if (latest.current === key) setState({ status: 'error', key, message: friendlyError(detail) });
    }
  }, [onComplete]);

  const reset = useCallback(() => {
    latest.current = '';
    setState({ status: 'idle' });
  }, []);

  return { state, run, reset };
}
