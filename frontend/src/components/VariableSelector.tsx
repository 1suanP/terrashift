/**
 * Compact variable picker. The selected variable expands to explain what it measures,
 * where the data comes from, and its resolution.
 */
import type { CatalogueVariable } from '../services/api';
import { FEATURED } from '../lib/variables';
import { IconChevron, IconGrid, VARIABLE_ICONS } from './icons';

interface Props {
  variables: CatalogueVariable[];
  selectedId: string;
  onSelect: (id: string) => void;
  collapsed: boolean;
  onToggle: () => void;
  loading: boolean;
  error: string;
}

export const VariableSelector = ({ variables, selectedId, onSelect, collapsed, onToggle, loading, error }: Props) => {
  const byId = new Map(variables.map((v) => [v.id, v]));
  const selected = byId.get(selectedId);
  const featuredIds = new Set(FEATURED.map((f) => f.id));
  const others = variables.filter((v) => v.status === 'available' && !featuredIds.has(v.id));
  const isOther = selected ? !featuredIds.has(selected.id) : false;

  if (collapsed) {
    return (
      <div className="glass var-rail">
        <button className="icon-btn" onClick={onToggle} data-tip="Show variables" aria-label="Show variables">
          <IconChevron />
        </button>
        {FEATURED.map((f) => {
          const Icon = VARIABLE_ICONS[f.icon];
          return (
            <button
              key={f.id}
              className={`icon-btn ${selectedId === f.id ? 'active' : ''}`}
              onClick={() => onSelect(f.id)}
              data-tip={f.label}
              aria-label={f.label}
            >
              <Icon />
            </button>
          );
        })}
      </div>
    );
  }

  return (
    <section className="glass var-panel" aria-label="Environmental variables">
      <header className="panel-head">
        <div>
          <div className="eyebrow">Variable</div>
          <div className="panel-title">What do you want to explore?</div>
        </div>
        <button className="icon-btn subtle" onClick={onToggle} data-tip="Hide panel" aria-label="Hide variables panel">
          <IconChevron style={{ transform: 'rotate(180deg)' }} />
        </button>
      </header>

      {loading && <div className="skeleton-list">{[0, 1, 2, 3, 4].map((i) => <div key={i} className="skeleton" />)}</div>}
      {error && <div className="inline-error">{error}</div>}

      {!loading && !error && (
        <div className="var-list">
          {FEATURED.map((f) => {
            const v = byId.get(f.id);
            const Icon = VARIABLE_ICONS[f.icon];
            const active = selectedId === f.id;
            const unavailable = v?.status === 'requires_dataset';
            return (
              <button
                key={f.id}
                className={`var-item ${active ? 'active' : ''} ${unavailable ? 'unavailable' : ''}`}
                onClick={() => onSelect(f.id)}
                aria-pressed={active}
              >
                <span className="var-icon"><Icon /></span>
                <span className="var-text">
                  <span className="var-name">{f.label}</span>
                  <span className="var-unit">{unavailable ? 'Needs another dataset' : v?.units}</span>
                </span>
              </button>
            );
          })}
          <label className={`var-item more ${isOther ? 'active' : ''}`}>
            <span className="var-icon"><IconGrid /></span>
            <select
              value={isOther ? selectedId : ''}
              onChange={(e) => e.target.value && onSelect(e.target.value)}
              aria-label="More variables"
            >
              <option value="">More variables…</option>
              {others.map((v) => <option key={v.id} value={v.id}>{v.common_name} ({v.units})</option>)}
            </select>
          </label>
        </div>
      )}

      {selected && <VariableDetails v={selected} />}
    </section>
  );
};

const VariableDetails = ({ v }: { v: CatalogueVariable }) => (
  <div className="var-details" key={v.id}>
    <div className="var-details-title">{v.common_name}</div>
    <p className="var-details-short">{v.short_description}</p>
    {v.status === 'available' && v.coverage ? (
      <dl className="facts">
        <div><dt>Unit</dt><dd>{v.units}</dd></div>
        <div><dt>Dataset</dt><dd title={v.dataset_title}>{v.dataset_key}</dd></div>
        <div><dt>Time step</dt><dd>{v.coverage.temporal_resolution}</dd></div>
        <div><dt>Grid</dt><dd>{v.coverage.spatial_resolution}</dd></div>
        <div className="wide"><dt>Coverage</dt><dd>{v.coverage.spatial_coverage}, {v.coverage.period_start.slice(0, 4)}–{v.coverage.period_end}</dd></div>
      </dl>
    ) : (
      <div className="notice warn">
        <strong>Not in the supported datasets.</strong> {v.reason_unavailable}
        {v.required_datasets?.[0] && <> Recommended: {v.required_datasets[0].short_name} ({v.required_datasets[0].archive}).</>}
      </div>
    )}
    <details className="explain">
      <summary>What does it measure?</summary>
      <p>{v.plain_language}</p>
      {v.trend_direction_hint && <p className="muted">Reading the numbers: {v.trend_direction_hint}.</p>}
    </details>
  </div>
);
