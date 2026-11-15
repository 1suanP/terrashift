/**
 * Floating location card: where you clicked, the current map value, and the
 * historical trend analysis for the selected variable.
 */
import { useEffect, useState } from 'react';
import type { CatalogueVariable, CoverageResponse, ReverseGeocode } from '../services/api';
import { FEATURED } from '../lib/variables';
import type { TrendState } from '../hooks/useTrendAnalysis';
import type { BBox, LatLon } from '../lib/geo';
import { formatBox, formatLatLon } from '../lib/geo';
import { TrendChart } from './TrendChart';
import { IconChevron, IconClose, IconPin, IconTrend } from './icons';

/** name/subtitle/attribution are set when the place came from search (no reverse lookup needed). */
interface SelectionMeta {
  name?: string;
  subtitle?: string;
  attribution?: string;
}

export type Selection =
  | ({ kind: 'point'; point: LatLon } & SelectionMeta)
  | ({ kind: 'region'; box: BBox } & SelectionMeta);

export interface CoverageState {
  status: 'loading' | 'done' | 'error';
  data?: CoverageResponse;
}

export interface Period {
  start: number;
  end: number;
}

interface Props {
  selection: Selection;
  place: { status: 'loading' | 'done' | 'error'; data?: ReverseGeocode };
  variable: CatalogueVariable | undefined;
  variables: CatalogueVariable[];
  coverage: CoverageState;
  closestAvailable?: CatalogueVariable;
  mapValue: { value: number | null; label: string; note: string; units: string; color: string; decimals: number } | null;
  period: Period;
  onPeriod: (p: Period) => void;
  useAnomalies: boolean;
  onUseAnomalies: (v: boolean) => void;
  trend: TrendState;
  onAnalyze: () => void;
  onSwitchVariable: (id: string) => void;
  onClose: () => void;
  collapsed: boolean;
  onToggle: () => void;
  alpha: number;
}

const placeTitle = (sel: Selection, place: Props['place']) => {
  if (sel.name) return sel.name;
  const d = place.data;
  if (place.status === 'loading') return sel.kind === 'region' ? 'Selected region' : 'Locating…';
  if (d?.found) {
    const main = d.place || d.region || d.country || 'Unnamed place';
    return sel.kind === 'region' ? `Region around ${main}` : main;
  }
  return sel.kind === 'region' ? 'Selected region' : 'Open water or remote area';
};

const placeSubtitle = (sel: Selection, place: Props['place']) => {
  if (sel.subtitle !== undefined) return sel.subtitle;
  const d = place.data;
  if (!d?.found) return place.status === 'error' ? 'Place name unavailable' : sel.kind === 'region' ? '' : 'No named place nearby';
  return [d.place ? d.region : null, d.country].filter(Boolean).join(', ');
};

const Elapsed = ({ startedAt, estimate }: { startedAt: number; estimate: number }) => {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 500);
    return () => window.clearInterval(id);
  }, []);
  const s = Math.round((now - startedAt) / 1000);
  const pct = Math.min(95, (s / estimate) * 100);
  return (
    <div className="progress">
      <div className="progress-bar"><span style={{ width: `${pct}%` }} /></div>
      <div className="progress-text">
        {s}s elapsed · usually about {estimate < 90 ? `${Math.round(estimate / 10) * 10}s` : `${Math.round(estimate / 60)} min`}
      </div>
    </div>
  );
};

const verdict = (sig: string) =>
  sig === 'increasing'
    ? { cls: 'up', title: 'Significant increase', icon: '↗' }
    : sig === 'decreasing'
      ? { cls: 'down', title: 'Significant decrease', icon: '↘' }
      : { cls: 'flat', title: 'No significant trend', icon: '→' };

const fmtNum = (v: number, digits = 3) => {
  const a = Math.abs(v);
  if (a !== 0 && (a < 0.001 || a >= 10000)) return v.toExponential(2);
  return v.toFixed(a >= 10 ? 1 : digits);
};

const pPlain = (p: number) => {
  const pct = p * 100;
  const shown = pct < 0.1 ? 'less than 0.1%' : pct < 1 ? `${pct.toFixed(1)}%` : `${Math.round(pct)}%`;
  return `If there were no real trend, random ups and downs would produce a slope this steep about ${shown} of the time.`;
};

export const LocationPanel = (props: Props) => {
  const { selection, variable, trend, period, alpha } = props;
  const title = placeTitle(selection, props.place);
  const subtitle = placeSubtitle(selection, props.place);
  const coords = selection.kind === 'point' ? formatLatLon(selection.point) : formatBox(selection.box);
  const available = variable?.status === 'available';
  const startYear = Number(variable?.coverage?.period_start.slice(0, 4) ?? 1980);
  const firstFull = variable?.coverage?.period_start.slice(5, 7) === '01' ? startYear : startYear + 1;
  const lastFull = new Date().getFullYear() - 1;
  const years = period.end - period.start + 1;
  const estimate = (variable?.coverage?.load_seconds_per_year ?? 10) * years + 10;
  const yearOptions = Array.from({ length: lastFull - firstFull + 1 }, (_, i) => firstFull + i);
  const cov = props.coverage.data?.variables;
  const here = variable && cov ? cov[variable.id] : undefined;
  const noDataHere = here?.status === 'no_data_here';
  const byId = new Map(props.variables.map((x) => [x.id, x]));
  const alternatives = FEATURED
    .map((f) => byId.get(f.id))
    .filter((x): x is CatalogueVariable => Boolean(x) && x!.status === 'available' && x!.id !== variable?.id && cov?.[x!.id]?.status === 'available');

  if (props.collapsed) {
    return (
      <button className="glass loc-pill" onClick={props.onToggle} aria-label="Show location panel">
        <IconPin /> <span>{title}</span> <IconChevron style={{ transform: 'rotate(180deg)' }} />
      </button>
    );
  }

  const done = trend.status === 'done' ? trend : null;
  const v = done ? verdict(done.result.significance) : null;

  return (
    <section className="glass loc-panel" aria-label="Location details">
      <header className="loc-head">
        <div className="loc-title-wrap">
          <div className="eyebrow"><IconPin width={13} height={13} /> {selection.kind === 'point' ? 'Selected location' : 'Selected region'}</div>
          <h2 className={`loc-title ${props.place.status === 'loading' && !selection.name ? 'shimmer-text' : ''}`}>{title}</h2>
          {subtitle && <div className="loc-sub">{subtitle}</div>}
          <div className="loc-coords">{coords}</div>
        </div>
        <div className="loc-actions">
          <button className="icon-btn subtle" onClick={props.onToggle} data-tip="Minimize" aria-label="Minimize panel"><IconChevron /></button>
          <button className="icon-btn subtle" onClick={props.onClose} data-tip="Clear selection" aria-label="Clear selection"><IconClose /></button>
        </div>
      </header>

      {props.mapValue && (
        <div className="now-card">
          <span className="now-swatch" style={{ background: props.mapValue.color }} />
          <div>
            <div className="now-value">
              {props.mapValue.value === null ? 'No data' : props.mapValue.value.toFixed(props.mapValue.decimals)}
              {props.mapValue.value !== null && <small> {props.mapValue.units}</small>}
            </div>
            <div className="now-label">{props.mapValue.label}</div>
          </div>
          <span className="now-note" data-tip={props.mapValue.note}>ⓘ</span>
        </div>
      )}

      <div className="loc-section">
        <div className="eyebrow">Data available here</div>
        {props.coverage.status === 'loading' && <div className="avail-row"><span className="spinner small" /> <span className="muted small">Checking NASA coverage for this place…</span></div>}
        {props.coverage.status === 'error' && <div className="muted small">Coverage could not be checked right now. Analyses may still work.</div>}
        {cov && (
          <div className="avail-row" role="list">
            {FEATURED.map((f) => {
              const v = byId.get(f.id);
              const c = cov[f.id];
              const state = !v ? 'unknown' : v.status === 'requires_dataset' ? 'unsupported' : c?.status ?? 'unknown';
              const tip = state === 'available' ? `${v?.common_name}: NASA data exists here. Click to explore.`
                : state === 'no_data_here' ? `${v?.common_name}: ${c?.reason}`
                  : state === 'unsupported' ? `${f.label}: not in the supported datasets.`
                    : `${f.label}: coverage unknown.`;
              return (
                <button
                  key={f.id}
                  role="listitem"
                  className={`avail-chip ${state} ${variable?.id === f.id ? 'current' : ''}`}
                  data-tip={tip}
                  disabled={state === 'no_data_here' || state === 'unsupported'}
                  onClick={() => props.onSwitchVariable(f.id)}
                >
                  <span className="avail-dot" aria-hidden="true" />
                  {f.label}
                  <span className="sr-only">{state === 'available' ? ' (available)' : state === 'no_data_here' ? ' (no data here)' : ' (not supported)'}</span>
                </button>
              );
            })}
          </div>
        )}
      </div>

      <div className="loc-section">
        <div className="eyebrow">Variable</div>
        {variable ? (
          <div className="loc-var">
            <div className="loc-var-name">{variable.common_name} <span className="muted">({variable.units})</span></div>
            {available && variable.coverage ? (
              <div className="loc-var-meta">
                <span data-tip={variable.dataset_title}>{variable.dataset_key}</span>
                <span>{variable.coverage.temporal_resolution.toLowerCase()}</span>
                <span>{variable.coverage.period_start.slice(0, 4)}–{variable.coverage.period_end}</span>
              </div>
            ) : (
              <div className="notice warn">
                {variable.common_name} is not in the supported datasets. {variable.reason_unavailable}
                {props.closestAvailable && (
                  <button className="link-btn" onClick={() => props.onSwitchVariable(props.closestAvailable!.id)}>
                    Use {props.closestAvailable.common_name.toLowerCase()} instead →
                  </button>
                )}
              </div>
            )}
          </div>
        ) : <div className="skeleton" />}
      </div>

      {available && noDataHere && (
        <div className="notice warn">
          <strong>No {variable!.common_name.toLowerCase()} data at this place.</strong> {here!.reason}
          {alternatives.length > 0 && (
            <div className="alt-row">
              Try:{' '}
              {alternatives.map((a) => (
                <button key={a.id} className="link-btn" onClick={() => props.onSwitchVariable(a.id)}>{a.common_name}</button>
              ))}
            </div>
          )}
        </div>
      )}

      {available && !noDataHere && (
        <div className="loc-section">
          <div className="eyebrow">Historical trend</div>
          <div className="period-row">
            <label>
              From
              <select value={period.start} onChange={(e) => props.onPeriod({ start: +e.target.value, end: Math.max(+e.target.value + 1, period.end) })}>
                {yearOptions.slice(0, -1).map((y) => <option key={y} value={y}>{y}</option>)}
              </select>
            </label>
            <label>
              to
              <select value={period.end} onChange={(e) => props.onPeriod({ start: Math.min(period.start, +e.target.value - 1), end: +e.target.value })}>
                {yearOptions.slice(1).map((y) => <option key={y} value={y}>{y}</option>)}
              </select>
            </label>
            <label className="check" data-tip="Compare each month with its usual value for that time of year, so seasons don't hide a long-term change. Recommended.">
              <input type="checkbox" checked={props.useAnomalies} onChange={(e) => props.onUseAnomalies(e.target.checked)} />
              Remove seasons
            </label>
          </div>
          {years < 10 && <div className="hint">Trends over fewer than 10 years are easily dominated by natural year-to-year swings.</div>}

          {trend.status !== 'loading' && (
            <button className="primary-btn" onClick={props.onAnalyze}>
              <IconTrend /> {done ? 'Re-run analysis' : 'Analyze trend'}
              <span className="btn-note">{years} years · {estimate < 90 ? `~${Math.round(estimate / 10) * 10}s` : `~${Math.round(estimate / 60)} min`}</span>
            </button>
          )}
          {trend.status === 'loading' && (
            <div className="loading-card">
              <div className="spinner" />
              <div>
                <div>Downloading {years * 12} monthly NASA files and testing for a trend…</div>
                <Elapsed startedAt={trend.startedAt} estimate={trend.estimateSeconds} />
              </div>
            </div>
          )}
          {trend.status === 'error' && (
            <div className="notice error">
              <strong>Analysis failed.</strong> {trend.message}
            </div>
          )}
        </div>
      )}

      {done && v && (
        <div className="loc-section results">
          <div className={`verdict ${v.cls}`}>
            <span className="verdict-icon">{v.icon}</span>
            <div>
              <div className="verdict-title">{v.title}</div>
              <div className="verdict-sub">
                {done.request.time_range_start.slice(0, 4)}–{done.request.time_range_end.slice(0, 4)} · {done.result.n_points} months · α = {alpha}
              </div>
            </div>
            <div className="verdict-num">
              {done.result.linear.slope * 10 > 0 ? '+' : ''}{fmtNum(done.result.linear.slope * 10)}
              <small>{done.result.units} per decade</small>
            </div>
          </div>

          <TrendChart
            timestamps={done.result.time_series.timestamps}
            values={done.result.time_series.values}
            anomalies={done.result.time_series.anomalies}
            slope={done.result.linear.slope}
            intercept={done.result.linear.intercept}
            units={done.result.units}
            significance={done.result.significance}
          />

          <p className="plain">{done.result.interpretation}</p>

          <div className="stats">
            <div data-tip="How much the value changes per year on average, from a straight-line (least-squares) fit. The range is the 95% confidence interval.">
              <span>Linear slope</span>
              <strong>{fmtNum(done.result.linear.slope)} /yr</strong>
              {done.result.linear.ci_lower !== undefined && (
                <em>95% CI {fmtNum(done.result.linear.ci_lower)} to {fmtNum(done.result.linear.ci_upper!)}</em>
              )}
            </div>
            <div data-tip={pPlain(done.result.linear.p_value)}>
              <span>Regression p-value</span>
              <strong className={done.result.linear.p_value < alpha ? 'sig' : ''}>{done.result.linear.p_value.toPrecision(2)}</strong>
              <em>{done.result.linear.p_value < alpha ? `below ${alpha}` : `above ${alpha}`}</em>
            </div>
            <div data-tip="A rank-based test that asks whether later values tend to be higher (or lower) than earlier ones. It does not assume a straight line or normal data, so it is robust to outliers.">
              <span>Mann-Kendall</span>
              <strong className={done.result.mann_kendall.p < alpha ? 'sig' : ''}>{done.result.mann_kendall.trend}</strong>
              <em>p = {done.result.mann_kendall.p.toPrecision(2)}{done.result.mann_kendall.tau !== undefined ? ` · τ = ${done.result.mann_kendall.tau.toFixed(2)}` : ''}</em>
            </div>
            {done.result.sens_slope_value !== undefined && (
              <div data-tip="The median of the slopes between every pair of months. Less affected by extreme months than the straight-line fit.">
                <span>Sen's slope</span>
                <strong>{fmtNum(done.result.sens_slope_value)} /yr</strong>
                <em>robust estimate</em>
              </div>
            )}
          </div>

          <div className="explain-box">
            <strong>How to read this.</strong>{' '}
            {done.result.significance === 'none'
              ? 'The values go up and down, but not consistently enough to be confident of a long-term change over this period. This is not proof that nothing is changing: a longer period or larger region may show a trend.'
              : `Both tests agree on the direction, and the regression p-value is below ${alpha}. A change this consistent would be unlikely if there were no real trend. It describes this place and period only, and does not by itself explain the cause.`}
          </div>

          <details className="explain">
            <summary>Data source & method</summary>
            <ul>
              <li><strong>Data:</strong> {variable?.dataset_title} ({variable?.dataset_key}), {variable?.coverage?.archive}. {variable?.coverage?.source_type}.</li>
              <li><strong>Area:</strong> {formatBox({
                min_lat: done.request.min_lat, max_lat: done.request.max_lat,
                min_lon: done.request.min_lon, max_lon: done.request.max_lon,
              })}, averaged over all grid cells inside (empty cells skipped).</li>
              <li><strong>Seasons:</strong> {done.request.use_anomalies ? 'Each month minus that calendar month\'s average over the period (anomalies).' : 'Raw monthly values (seasonal cycle included).'}</li>
              <li><strong>Tests:</strong> ordinary least-squares regression against time, Mann-Kendall trend test, and Sen's slope.</li>
              <li><strong>Rule:</strong> called significant only if the regression p &lt; {alpha} and Mann-Kendall agrees on the direction.</li>
            </ul>
          </details>
        </div>
      )}

      {(selection.attribution || props.place.data?.attribution) && (
        <div className="attribution">{selection.attribution || props.place.data?.attribution}</div>
      )}
    </section>
  );
};
