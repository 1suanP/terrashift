/**
 * Variable Discovery - searchable catalogue of Earth science variables and
 * suggested trend questions. Availability is never presented as a trend:
 * only completed analyses report one.
 */
import { useEffect, useMemo, useState } from 'react';
import apiService from '../services/api';
import type { Catalogue, CatalogueVariable, CompletedAnalysis, TrendQuestion } from '../services/api';
import type { AnalysisPreset } from './AnalysisPanel';
import './VariableDiscovery.css';

interface Props {
  refreshKey: number;
  onInvestigate: (preset: Omit<AnalysisPreset, 'nonce'>) => void;
}

type Availability = 'all' | 'available' | 'requires_dataset';

const SIGNIFICANCE_LABEL: Record<CompletedAnalysis['significance'], string> = {
  increasing: 'STATISTICALLY SIGNIFICANT INCREASE',
  decreasing: 'STATISTICALLY SIGNIFICANT DECREASE',
  none: 'NO STATISTICALLY SIGNIFICANT TREND',
};

const year = (iso: string) => iso.slice(0, 4);

const formatWait = (seconds: number) =>
  seconds < 90 ? `about ${Math.max(10, Math.round(seconds / 10) * 10)} s` : `about ${Math.round(seconds / 60)} min`;

const matches = (v: CatalogueVariable, q: string) => {
  if (!q) return true;
  const haystack = [
    v.common_name, v.scientific_name, v.variable_id ?? '', v.dataset_title ?? '', v.dataset_key ?? '',
    v.short_description, ...v.keywords,
  ].join(' ').toLowerCase();
  return q.toLowerCase().split(/\s+/).every((word) => haystack.includes(word));
};

const TrendStatus = ({ analyses, alpha }: { analyses: CompletedAnalysis[]; alpha: number }) => {
  if (analyses.length === 0) {
    return (
      <div className="vd-trend-status untested">
        <div className="vd-label">TREND STATUS</div>
        <p>
          <strong>Not yet tested.</strong> This variable can be downloaded and analyzed, but no trend has been
          established. Run an analysis to test it.
        </p>
      </div>
    );
  }
  return (
    <div className="vd-trend-status tested">
      <div className="vd-label">YOUR RESULTS THIS SESSION</div>
      {analyses.map((a) => (
        <div key={a.analysis_id} className="vd-result-row">
          <div>
            <span className="vd-result-where">{a.region_name}, {year(a.time_range_start)}–{year(a.time_range_end)}</span>
            <span className={`vd-sig vd-sig-${a.significance}`}>{SIGNIFICANCE_LABEL[a.significance]}</span>
          </div>
          <div className="vd-result-stats">
            slope {a.slope_per_year.toFixed(4)} {a.units}/yr · linear p = {a.linear_p_value.toPrecision(2)} ·
            Mann-Kendall p = {a.mann_kendall_p.toPrecision(2)} · n = {a.n_points}
          </div>
        </div>
      ))}
      <p className="vd-fineprint">
        A result applies only to that region and period. It counts as a statistically established trend only when
        both tests have p &lt; {alpha} and agree on the direction.
      </p>
    </div>
  );
};

export const VariableDiscovery = ({ refreshKey, onInvestigate }: Props) => {
  const [catalogue, setCatalogue] = useState<Catalogue | null>(null);
  const [error, setError] = useState('');
  const [tab, setTab] = useState<'variables' | 'questions'>('variables');
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('all');
  const [level, setLevel] = useState('all');
  const [availability, setAvailability] = useState<Availability>('all');
  const [expanded, setExpanded] = useState<string | null>(null);

  useEffect(() => {
    apiService
      .getCatalogue()
      .then((c) => { setCatalogue(c); setError(''); })
      .catch(() => setError('Could not load the variable catalogue. Is the backend running on port 8000?'));
  }, [refreshKey]);

  const byId = useMemo(() => {
    const map = new Map<string, CatalogueVariable>();
    catalogue?.variables.forEach((v) => map.set(v.id, v));
    return map;
  }, [catalogue]);

  const categoryLabel = (key: string) => catalogue?.categories.find((c) => c.key === key)?.label ?? key;

  const filtered = useMemo(() => {
    if (!catalogue) return [];
    return catalogue.variables.filter((v) =>
      (category === 'all' || v.categories.includes(category)) &&
      (level === 'all' || v.level === level) &&
      (availability === 'all' || v.status === availability) &&
      matches(v, search.trim()));
  }, [catalogue, category, level, availability, search]);

  const investigate = (v: CatalogueVariable, extra: Partial<AnalysisPreset> = {}) => {
    if (v.status !== 'available' || !v.dataset_key || !v.variable_id) return;
    onInvestigate({ datasetKey: v.dataset_key, variableId: v.variable_id, ...extra });
  };

  if (error) return <div className="vd-overlay"><div className="vd-error">{error}</div></div>;
  if (!catalogue) return <div className="vd-overlay"><div className="vd-loading">LOADING CATALOGUE...</div></div>;

  const availableCount = catalogue.variables.filter((v) => v.status === 'available').length;

  return (
    <div className="vd-overlay">
      <div className="vd-header">
        <div>
          <div className="vd-title">VARIABLE DISCOVERY</div>
          <div className="vd-subtitle">
            {availableCount} variables ready to analyze · {catalogue.variables.length - availableCount} need an
            additional dataset
          </div>
        </div>
        <div className="vd-tabs">
          <button className={tab === 'variables' ? 'active' : ''} onClick={() => setTab('variables')}>CATALOGUE</button>
          <button className={tab === 'questions' ? 'active' : ''} onClick={() => setTab('questions')}>TREND QUESTIONS</button>
        </div>
      </div>

      <div className="vd-legend">
        <span className="vd-badge available">ANALYZABLE</span> NASA data can be downloaded and tested here.
        <span className="vd-badge requires">NEEDS DATASET</span> Not in the supported datasets.
        Being analyzable does not mean a trend exists. Only a completed analysis can show one.
      </div>

      {tab === 'variables' && (
        <>
          <div className="vd-filters">
            <input
              className="vd-search"
              type="search"
              placeholder="Search: rain, soil moisture, dust, T2M..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
            <select value={level} onChange={(e) => setLevel(e.target.value)}>
              <option value="all">All levels</option>
              {catalogue.levels.map((l) => (
                <option key={l.key} value={l.key} title={l.label}>
                  {l.key.charAt(0).toUpperCase() + l.key.slice(1)}
                </option>
              ))}
            </select>
            <select value={availability} onChange={(e) => setAvailability(e.target.value as Availability)}>
              <option value="all">All variables</option>
              <option value="available">Analyzable only</option>
              <option value="requires_dataset">Needs additional dataset</option>
            </select>
          </div>
          <div className="vd-chips">
            <button className={category === 'all' ? 'active' : ''} onClick={() => setCategory('all')}>ALL</button>
            {catalogue.categories.map((c) => (
              <button
                key={c.key}
                title={c.description}
                className={category === c.key ? 'active' : ''}
                onClick={() => setCategory(c.key)}
              >
                {c.label.toUpperCase()}
              </button>
            ))}
          </div>

          <div className="vd-list">
            {filtered.length === 0 && <div className="vd-empty">No variables match. Try a different word or clear a filter.</div>}
            {filtered.map((v) => {
              const open = expanded === v.id;
              return (
                <div key={v.id} className={`vd-card ${open ? 'open' : ''} ${v.status}`}>
                  <button className="vd-card-head" onClick={() => setExpanded(open ? null : v.id)}>
                    <div className="vd-card-names">
                      <span className="vd-common">{v.common_name}</span>
                      <span className="vd-scientific">
                        {v.scientific_name}{v.variable_id ? ` · ${v.variable_id}` : ''}
                      </span>
                    </div>
                    <div className="vd-card-badges">
                      {v.categories.map((c) => <span key={c} className="vd-badge cat">{categoryLabel(c).toUpperCase()}</span>)}
                      <span className="vd-badge level">{v.level.toUpperCase()}</span>
                      {v.status === 'available'
                        ? <span className="vd-badge available">ANALYZABLE</span>
                        : <span className="vd-badge requires">NEEDS DATASET</span>}
                      {v.status === 'available' && (
                        <span className={`vd-badge ${v.analyses.length ? 'tested' : 'untested'}`}>
                          {v.analyses.length ? `TESTED ×${v.analyses.length}` : 'NOT YET TESTED'}
                        </span>
                      )}
                    </div>
                  </button>
                  <div className="vd-card-short">{v.short_description}</div>

                  {open && (
                    <div className="vd-card-body">
                      <div className="vd-section">
                        <div className="vd-label">IN PLAIN LANGUAGE</div>
                        <p>{v.plain_language}</p>
                      </div>
                      <div className="vd-section">
                        <div className="vd-label">WHY TEST IT FOR A TREND</div>
                        <p>{v.why_trend}</p>
                      </div>

                      {v.status === 'available' && v.coverage && (
                        <>
                          <div className="vd-facts">
                            <div><span>UNITS</span>{v.units}</div>
                            <div><span>READING IT</span>{v.trend_direction_hint}</div>
                            <div><span>DATASET</span>{v.dataset_title} ({v.dataset_key})</div>
                            <div><span>ARCHIVE</span>{v.coverage.archive}</div>
                            <div><span>SOURCE</span>{v.coverage.source_type}</div>
                            <div><span>SPATIAL RESOLUTION</span>{v.coverage.spatial_resolution}</div>
                            <div><span>SPATIAL COVERAGE</span>{v.coverage.spatial_coverage}</div>
                            <div><span>TIME SPAN</span>{year(v.coverage.period_start)} – {v.coverage.period_end}</div>
                            <div><span>TIME STEP</span>{v.coverage.temporal_resolution}</div>
                            <div><span>WAIT FOR 10 YEARS</span>{formatWait(v.coverage.load_seconds_per_year * 10)}</div>
                          </div>
                          {v.other_datasets && v.other_datasets.length > 0 && (
                            <div className="vd-section">
                              <div className="vd-label">OTHER NASA DATASETS (NOT YET SUPPORTED HERE)</div>
                              {v.other_datasets.map((d) => (
                                <p key={d.short_name} className="vd-dataset">
                                  <strong>{d.short_name}</strong> · {d.archive} · {d.period}<br />{d.note}
                                </p>
                              ))}
                            </div>
                          )}
                          <TrendStatus analyses={v.analyses} alpha={catalogue.alpha} />
                          <button className="vd-go" onClick={() => investigate(v)}>
                            INVESTIGATE ON THE GLOBE →
                          </button>
                        </>
                      )}

                      {v.status === 'requires_dataset' && (
                        <>
                          <div className="vd-facts">
                            <div><span>TYPICAL UNITS</span>{v.units}</div>
                            <div><span>WHY NOT AVAILABLE</span>{v.reason_unavailable}</div>
                          </div>
                          <div className="vd-section">
                            <div className="vd-label">RECOMMENDED NASA DATASET</div>
                            {v.required_datasets?.map((d) => (
                              <p key={d.short_name} className="vd-dataset">
                                <strong>{d.short_name}</strong> · {d.archive} · {d.period}<br />{d.title}. {d.note}
                              </p>
                            ))}
                          </div>
                          {v.closest_available ? (
                            <button
                              className="vd-go secondary"
                              onClick={() => { const c = byId.get(v.closest_available!.id); if (c) investigate(c); }}
                            >
                              INVESTIGATE CLOSEST AVAILABLE: {v.closest_available.common_name.toUpperCase()}
                            </button>
                          ) : (
                            <p className="vd-fineprint">No supported variable is a reasonable substitute.</p>
                          )}
                        </>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </>
      )}

      {tab === 'questions' && (
        <div className="vd-list">
          <p className="vd-fineprint" style={{ marginBottom: 12 }}>
            These are open questions to test, not findings. The answer comes only from running the analysis.
          </p>
          {catalogue.questions.map((q: TrendQuestion) => {
            const v = q.variable_key ? byId.get(q.variable_key) : undefined;
            const missing = q.unavailable_id ? byId.get(q.unavailable_id) : undefined;
            const answered = v?.analyses.filter((a) =>
              a.region_name === q.region.name &&
              year(a.time_range_start) === String(q.start_year) &&
              year(a.time_range_end) === String(q.end_year)) ?? [];
            const years = q.end_year - q.start_year + 1;
            return (
              <div key={q.id} className={`vd-card question ${missing ? 'requires_dataset' : 'available'}`}>
                <div className="vd-question">{q.question}</div>
                <p className="vd-card-short">{q.why}</p>
                <div className="vd-facts compact">
                  {missing && (
                    <div>
                      <span>NEEDS</span>
                      {missing.common_name} from {missing.required_datasets?.map((d) => d.short_name).join(', ')}
                    </div>
                  )}
                  {v && <div><span>{missing ? 'CLOSEST AVAILABLE' : 'VARIABLE'}</span>{v.common_name} ({v.dataset_key}/{v.variable_id})</div>}
                  <div><span>REGION</span>{q.region.name}</div>
                  <div><span>PERIOD</span>{q.start_year}–{q.end_year} ({years} years)</div>
                  {v?.coverage && <div><span>EXPECTED WAIT</span>{formatWait(v.coverage.load_seconds_per_year * years)}</div>}
                  <div>
                    <span>STATUS</span>
                    {answered.length
                      ? <span className={`vd-sig vd-sig-${answered[answered.length - 1].significance}`}>
                          {SIGNIFICANCE_LABEL[answered[answered.length - 1].significance]}
                        </span>
                      : 'Not yet tested'}
                  </div>
                </div>
                {v && (
                  <button
                    className={`vd-go ${missing ? 'secondary' : ''}`}
                    onClick={() => investigate(v, { region: q.region, startYear: q.start_year, endYear: q.end_year })}
                  >
                    {missing ? 'INVESTIGATE WITH CLOSEST AVAILABLE VARIABLE' : 'INVESTIGATE THIS QUESTION'}
                  </button>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
