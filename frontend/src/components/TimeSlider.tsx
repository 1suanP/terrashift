/**
 * Bottom time control for the active data layer: year stepper, month track,
 * play/pause, legend, and an honest source line.
 */
import type { MapLayerState } from '../hooks/useMapLayer';
import type { Palette } from '../lib/colorScales';
import { MONTH_NAMES, legendGradient } from '../lib/colorScales';
import { IconChevron, IconPause, IconPlay } from './icons';

interface Props {
  layer: MapLayerState;
  palette: Palette;
  source: string;
  resolution: string;
  kind: string; // e.g. "Satellite observations" or "Reanalysis"
}

export const TimeSlider = ({ layer, palette, source, resolution, kind }: Props) => {
  const { year, months, month, grids, failed, playing, status } = layer;
  const loaded = months.filter((m) => grids[m]).length;
  const canPlay = loaded >= 2;
  const lo = palette.ticks[0];
  const hi = palette.ticks[palette.ticks.length - 1];

  return (
    <div className="glass time-bar" aria-label={`${palette.short} time control`}>
      <div className="time-row">
        <button
          className="icon-btn play"
          onClick={() => layer.setPlaying(!playing)}
          disabled={!canPlay}
          aria-label={playing ? 'Pause animation' : 'Play animation'}
          data-tip={canPlay ? (playing ? 'Pause' : 'Animate the months') : 'Waiting for months to load'}
        >
          {playing ? <IconPause /> : <IconPlay />}
        </button>

        <div className="year-step">
          <button className="icon-btn subtle" aria-label="Previous year" disabled={year === null || year <= layer.firstYear}
            onClick={() => year !== null && layer.setYear(year - 1)}>
            <IconChevron style={{ transform: 'rotate(180deg)' }} />
          </button>
          <span className="year">{year ?? '····'}</span>
          <button className="icon-btn subtle" aria-label="Next year" disabled={year === null || year >= layer.lastYear}
            onClick={() => year !== null && layer.setYear(year + 1)}>
            <IconChevron />
          </button>
        </div>

        <div className="months" role="radiogroup" aria-label="Month">
          {MONTH_NAMES.map((name, i) => {
            const m = i + 1;
            const published = months.includes(m);
            const ready = Boolean(grids[m]);
            const err = failed[m];
            const state = !published ? 'na' : err ? 'err' : ready ? 'ready' : 'loading';
            return (
              <button
                key={m}
                role="radio"
                aria-checked={month === m}
                className={`month ${state} ${month === m ? 'on' : ''}`}
                disabled={!published || Boolean(err)}
                onClick={() => { layer.setPlaying(false); layer.setMonth(m); }}
                data-tip={!published ? 'Not published by NASA yet' : err ? err : ready ? `${name} ${year}` : 'Loading from NASA…'}
              >
                <span className="month-tick" />
                <span className="month-name">{name}</span>
              </button>
            );
          })}
        </div>

        <div className="legend" aria-label={`${palette.short} legend`}>
          <div className="legend-title">{palette.title}</div>
          <div className="legend-bar" style={{ background: legendGradient(palette) }} />
          <div className="legend-ticks">
            {palette.ticks.map((t) => (
              <span key={t}>{t === lo && !palette.clearBelow && lo < 0 ? '≤' : ''}{t}{t === hi ? '+' : ''}</span>
            ))}
            <span className="unit">{palette.units}</span>
          </div>
        </div>
      </div>

      <div className="time-foot">
        {status === 'finding' && <span className="live">Checking which months NASA has published…</span>}
        {status === 'loading' && <span className="live">Loading {loaded}/{months.length} months from NASA (~10 s each the first time, then cached)…</span>}
        {status === 'empty' && <span>No months published for {year} yet. Try the previous year.</span>}
        {status === 'error' && <span className="err-text">{layer.error}</span>}
        {status === 'ready' && month !== null && <span>{MONTH_NAMES[month - 1]} {year} · monthly average{palette.note ? ` · ${palette.note}` : ''}</span>}
        <span className="source">{source} · {resolution} · {kind}, not real-time or forecast</span>
      </div>
    </div>
  );
};
