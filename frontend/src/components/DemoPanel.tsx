/** Demo mode: ready-made investigations from config.DEMO_PRESETS, run on real data. */
import { useEffect, useState } from 'react';
import apiService from '../services/api';
import type { DemoPresetInfo } from '../services/api';
import { IconChevron } from './icons';

interface Props {
  onRun: (p: DemoPresetInfo) => void;
  activeName: string | null;
  collapsed: boolean;
  onToggle: () => void;
}

export const DemoPanel = ({ onRun, activeName, collapsed, onToggle }: Props) => {
  const [presets, setPresets] = useState<DemoPresetInfo[] | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    apiService.getDemoPresets().then(setPresets).catch(() => setError('Could not load demo investigations.'));
  }, []);

  if (collapsed) {
    return (
      <button className="glass loc-pill left" onClick={onToggle}>Demo investigations <IconChevron /></button>
    );
  }

  return (
    <section className="glass side-panel" aria-label="Demo investigations">
      <header className="panel-head">
        <div>
          <div className="eyebrow">Demo</div>
          <div className="panel-title">Try a ready-made investigation</div>
        </div>
        <button className="icon-btn subtle" onClick={onToggle} aria-label="Hide panel">
          <IconChevron style={{ transform: 'rotate(180deg)' }} />
        </button>
      </header>
      <p className="muted small">
        Each one flies to a region and runs a real trend test on NASA data for the last 10 complete years.
      </p>
      {error && <div className="inline-error">{error}</div>}
      {!presets && !error && <div className="skeleton-list">{[0, 1, 2].map((i) => <div key={i} className="skeleton tall" />)}</div>}
      <div className="demo-list">
        {presets?.map((p) => (
          <button key={p.name} className={`demo-card ${activeName === p.name ? 'active' : ''}`} onClick={() => onRun(p)}>
            <div className="demo-name">{p.name}</div>
            <div className="demo-desc">{p.description}</div>
            <div className="demo-expect"><span>Scientists' expectation (not a result):</span> {p.expected_insight}</div>
            <div className="demo-go">Run on real data →</div>
          </button>
        ))}
      </div>
    </section>
  );
};
