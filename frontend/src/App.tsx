/**
 * TerraShift - Earth exploration interface. "Every shift tells a story."
 *
 * Modes (all share the same globe):
 *   Explore  - pick a variable, click Earth, analyze the trend
 *   Discover - searchable variable catalogue and trend questions
 *   Guided   - Explore with a step-by-step coach
 *   Expert   - the full analysis form (AnalysisPanel), fed by globe clicks
 *   Demo     - ready-made investigations on real data
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { EarthGlobe } from './components/EarthGlobe';
import type { GlobeHandle, SunMode } from './components/EarthGlobe';
import { LayerMenu } from './components/LayerMenu';
import { AnalysisPanel } from './components/AnalysisPanel';
import type { AnalysisPreset } from './components/AnalysisPanel';
import { VariableDiscovery } from './components/VariableDiscovery';
import { VariableSelector } from './components/VariableSelector';
import { LocationPanel } from './components/LocationPanel';
import type { CoverageState, Period, Selection } from './components/LocationPanel';
import { TimeSlider } from './components/TimeSlider';
import { DemoPanel } from './components/DemoPanel';
import { GuidedSteps } from './components/GuidedSteps';
import { TooltipLayer } from './components/TooltipLayer';
import { BrandMark } from './components/BrandMark';
import { BRAND } from './brand';
import { SearchBar } from './components/SearchBar';
import type { PlacePick } from './components/SearchBar';
import { IconBox, IconClose, IconInfo, IconLayers, IconMinus, IconPlus, IconReset, IconRotate } from './components/icons';
import apiService from './services/api';
import type { AnalysisRequest, Catalogue, DemoPresetInfo, MapLayerInfo, ReverseGeocode } from './services/api';
import { useMapLayer } from './hooks/useMapLayer';
import type { MapLayerState } from './hooks/useMapLayer';
import { useTrendAnalysis } from './hooks/useTrendAnalysis';
import type { BBox, LatLon } from './lib/geo';
import { boxAroundPoint, boxCenter, boxSpan, formatLatLon } from './lib/geo';
import type { Palette } from './lib/colorScales';
import { MONTH_NAMES, PALETTES, colorFor, meanInBox, sampleGrid } from './lib/colorScales';
import { DEFAULT_PERIOD, DEFAULT_VARIABLE } from './lib/variables';
import './App.css';

type Mode = 'explore' | 'discover' | 'guided' | 'expert' | 'demo';

const MODES: { key: Mode; label: string; tip: string }[] = [
  { key: 'explore', label: 'Explore', tip: 'Click anywhere on Earth to investigate it' },
  { key: 'discover', label: 'Discover', tip: 'Browse every variable and suggested trend questions' },
  { key: 'guided', label: 'Guided', tip: 'Step-by-step investigation for beginners' },
  { key: 'expert', label: 'Expert', tip: 'Full control over dataset, region and period' },
  { key: 'demo', label: 'Demo', tip: 'Ready-made investigations on real data' },
];

type PlaceState = { status: 'loading' | 'done' | 'error'; data?: ReverseGeocode };

const RECENT_KEY = 'etd.recentSearches'; // storage key kept from before the rename so history survives
const MAX_RECENT = 8;
/** Bigger areas (Russia, Canada, ...) are shown by their centre point instead of one huge box. */
const MAX_REGION_SPAN = { lat: 45, lon: 60 };

const isMobile = () => window.matchMedia('(max-width: 760px)').matches;

function App() {
  const globe = useRef<GlobeHandle>(null);
  const [mode, setMode] = useState<Mode>('explore');
  const [globeReady, setGlobeReady] = useState(false);

  // Catalogue (variables, coverage, analyses) from the existing discovery API
  const [catalogue, setCatalogue] = useState<Catalogue | null>(null);
  const [catalogueError, setCatalogueError] = useState('');
  const [analysisCount, setAnalysisCount] = useState(0);
  const [layers, setLayers] = useState<MapLayerInfo[]>([]);

  useEffect(() => {
    apiService.getCatalogue()
      .then((c) => { setCatalogue(c); setCatalogueError(''); })
      .catch(() => setCatalogueError('Could not reach the backend on port 8000. Start it with: uvicorn api.main:app --reload'));
  }, [analysisCount]);
  useEffect(() => { apiService.getMapLayers().then(setLayers).catch(() => setLayers([])); }, []);

  // Explorer state
  const [variableId, setVariableId] = useState(DEFAULT_VARIABLE);
  const [userPickedVariable, setUserPickedVariable] = useState(false);
  const [selection, setSelection] = useState<Selection | null>(null);
  const [place, setPlace] = useState<PlaceState>({ status: 'done' });
  const [period, setPeriod] = useState<Period>(DEFAULT_PERIOD);
  const [useAnomalies, setUseAnomalies] = useState(true);
  const [drawMode, setDrawMode] = useState(false);
  const [autoRotate, setAutoRotate] = useState(true);
  const [layerOn, setLayerOn] = useState(true);
  const [cloudsOn, setCloudsOn] = useState(true);
  const [sunMode, setSunMode] = useState<SunMode>('camera');
  const [gridOn, setGridOn] = useState(false);
  const [layerMenu, setLayerMenu] = useState(false);
  const [stats, setStats] = useState<{ fps: number; tier: string } | null>(null);
  const [leftCollapsed, setLeftCollapsed] = useState(isMobile());
  const [rightCollapsed, setRightCollapsed] = useState(false);
  const [showAbout, setShowAbout] = useState(false);
  const [showHint, setShowHint] = useState(true);
  const [preset, setPreset] = useState<AnalysisPreset | null>(null);
  const [demoActive, setDemoActive] = useState<string | null>(null);

  const onAnalysisComplete = useCallback(() => setAnalysisCount((n) => n + 1), []);
  const trend = useTrendAnalysis(onAnalysisComplete);

  const byId = useMemo(() => new Map((catalogue?.variables ?? []).map((v) => [v.id, v])), [catalogue]);
  const variable = byId.get(variableId);
  const closestAvailable = variable?.closest_available ? byId.get(variable.closest_available.id) : undefined;

  // Data layer on the globe: the selected variable's real NASA monthly map, if it has one
  const layerInfo = layers.find((l) => l.key === variableId && PALETTES[l.key]);
  const palette: Palette | null = layerInfo ? PALETTES[layerInfo.key] : null;
  const layerActive = Boolean(layerInfo) && layerOn && mode !== 'discover' && mode !== 'expert';
  const mapLayer = useMapLayer(layerInfo?.key ?? null, palette, layerActive, layerInfo?.first_year ?? 2001, new Date().getFullYear());
  const cloudsVisible = cloudsOn && !(layerActive && mapLayer.canvas);
  const variableKind = variable?.coverage?.source_type.toLowerCase().startsWith('reanalysis') ? 'Reanalysis model' : 'Satellite observations';

  // Keep the period inside the variable's coverage
  useEffect(() => {
    if (!variable?.coverage) return;
    const first = Number(variable.coverage.period_start.slice(0, 4)) + (variable.coverage.period_start.slice(5, 7) === '01' ? 0 : 1);
    const last = new Date().getFullYear() - 1;
    setPeriod((p) => {
      const start = Math.max(first, Math.min(p.start, last - 1));
      const end = Math.min(last, Math.max(p.end, start + 1));
      return start === p.start && end === p.end ? p : { start, end };
    });
  }, [variable?.id, variable?.coverage]);

  // Reverse geocode the selected point (or region centre)
  const selKey = selection
    ? selection.kind === 'point' ? `p${selection.point.lat.toFixed(3)},${selection.point.lon.toFixed(3)}`
      : `b${selection.box.min_lat},${selection.box.max_lat},${selection.box.min_lon},${selection.box.max_lon}`
    : '';
  useEffect(() => {
    if (!selection) return;
    // Places picked from search already have a name and country: no extra lookup
    if (selection.subtitle !== undefined) {
      setPlace({ status: 'done' });
      return;
    }
    const c = selection.kind === 'point' ? selection.point : boxCenter(selection.box);
    let cancelled = false;
    setPlace({ status: 'loading' });
    apiService.reverseGeocode(c.lat, c.lon)
      .then((data) => !cancelled && setPlace({ status: 'done', data }))
      .catch(() => !cancelled && setPlace({ status: 'error' }));
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selKey]);

  // Which variables actually have NASA data here (checked against real grids)
  const [coverage, setCoverage] = useState<CoverageState>({ status: 'loading' });
  useEffect(() => {
    if (!selection) return;
    let cancelled = false;
    setCoverage({ status: 'loading' });
    const area = selection.kind === 'point' ? { lat: selection.point.lat, lon: selection.point.lon } : selection.box;
    apiService.getCoverage(area)
      .then((data) => !cancelled && setCoverage({ status: 'done', data }))
      .catch(() => !cancelled && setCoverage({ status: 'error' }));
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selKey]);

  // Session search history (sessionStorage: survives reloads, cleared when the tab closes)
  const [recent, setRecent] = useState<PlacePick[]>(() => {
    try {
      return JSON.parse(sessionStorage.getItem(RECENT_KEY) || '[]') as PlacePick[];
    } catch {
      return [];
    }
  });
  useEffect(() => {
    try { sessionStorage.setItem(RECENT_KEY, JSON.stringify(recent)); } catch { /* storage disabled */ }
  }, [recent]);

  // A new place or variable invalidates the shown result. Reset explicitly in each
  // handler (not in an effect) so Demo can select a region and start a run in one step.
  const { reset: resetTrend } = trend;

  // ------------------------------------------------------------------ actions
  const flyToBox = (box: BBox) => {
    const span = boxSpan(box);
    globe.current?.flyTo(boxCenter(box), Math.min(3.2, Math.max(1.45, 1.3 + span / 40)));
  };

  const selectVariable = (id: string) => {
    if (id !== variableId) resetTrend();
    setVariableId(id);
    setUserPickedVariable(true);
    setLayerOn(true);
  };

  // Layer menu: picking a data layer also selects that variable, so the map, the
  // location card, and the trend analysis always describe the same thing.
  const chooseDataLayer = (key: string | null) => {
    if (key === null) {
      setLayerOn(false);
      return;
    }
    if (key !== variableId) selectVariable(key);
    setLayerOn(true);
  };

  const handlePick = useCallback((p: LatLon) => {
    setAutoRotate(false);
    setShowHint(false);
    setDemoActive(null);
    resetTrend();
    setSelection({ kind: 'point', point: p });
    setRightCollapsed(false);
    globe.current?.flyTo(p, 2.0);
    if (mode === 'expert') {
      const ds = variable?.dataset_key ?? 'M2TMNXSLV';
      setPreset({ region: { name: formatLatLon(p), ...boxAroundPoint(p, ds) }, nonce: Date.now() });
    }
  }, [mode, variable?.dataset_key, resetTrend]);

  // Search → globe. Countries, states and regions become a region (their bounding box)
  // when the box is a sensible size; cities, places and coordinates become a point.
  const handleSearchSelect = (p: PlacePick) => {
    setAutoRotate(false);
    setShowHint(false);
    setDemoActive(null);
    setDrawMode(false);
    resetTrend();
    setRightCollapsed(false);
    if (mode === 'discover') setMode('explore');
    setRecent((r) => [{ ...p }, ...r.filter((x) => x.key !== p.key)].slice(0, MAX_RECENT));

    const meta = p.kind === 'coordinates'
      ? {} // let reverse geocoding name it
      : { name: p.name, subtitle: p.subtitle, attribution: p.attribution };
    const areaKind = p.kind === 'country' || p.kind === 'state' || p.kind === 'region';
    const box = p.bbox;
    const usable = box && box.max_lat - box.min_lat <= MAX_REGION_SPAN.lat && box.max_lon - box.min_lon <= MAX_REGION_SPAN.lon
      && box.max_lat - box.min_lat >= 0.3 && box.max_lon - box.min_lon >= 0.3;
    if (areaKind && box && usable) {
      setSelection({ kind: 'region', box, ...meta });
      flyToBox(box);
      if (mode === 'expert') setPreset({ region: { name: p.name, ...box }, nonce: Date.now() });
      return;
    }
    const point = { lat: p.lat, lon: p.lon };
    const note = areaKind && box && !usable ? `${p.subtitle ? `${p.subtitle} · ` : ''}too large to analyze as one box; showing its centre` : p.subtitle;
    setSelection({ kind: 'point', point, ...meta, ...(p.kind === 'coordinates' ? {} : { subtitle: note }) });
    globe.current?.flyTo(point, areaKind ? 2.6 : p.kind === 'city' || p.kind === 'district' ? 1.55 : 1.6);
    if (mode === 'expert') {
      setPreset({ region: { name: p.name, ...boxAroundPoint(point, variable?.dataset_key ?? 'M2TMNXSLV') }, nonce: Date.now() });
    }
  };

  const handleRegion = useCallback((box: BBox) => {
    setDrawMode(false);
    setAutoRotate(false);
    setShowHint(false);
    setDemoActive(null);
    resetTrend();
    setSelection({ kind: 'region', box });
    setRightCollapsed(false);
    flyToBox(box);
    if (mode === 'expert') setPreset({ region: { name: 'Drawn region', ...box }, nonce: Date.now() });
  }, [mode, resetTrend]);

  const analysisBox = (): BBox | null => {
    if (!selection || !variable?.dataset_key) return null;
    return selection.kind === 'point' ? boxAroundPoint(selection.point, variable.dataset_key) : selection.box;
  };

  const runTrend = (overrides?: { period?: Period; variableKey?: string; box?: BBox; name?: string; anomalies?: boolean }) => {
    const v = overrides?.variableKey ? byId.get(overrides.variableKey) : variable;
    const box = overrides?.box ?? analysisBox();
    const per = overrides?.period ?? period;
    if (!v?.dataset_key || !v.variable_id || !box) return;
    const name = overrides?.name
      || selection?.name
      || (place.data?.found ? place.data.place || place.data.region || place.data.country : undefined)
      || (selection?.kind === 'point' ? formatLatLon(selection.point) : 'Selected region');
    const request: AnalysisRequest = {
      dataset_key: v.dataset_key,
      variable_id: v.variable_id,
      ...box,
      time_range_start: `${per.start}-01-01`,
      time_range_end: `${per.end}-12-31`,
      use_anomalies: overrides?.anomalies ?? useAnomalies,
      region_name: name || 'Selected region',
    };
    const years = per.end - per.start + 1;
    trend.run(request, (v.coverage?.load_seconds_per_year ?? 10) * years + 10);
  };

  const clearSelection = () => {
    setSelection(null);
    setDemoActive(null);
    resetTrend();
  };

  const resetView = () => {
    globe.current?.reset();
    setDrawMode(false);
  };

  // Discover → Explore with the chosen variable (and region / years if a question had them)
  const handleInvestigate = (p: Omit<AnalysisPreset, 'nonce'>) => {
    if (!p.datasetKey || !p.variableId) return;
    const id = `${p.datasetKey}/${p.variableId}`;
    resetTrend();
    setPreset({ ...p, nonce: Date.now() });
    setVariableId(id);
    setUserPickedVariable(true);
    if (p.startYear && p.endYear) setPeriod({ start: p.startYear, end: p.endYear });
    if (p.region) {
      const { name, ...box } = p.region;
      setSelection({ kind: 'region', box, name });
      setTimeout(() => flyToBox(box), 50);
    }
    setAutoRotate(false);
    setShowHint(false);
    setRightCollapsed(false);
    setMode('explore');
  };

  const runDemo = (p: DemoPresetInfo) => {
    const id = `${p.dataset_key}/${p.variable_id}`;
    const v = byId.get(id);
    const box: BBox = { min_lat: p.min_lat, max_lat: p.max_lat, min_lon: p.min_lon, max_lon: p.max_lon };
    const last = new Date().getFullYear() - 1;
    const start = Math.max(Number(p.time_range_start.slice(0, 4)), last - 9);
    const per = { start, end: Math.min(last, Number(p.time_range_end.slice(0, 4))) };
    setVariableId(id);
    setLayerOn(true);
    setSelection({ kind: 'region', box, name: p.region_name });
    setPeriod(per);
    setUseAnomalies(p.use_anomalies);
    setDemoActive(p.name);
    setAutoRotate(false);
    setShowHint(false);
    setRightCollapsed(false);
    flyToBox(box);
    if (v) runTrend({ period: per, variableKey: id, box, name: p.region_name, anomalies: p.use_anomalies });
  };

  // Keyboard: Esc leaves draw mode, then clears the selection
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return;
      // Esc inside a text field belongs to that field (e.g. closing search suggestions)
      if ((e.target as HTMLElement | null)?.closest?.('input, textarea, select')) return;
      if (drawMode) setDrawMode(false);
      else if (showAbout) setShowAbout(false);
      else if (selection) clearSelection();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  });

  // Value under the selection from the current data-layer map
  const mapValue = useMemo(() => {
    if (!layerActive || !palette || !mapLayer.grid || !selection || mapLayer.month === null) return null;
    const value = selection.kind === 'point'
      ? sampleGrid(mapLayer.grid, selection.point.lat, selection.point.lon)
      : meanInBox(mapLayer.grid, selection.box);
    const [r, g, b] = value === null ? [0, 0, 0] : colorFor(palette, Math.max(value, palette.clearBelow ? palette.stops[1].value : value));
    return {
      value,
      units: mapLayer.grid.units,
      decimals: palette.decimals,
      color: value === null ? 'transparent' : `rgb(${Math.round(r)},${Math.round(g)},${Math.round(b)})`,
      label: `${MONTH_NAMES[mapLayer.month - 1]} ${mapLayer.year} · ${selection.kind === 'point' ? 'at this point' : 'region average'}`,
      note: `From the globe map: ${mapLayer.grid.sampling_note}`,
    };
  }, [layerActive, palette, mapLayer.grid, mapLayer.month, mapLayer.year, selection]);

  // Performance read-out for the About panel (updated only while it is open)
  const aboutOpen = useRef(false);
  aboutOpen.current = showAbout;
  const onStats = useCallback((s: { fps: number; tier: string }) => { if (aboutOpen.current) setStats(s); }, []);

  // Hover read-out without re-rendering the whole app on every mouse move
  const hoverListeners = useRef(new Set<(p: LatLon | null) => void>());
  const onHover = useCallback((p: LatLon | null) => hoverListeners.current.forEach((fn) => fn(p)), []);

  const showExplorerPanels = mode === 'explore' || mode === 'guided' || mode === 'demo';
  const marker = selection?.kind === 'point' ? selection.point : null;
  const region = selection?.kind === 'region' ? selection.box : null;
  const placeName = selection?.name
    || (place.data?.found ? place.data.place || place.data.region || place.data.country : null)
    || null;
  const globeLabel = selection && placeName
    ? { ...(selection.kind === 'point' ? selection.point : boxCenter(selection.box)), text: placeName }
    : null;

  const hasRight = showExplorerPanels && Boolean(selection) && !rightCollapsed;
  const hasTimebar = layerActive;

  return (
    <div className={`app mode-${mode} ${hasRight ? 'has-right' : ''} ${hasTimebar ? 'has-timebar' : ''}`}>
      <EarthGlobe
        ref={globe}
        marker={marker}
        region={region}
        label={showExplorerPanels || mode === 'expert' ? globeLabel : null}
        drawMode={drawMode && mode !== 'discover'}
        overlay={layerActive ? mapLayer.canvas : null}
        overlayVersion={mapLayer.month ?? 0}
        autoRotate={autoRotate && !selection}
        clouds={cloudsVisible}
        sunMode={sunMode}
        showGrid={gridOn}
        onPick={handlePick}
        onRegion={handleRegion}
        onHover={onHover}
        onReady={() => setGlobeReady(true)}
        onStats={onStats}
      />
      {!globeReady && <div className="globe-loading"><div className="spinner" /> Loading Earth…</div>}

      {/* ---------------------------------------------------------- top bar */}
      <header className="topbar">
        <div className="brand" onClick={() => { setMode('explore'); resetView(); }} role="button" tabIndex={0}
          onKeyDown={(e) => e.key === 'Enter' && setMode('explore')} aria-label={`${BRAND.name} home`} data-tip={BRAND.description}>
          <BrandMark />
          <span className="brand-text">
            <span className="brand-name">Terra<span className="brand-accent">Shift</span></span>
            <span className="brand-sub">{BRAND.tagline}</span>
          </span>
        </div>
        <SearchBar
          onSelect={handleSearchSelect}
          recent={recent}
          onClearRecent={() => setRecent([])}
          hasSelection={Boolean(selection)}
          onClearSelection={clearSelection}
          onResetView={resetView}
        />
        <nav className="tabs" aria-label="Modes">
          {MODES.map((m) => (
            <button key={m.key} className={`tab ${mode === m.key ? 'on' : ''}`} onClick={() => setMode(m.key)}
              data-tip={m.tip} aria-current={mode === m.key ? 'page' : undefined}>
              {m.label}
            </button>
          ))}
        </nav>
        <button className="icon-btn subtle about-btn" onClick={() => setShowAbout((s) => !s)} data-tip="About, data sources & help" aria-label="About">
          <IconInfo />
        </button>
      </header>

      {/* ---------------------------------------------------------- left */}
      {showExplorerPanels && (
        <div className="left-dock">
          {mode === 'guided' && (
            <GuidedSteps
              variableChosen={userPickedVariable}
              placeChosen={Boolean(selection)}
              analyzed={trend.state.status === 'done'}
              variableName={variable?.common_name ?? 'the variable'}
            />
          )}
          {mode === 'demo' ? (
            <DemoPanel onRun={runDemo} activeName={demoActive} collapsed={leftCollapsed} onToggle={() => setLeftCollapsed((c) => !c)} />
          ) : (
            <VariableSelector
              variables={catalogue?.variables ?? []}
              selectedId={variableId}
              onSelect={selectVariable}
              collapsed={leftCollapsed}
              onToggle={() => setLeftCollapsed((c) => !c)}
              loading={!catalogue && !catalogueError}
              error={catalogueError}
            />
          )}
        </div>
      )}

      {mode === 'expert' && (
        <div className="left-dock expert-dock">
          <div className="glass expert-note">
            <strong>Expert mode.</strong> Choose any dataset and variable. Click the globe or draw a box to set the region.
          </div>
          <AnalysisPanel preset={preset} onAnalysisComplete={onAnalysisComplete} />
        </div>
      )}

      {mode === 'discover' && (
        <div className="discover-wrap">
          <VariableDiscovery refreshKey={analysisCount} onInvestigate={handleInvestigate} />
        </div>
      )}

      {/* ---------------------------------------------------------- right */}
      {showExplorerPanels && selection && (
        <div className="right-dock">
          <LocationPanel
            selection={selection}
            place={place}
            variable={variable}
            closestAvailable={closestAvailable}
            variables={catalogue?.variables ?? []}
            coverage={coverage}
            mapValue={mapValue}
            period={period}
            onPeriod={setPeriod}
            useAnomalies={useAnomalies}
            onUseAnomalies={setUseAnomalies}
            trend={trend.state}
            onAnalyze={() => runTrend()}
            onSwitchVariable={selectVariable}
            onClose={clearSelection}
            collapsed={rightCollapsed}
            onToggle={() => setRightCollapsed((c) => !c)}
            alpha={catalogue?.alpha ?? 0.05}
          />
        </div>
      )}

      {/* ---------------------------------------------------------- globe tools */}
      {mode !== 'discover' && (
        <div className="globe-tools glass" role="toolbar" aria-label="Globe controls">
          <button className="icon-btn" onClick={() => globe.current?.zoomBy(0.8)} data-tip="Zoom in" aria-label="Zoom in"><IconPlus /></button>
          <button className="icon-btn" onClick={() => globe.current?.zoomBy(1.25)} data-tip="Zoom out" aria-label="Zoom out"><IconMinus /></button>
          <button className={`icon-btn ${drawMode ? 'active' : ''}`} onClick={() => setDrawMode((d) => !d)}
            data-tip={drawMode ? 'Drawing: drag on Earth (Esc to cancel)' : 'Draw a region'} aria-pressed={drawMode} aria-label="Draw a region">
            <IconBox />
          </button>
          <button className={`icon-btn ${layerMenu ? 'active' : ''}`} onClick={() => setLayerMenu((o) => !o)}
            data-tip="Layers: NASA data maps, clouds, sunlight" aria-expanded={layerMenu} aria-label="Layers">
            <IconLayers />
          </button>
          <button className={`icon-btn ${autoRotate ? 'active' : ''}`} onClick={() => setAutoRotate((a) => !a)}
            data-tip={autoRotate ? 'Stop spinning' : 'Spin slowly'} aria-pressed={autoRotate} aria-label="Toggle auto-rotate">
            <IconRotate />
          </button>
          <button className="icon-btn" onClick={resetView} data-tip="Reset view" aria-label="Reset view"><IconReset /></button>
        </div>
      )}

      {layerMenu && mode !== 'discover' && (
        <LayerMenu
          layers={mode === 'expert' ? [] : layers}
          activeKey={layerInfo?.key ?? null}
          dataOn={layerOn}
          onData={chooseDataLayer}
          clouds={cloudsOn}
          cloudsHidden={!cloudsVisible}
          onClouds={setCloudsOn}
          sunMode={sunMode}
          onSunMode={setSunMode}
          grid={gridOn}
          onGrid={setGridOn}
          onClose={() => setLayerMenu(false)}
        />
      )}

      {drawMode && mode !== 'discover' && (
        <div className="draw-banner glass">
          Drag across Earth to draw a region <button className="link-btn" onClick={() => setDrawMode(false)}>Cancel</button>
        </div>
      )}

      {/* ---------------------------------------------------------- bottom */}
      {layerActive && layerInfo && palette && (
        <div className="bottom-dock">
          <TimeSlider layer={mapLayer} palette={palette} source={layerInfo.source} resolution={layerInfo.resolution_label} kind={variableKind} />
        </div>
      )}

      {mode !== 'discover' && (
        <HoverReadout listeners={hoverListeners.current} grid={layerActive ? mapLayer.grid : null} decimals={palette?.decimals ?? 1} />
      )}

      {showHint && !selection && mode !== 'discover' && globeReady && (
        <div className="hint-toast glass welcome" role="note" aria-label={`Welcome to ${BRAND.name}`}>
          <div className="welcome-copy">
            <div className="welcome-tagline">{BRAND.tagline}</div>
            <div className="welcome-desc">{BRAND.description}</div>
          </div>
          <div className="welcome-hints">
            <span><b>Search</b> or <b>click</b> a place</span>
            <span><b>Drag</b> to rotate</span>
            <span><b>Scroll</b> to zoom</span>
          </div>
          <button className="icon-btn subtle welcome-close" onClick={() => setShowHint(false)} aria-label="Dismiss welcome"><IconClose /></button>
        </div>
      )}

      <TooltipLayer />

      {showAbout && (
        <About
          onClose={() => setShowAbout(false)}
          counts={catalogue ? {
            datasets: new Set(catalogue.variables.filter((v) => v.dataset_key).map((v) => v.dataset_key)).size,
            variables: catalogue.variables.filter((v) => v.status === 'available').length,
          } : null}
          backendOk={Boolean(catalogue)}
          stats={stats}
        />
      )}
    </div>
  );
}

const HoverReadout = ({ listeners, grid, decimals }: { listeners: Set<(p: LatLon | null) => void>; grid: MapLayerState['grid']; decimals: number }) => {
  const [p, setP] = useState<LatLon | null>(null);
  useEffect(() => {
    listeners.add(setP);
    return () => { listeners.delete(setP); };
  }, [listeners]);
  if (!p) return null;
  const v = grid ? sampleGrid(grid, p.lat, p.lon) : null;
  return (
    <div className="hover-readout">
      {formatLatLon(p)}
      {grid && <span> · {v === null ? 'no data' : `${v.toFixed(decimals)} ${grid.units}`}</span>}
    </div>
  );
};

const About = ({ onClose, counts, backendOk, stats }: {
  onClose: () => void;
  counts: { datasets: number; variables: number } | null;
  backendOk: boolean;
  stats: { fps: number; tier: string } | null;
}) => (
  <div className="about-backdrop" onClick={onClose}>
    <section className="glass about" onClick={(e) => e.stopPropagation()} aria-label="About">
      <header className="panel-head about-head">
        <div className="about-brand">
          <BrandMark size={34} />
          <div>
            <div className="about-name">Terra<span className="brand-accent">Shift</span></div>
            <div className="about-tagline">{BRAND.tagline}</div>
          </div>
        </div>
        <button className="icon-btn subtle" onClick={onClose} aria-label="Close"><IconClose /></button>
      </header>
      <p className="about-desc">
        {BRAND.description} Pick a place and a variable, see how it has changed over the years, and find out
        whether the change is statistically significant, explained in plain language.
      </p>
      <div className="about-grid">
        <div className="stat"><strong>{counts?.datasets ?? '–'}</strong><span>NASA datasets</span></div>
        <div className="stat"><strong>{counts?.variables ?? '–'}</strong><span>analyzable variables</span></div>
        <div className="stat"><strong className={backendOk ? 'ok' : 'bad'}>{backendOk ? 'Online' : 'Offline'}</strong><span>backend (FastAPI)</span></div>
      </div>
      <h3>How to use</h3>
      <ol className="about-steps">
        <li><b>Choose a variable</b> on the left, such as precipitation or temperature.</li>
        <li><b>Click Earth</b> to pick a place, or use the box tool to draw a region.</li>
        <li><b>Analyze the trend</b> in the location card on the right.</li>
        <li><b>Read the result</b>: the chart, the plain-language summary, and the statistics.</li>
      </ol>
      <h3>Data</h3>
      <ul className="about-list">
        <li>Precipitation layer and trends: NASA GPM IMERG V07 monthly (GES DISC). Monthly averages, not real-time radar or forecasts.</li>
        <li>Temperature, soil moisture and evaporation layers, other variables: NASA MERRA-2 monthly reanalysis (GES DISC).</li>
        <li>Place names: © OpenStreetMap contributors (ODbL), via Nominatim.</li>
      </ul>
      <h3>Earth imagery</h3>
      <ul className="about-list">
        <li>Surface colour: NASA Blue Marble (public domain).</li>
        <li>City lights, clouds, terrain relief and ocean mask: <a href="https://www.solarsystemscope.com/textures/" target="_blank" rel="noreferrer">Solar System Scope</a>, CC BY 4.0, based on NASA imagery.</li>
        <li>The clouds are a representative image for realism, not current weather. They hide automatically when a data layer is on.</li>
      </ul>
      {stats && <p className="about-perf">Rendering at {stats.fps} fps with {stats.tier} textures.</p>}
      <footer className="about-foot">
        <span><b>{BRAND.name}</b> · {BRAND.tagline}</span>
        <span>Built with NASA Earth observation data for the 2026 NASA Space Apps Challenge.</span>
      </footer>
      <p className="disclaimer">
        NASA does not endorse any non-U.S. Government entity and is not responsible for information contained on
        non-U.S. Government websites. Data from non-U.S. Government websites is used under that website's terms.
      </p>
    </section>
  </div>
);

export default App;
