/**
 * Time-series chart (plain SVG, no chart library).
 * "Change vs. normal" shows the series the trend was fitted to, with the regression line.
 * "Actual values" shows monthly values with a 12-month running mean.
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import type { PointerEvent as ReactPointerEvent } from 'react';

interface Props {
  timestamps: string[];
  values: (number | null)[];
  anomalies?: (number | null)[] | null;
  slope: number;
  intercept: number | undefined;
  units: string;
  significance: string;
}

const H = 210;
const PAD = { top: 14, right: 12, bottom: 26, left: 44 };

/** Same x as the backend regression: year + day-of-year / days-in-year. */
const fractionalYear = (iso: string) => {
  const d = new Date(iso);
  const y = d.getUTCFullYear();
  const start = Date.UTC(y, 0, 1);
  const leap = (y % 4 === 0 && y % 100 !== 0) || y % 400 === 0;
  const dayOfYear = Math.floor((d.getTime() - start) / 86400000) + 1;
  return y + dayOfYear / (leap ? 366 : 365);
};

const niceTicks = (lo: number, hi: number, count = 4) => {
  if (!(hi > lo)) return [lo];
  const raw = (hi - lo) / count;
  const mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) ?? raw;
  const ticks: number[] = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) ticks.push(Number(v.toFixed(10)));
  return ticks;
};

const fmt = (v: number) => (Math.abs(v) >= 100 ? v.toFixed(0) : Math.abs(v) >= 10 ? v.toFixed(1) : v.toFixed(2));

export const TrendChart = ({ timestamps, values, anomalies, slope, intercept, units, significance }: Props) => {
  const wrapRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(360);
  const hasAnomalies = Boolean(anomalies && anomalies.some((v) => v !== null));
  const [view, setView] = useState<'anomaly' | 'actual'>(hasAnomalies ? 'anomaly' : 'actual');
  const [hover, setHover] = useState<number | null>(null);

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setWidth(Math.max(240, el.clientWidth)));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const showTrendLine = view === 'anomaly' || !hasAnomalies;
  const series = view === 'anomaly' && hasAnomalies ? anomalies! : values;

  const data = useMemo(() => {
    const pts = timestamps.map((t, i) => ({ t, x: fractionalYear(t), y: series[i] }));
    const running = pts.map((_, i) => {
      if (i < 11) return null;
      const win = series.slice(i - 11, i + 1).filter((v): v is number => v !== null);
      return win.length >= 9 ? win.reduce((a, b) => a + b, 0) / win.length : null;
    });
    return { pts, running };
  }, [timestamps, series]);

  const valid = data.pts.filter((p) => p.y !== null) as { t: string; x: number; y: number }[];
  if (valid.length < 2) return <div className="chart-empty">Not enough data points to draw a chart.</div>;

  const x0 = valid[0].x;
  const x1 = valid[valid.length - 1].x;
  const trend = showTrendLine && intercept !== undefined
    ? [x0, x1].map((x) => intercept + slope * x)
    : [];
  let ymin = Math.min(...valid.map((p) => p.y), ...trend);
  let ymax = Math.max(...valid.map((p) => p.y), ...trend);
  if (view === 'anomaly') {
    const m = Math.max(Math.abs(ymin), Math.abs(ymax));
    ymin = -m;
    ymax = m;
  }
  const padY = (ymax - ymin) * 0.08 || 1;
  ymin -= padY;
  ymax += padY;

  const iw = width - PAD.left - PAD.right;
  const ih = H - PAD.top - PAD.bottom;
  const sx = (x: number) => PAD.left + ((x - x0) / (x1 - x0 || 1)) * iw;
  const sy = (y: number) => PAD.top + (1 - (y - ymin) / (ymax - ymin)) * ih;

  const linePath = (ys: (number | null)[]) => {
    let d = '';
    let pen = false;
    data.pts.forEach((p, i) => {
      const y = ys[i];
      if (y === null || y === undefined) { pen = false; return; }
      d += `${pen ? 'L' : 'M'}${sx(p.x).toFixed(1)},${sy(y).toFixed(1)}`;
      pen = true;
    });
    return d;
  };

  const yTicks = niceTicks(ymin, ymax);
  const firstYear = Math.ceil(x0);
  const lastYear = Math.floor(x1);
  const yearStep = Math.max(1, Math.ceil((lastYear - firstYear + 1) / Math.max(2, Math.floor(iw / 70))));
  const xTicks: number[] = [];
  for (let y = firstYear; y <= lastYear; y += yearStep) xTicks.push(y);

  const onMove = (e: ReactPointerEvent<SVGSVGElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const px = e.clientX - rect.left;
    let best = 0;
    let bestD = Infinity;
    data.pts.forEach((p, i) => {
      if (p.y === null) return;
      const d = Math.abs(sx(p.x) - px);
      if (d < bestD) { bestD = d; best = i; }
    });
    setHover(best);
  };

  const trendClass = significance === 'increasing' ? 'up' : significance === 'decreasing' ? 'down' : 'flat';
  const hp = hover !== null ? data.pts[hover] : null;

  return (
    <div className="trend-chart" ref={wrapRef}>
      {hasAnomalies && (
        <div className="seg" role="tablist" aria-label="Chart view">
          <button role="tab" aria-selected={view === 'anomaly'} className={view === 'anomaly' ? 'on' : ''} onClick={() => setView('anomaly')}
            data-tip="Each month minus its usual value for that calendar month. This removes the seasons, so a long-term change is easier to see.">
            Change vs. normal
          </button>
          <button role="tab" aria-selected={view === 'actual'} className={view === 'actual' ? 'on' : ''} onClick={() => setView('actual')}
            data-tip="The monthly values as measured, with a 12-month running mean.">
            Actual values
          </button>
        </div>
      )}
      <svg width={width} height={H} onPointerMove={onMove} onPointerLeave={() => setHover(null)} role="img"
        aria-label={`Monthly ${view === 'anomaly' ? 'anomalies' : 'values'} in ${units}`}>
        {yTicks.map((t) => (
          <g key={t}>
            <line x1={PAD.left} x2={width - PAD.right} y1={sy(t)} y2={sy(t)} className={t === 0 && view === 'anomaly' ? 'grid zero' : 'grid'} />
            <text x={PAD.left - 6} y={sy(t) + 3} className="tick" textAnchor="end">{fmt(t)}</text>
          </g>
        ))}
        {xTicks.map((y) => (
          <text key={y} x={sx(y)} y={H - 8} className="tick" textAnchor="middle">{y}</text>
        ))}
        <path d={linePath(series)} className="series" />
        {view === 'actual' && <path d={linePath(data.running)} className="running" />}
        {trend.length === 2 && (
          <line x1={sx(x0)} y1={sy(trend[0])} x2={sx(x1)} y2={sy(trend[1])} className={`trendline ${trendClass}`} />
        )}
        {hp && hp.y !== null && (
          <g>
            <line x1={sx(hp.x)} x2={sx(hp.x)} y1={PAD.top} y2={H - PAD.bottom} className="cursor" />
            <circle cx={sx(hp.x)} cy={sy(hp.y)} r={3.5} className="dot" />
          </g>
        )}
      </svg>
      <div className="chart-foot">
        {hp && hp.y !== null ? (
          <span>
            <strong>{new Date(hp.t).toLocaleDateString('en', { month: 'short', year: 'numeric', timeZone: 'UTC' })}</strong>{' '}
            {hp.y > 0 && view === 'anomaly' ? '+' : ''}{fmt(hp.y)} {units}{view === 'anomaly' ? ' vs. normal' : ''}
          </span>
        ) : (
          <span className="legend-keys">
            <i className="k series" /> Monthly {view === 'anomaly' ? 'anomaly' : 'value'}
            {view === 'actual' && <><i className="k running" /> 12-month mean</>}
            {trend.length === 2 && <><i className={`k trendline ${trendClass}`} /> Linear trend</>}
          </span>
        )}
        <span className="units">{units}</span>
      </div>
    </div>
  );
};
