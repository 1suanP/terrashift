/**
 * Analysis Panel - User can select parameters and run analysis
 */
import { useState, useEffect, useRef } from 'react';
import apiService, { backendUnreachableMessage } from '../services/api';
import type { Dataset, Variable, AnalysisResult, Region } from '../services/api';
import './AnalysisPanel.css';

/** A selection handed over from Variable Discovery. `nonce` makes repeat clicks re-apply. */
export interface AnalysisPreset {
  /** Omit dataset/variable to update only the region or years (e.g. a globe click). */
  datasetKey?: string;
  variableId?: string;
  region?: Region;
  startYear?: number;
  endYear?: number;
  nonce: number;
}

interface AnalysisPanelProps {
  preset?: AnalysisPreset | null;
  onAnalysisComplete?: () => void;
}

export const AnalysisPanel = ({ preset = null, onAnalysisComplete }: AnalysisPanelProps) => {
  const panelRef = useRef<HTMLDivElement>(null);
  const pendingVariable = useRef<string | null>(null);
  const [highlight, setHighlight] = useState(false);
  const [regions, setRegions] = useState<Region[]>([]);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [variables, setVariables] = useState<Variable[]>([]);
  const [selectedDataset, setSelectedDataset] = useState<string>('');
  const [selectedVariable, setSelectedVariable] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState<string>('');
  
  // Region and time range
  const [minLat, setMinLat] = useState<number>(32.0);
  const [maxLat, setMaxLat] = useState<number>(42.0);
  const [minLon, setMinLon] = useState<number>(-124.0);
  const [maxLon, setMaxLon] = useState<number>(-114.0);
  const [regionName, setRegionName] = useState<string>('California');
  const [startYear, setStartYear] = useState<number>(2018);
  const [endYear, setEndYear] = useState<number>(2020);

  // Load datasets and preset regions on mount
  useEffect(() => {
    loadDatasets();
    apiService.getRegions().then((r) => setRegions(Object.values(r))).catch(() => setRegions([]));
  }, []);

  const loadDatasets = async () => {
    try {
      const data = await apiService.getDatasets();
      setDatasets(data);
      if (data.length > 0) {
        // Keep a dataset already chosen from Variable Discovery
        setSelectedDataset((prev) => prev || data[0].key);
      }
    } catch (err) {
      setError(`Failed to load datasets. ${backendUnreachableMessage()}`);
    }
  };

  const applyRegion = (r: Region) => {
    setRegionName(r.name);
    setMinLat(r.min_lat);
    setMaxLat(r.max_lat);
    setMinLon(r.min_lon);
    setMaxLon(r.max_lon);
  };

  // Apply a selection coming from Variable Discovery
  useEffect(() => {
    if (!preset) return;
    if (preset.datasetKey && preset.variableId) {
      pendingVariable.current = preset.variableId;
      if (preset.datasetKey === selectedDataset && variables.some((v) => v.variable_id === preset.variableId)) {
        setSelectedVariable(preset.variableId);
        pendingVariable.current = null;
      } else {
        setSelectedDataset(preset.datasetKey);
      }
    }
    if (preset.region) applyRegion(preset.region);
    if (preset.startYear) setStartYear(preset.startYear);
    if (preset.endYear) setEndYear(preset.endYear);
    setResult(null);
    setError('');
    panelRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    setHighlight(true);
    const timer = window.setTimeout(() => setHighlight(false), 1600);
    return () => window.clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [preset?.nonce]);

  // Load variables when dataset changes
  useEffect(() => {
    if (selectedDataset) {
      loadVariables(selectedDataset);
    }
  }, [selectedDataset]);

  const loadVariables = async (datasetKey: string) => {
    try {
      const data = await apiService.getVariables(datasetKey);
      setVariables(data);
      const pending = pendingVariable.current;
      pendingVariable.current = null;
      if (pending && data.some((v) => v.variable_id === pending)) {
        setSelectedVariable(pending);
      } else if (data.length > 0) {
        setSelectedVariable(data[0].variable_id);
      }
    } catch (err) {
      setError('Failed to load variables');
    }
  };

  const runAnalysis = async () => {
    if (!selectedDataset || !selectedVariable) return;

    setLoading(true);
    setError('');
    setResult(null);

    try {
      console.log('Starting analysis...');
      setError('Downloading NASA data... This may take 1-2 minutes.');
      
      // Simple analysis with user-selected parameters
      const response = await apiService.runAnalysis({
        dataset_key: selectedDataset,
        variable_id: selectedVariable,
        min_lat: minLat,
        max_lat: maxLat,
        min_lon: minLon,
        max_lon: maxLon,
        time_range_start: `${startYear}-01-01`,
        time_range_end: `${endYear}-12-31`,
        use_anomalies: true,
        region_name: regionName,
      });

      console.log('Analysis submitted, ID:', response.analysis_id);
      setError('Processing data...');

      // The run response carries the result; the extra GET is only for older backends.
      const analysisResult = response.result ?? (await apiService.getAnalysisResult(response.analysis_id));
      console.log('Analysis complete:', analysisResult);
      setResult(analysisResult);
      setError('');
      onAnalysisComplete?.();
    } catch (err: any) {
      console.error('Analysis error:', err);
      setError(err.response?.data?.detail || err.message || 'Analysis failed. Check backend logs.');
    } finally {
      setLoading(false);
    }
  };

  const selectedVar = variables.find(v => v.variable_id === selectedVariable);

  return (
    <div ref={panelRef} className={`analysis-panel ${highlight ? 'highlight' : ''}`}>
      <div className="panel-title">QUICK ANALYSIS</div>

      {error && <div className="error-box">{error}</div>}

      <div className="control-group">
        <label>DATASET</label>
        <select 
          value={selectedDataset} 
          onChange={(e) => setSelectedDataset(e.target.value)}
          disabled={loading}
        >
          {datasets.map(ds => (
            <option key={ds.key} value={ds.key}>{ds.title}</option>
          ))}
        </select>
      </div>

      <div className="control-group">
        <label>VARIABLE</label>
        <select 
          value={selectedVariable} 
          onChange={(e) => setSelectedVariable(e.target.value)}
          disabled={loading}
        >
          {variables.map(v => (
            <option key={v.variable_id} value={v.variable_id}>{v.long_name}</option>
          ))}
        </select>
        {selectedVar && (
          <div className="var-description">{selectedVar.short_description}</div>
        )}
      </div>

      <div className="control-group">
        <label>REGION</label>
        {regions.length > 0 && (
          <select
            value={regions.some((r) => r.name === regionName) ? regionName : ''}
            onChange={(e) => {
              const r = regions.find((x) => x.name === e.target.value);
              if (r) applyRegion(r);
            }}
            disabled={loading}
            style={{ marginBottom: '8px' }}
          >
            <option value="">Custom region</option>
            {regions.map((r) => (
              <option key={r.name} value={r.name}>{r.name}</option>
            ))}
          </select>
        )}
        <input 
          type="text" 
          value={regionName} 
          onChange={(e) => setRegionName(e.target.value)}
          placeholder="Region name"
          disabled={loading}
        />
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', marginTop: '8px' }}>
          <input 
            type="number" 
            value={minLat} 
            onChange={(e) => setMinLat(parseFloat(e.target.value))}
            placeholder="Min Lat"
            step="0.1"
            disabled={loading}
          />
          <input 
            type="number" 
            value={maxLat} 
            onChange={(e) => setMaxLat(parseFloat(e.target.value))}
            placeholder="Max Lat"
            step="0.1"
            disabled={loading}
          />
          <input 
            type="number" 
            value={minLon} 
            onChange={(e) => setMinLon(parseFloat(e.target.value))}
            placeholder="Min Lon"
            step="0.1"
            disabled={loading}
          />
          <input 
            type="number" 
            value={maxLon} 
            onChange={(e) => setMaxLon(parseFloat(e.target.value))}
            placeholder="Max Lon"
            step="0.1"
            disabled={loading}
          />
        </div>
      </div>

      <div className="control-group">
        <label>TIME PERIOD</label>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
          <input 
            type="number" 
            value={startYear} 
            onChange={(e) => setStartYear(parseInt(e.target.value))}
            placeholder="Start Year"
            min="1980"
            max="2024"
            disabled={loading}
          />
          <input 
            type="number" 
            value={endYear} 
            onChange={(e) => setEndYear(parseInt(e.target.value))}
            placeholder="End Year"
            min="1980"
            max="2024"
            disabled={loading}
          />
        </div>
      </div>

      <button 
        className="analyze-btn" 
        onClick={runAnalysis}
        disabled={loading || !selectedDataset || !selectedVariable}
      >
        {loading ? 'ANALYZING...' : 'RUN ANALYSIS'}
      </button>

      {result && (
        <div className="result-box">
          <div className="result-title">RESULTS</div>
          <div className="result-item">
            <span>Variable:</span>
            <span>{result.variable_name}</span>
          </div>
          <div className="result-item">
            <span>Trend:</span>
            <span className={`significance-${result.significance}`}>
              {result.significance.toUpperCase()}
            </span>
          </div>
          <div className="result-item">
            <span>Slope:</span>
            <span>{result.linear.slope.toFixed(4)} {result.units}/year</span>
          </div>
          <div className="result-item">
            <span>P-value:</span>
            <span>{result.linear.p_value.toExponential(2)}</span>
          </div>
          <div className="result-item">
            <span>Data Points:</span>
            <span>{result.n_points}</span>
          </div>
          <div className="interpretation">{result.interpretation}</div>
        </div>
      )}
    </div>
  );
};
