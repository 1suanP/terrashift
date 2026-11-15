/**
 * API Service - Connect to FastAPI backend
 */
import axios from 'axios';

// Override with VITE_API_URL (e.g. in frontend/.env.local) when the backend runs elsewhere.
const API_BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000, // 10 seconds for config/data requests
  headers: {
    'Content-Type': 'application/json',
  },
});

// Separate client for long-running analysis
const analysisApi = axios.create({
  baseURL: API_BASE_URL,
  timeout: 360000, // 6 minutes for analysis
  headers: {
    'Content-Type': 'application/json',
  },
});

// Types
export type Dataset = {
  key: string;
  title: string;
  description: string;
  short_name: string;
  start_date: string;
  end_date: string;
};

export type Variable = {
  variable_id: string;
  long_name: string;
  short_description: string;
  plain_language: string;
  units: string;
  trend_direction_hint: string;
  dataset_key: string;
};

export interface Region {
  name: string;
  min_lat: number;
  max_lat: number;
  min_lon: number;
  max_lon: number;
}

export interface AnalysisRequest {
  dataset_key: string;
  variable_id: string;
  min_lat: number;
  max_lat: number;
  min_lon: number;
  max_lon: number;
  time_range_start: string;
  time_range_end: string;
  use_anomalies: boolean;
  region_name: string;
}

export interface AnalysisResult {
  analysis_id: string;
  dataset_key?: string;
  variable_id?: string;
  variable_name: string;
  units: string;
  region_name?: string;
  time_range_start?: string;
  time_range_end?: string;
  significance: string;
  interpretation: string;
  n_points: number;
  sens_slope_value?: number;
  linear: {
    slope: number;
    p_value: number;
    r_value: number;
    intercept?: number;
    std_err?: number;
    ci_lower?: number;
    ci_upper?: number;
  };
  mann_kendall: {
    trend: string;
    p: number;
    z?: number;
    tau?: number;
  };
  time_series: {
    timestamps: string[];
    values: (number | null)[];
    anomalies?: (number | null)[] | null;
    is_anomaly?: boolean;
  };
}

// Globe map (real NASA monthly grid, rows south → north)
export interface MapGrid {
  key: string;
  year: number;
  month: number;
  units: string;
  name: string;
  source: string;
  sampling_note: string;
  legend_max: number;
  lat_count: number;
  lon_count: number;
  lat_start: number;
  lon_start: number;
  lat_step: number;
  lon_step: number;
  values: (number | null)[];
  min: number | null;
  max: number | null;
}

export interface MapLayerInfo {
  key: string;
  dataset_key: string;
  variable_id: string;
  name: string;
  units: string;
  legend_max: number;
  resolution_label: string;
  source: string;
  resolution_deg: number;
  native_resolution_deg: number;
  first_year: number;
  last_year: number;
}

export interface ReverseGeocode {
  found: boolean;
  place?: string | null;
  region?: string | null;
  country?: string | null;
  country_code?: string | null;
  display_name?: string | null;
  lat: number;
  lon: number;
  attribution: string;
}

export interface SearchResult {
  name: string;
  subtitle: string;
  kind: 'country' | 'state' | 'region' | 'city' | 'district' | 'place';
  category: string;
  lat: number;
  lon: number;
  bbox: { min_lat: number; max_lat: number; min_lon: number; max_lon: number } | null;
  country: string | null;
  country_code: string | null;
  state: string | null;
  osm_id: string;
}

export type CoverageStatus = 'available' | 'no_data_here' | 'unknown';

export interface CoverageResponse {
  reference_month: string;
  variables: Record<string, { status: CoverageStatus; reason: string }>;
}

export interface DemoPresetInfo {
  name: string;
  description: string;
  expected_insight: string;
  dataset_key: string;
  variable_id: string;
  region_name: string;
  min_lat: number;
  max_lat: number;
  min_lon: number;
  max_lon: number;
  time_range_start: string;
  time_range_end: string;
  use_anomalies: boolean;
}

// Discovery catalogue types
export interface DatasetSuggestion {
  short_name: string;
  title: string;
  archive: string;
  period: string;
  note: string;
}

export interface CompletedAnalysis {
  analysis_id: string;
  region_name: string;
  time_range_start: string;
  time_range_end: string;
  significance: 'increasing' | 'decreasing' | 'none';
  linear_p_value: number;
  mann_kendall_p: number;
  slope_per_year: number;
  units: string;
  n_points: number;
}

export interface CatalogueVariable {
  id: string;
  status: 'available' | 'requires_dataset';
  common_name: string;
  scientific_name: string;
  categories: string[];
  level: string;
  short_description: string;
  plain_language: string;
  units: string;
  why_trend: string;
  keywords: string[];
  analyses: CompletedAnalysis[];
  // available only
  variable_id?: string;
  dataset_key?: string;
  dataset_title?: string;
  trend_direction_hint?: string;
  coverage?: {
    spatial_resolution: string;
    spatial_coverage: string;
    temporal_resolution: string;
    source_type: string;
    archive: string;
    period_start: string;
    period_end: string;
    load_seconds_per_year: number;
  };
  other_datasets?: DatasetSuggestion[];
  // requires_dataset only
  reason_unavailable?: string;
  required_datasets?: DatasetSuggestion[];
  closest_available?: { id: string; common_name: string } | null;
}

export interface CatalogueRegion {
  name: string;
  min_lat: number;
  max_lat: number;
  min_lon: number;
  max_lon: number;
}

export interface TrendQuestion {
  id: number;
  question: string;
  why: string;
  variable_key: string | null;
  unavailable_id: string | null;
  region: CatalogueRegion;
  start_year: number;
  end_year: number;
}

export interface Catalogue {
  categories: { key: string; label: string; description: string }[];
  levels: { key: string; label: string }[];
  alpha: number;
  variables: CatalogueVariable[];
  questions: TrendQuestion[];
}

// API Methods
export const apiService = {
  // Globe map layers (real NASA data)
  async getMapLayers(): Promise<MapLayerInfo[]> {
    const response = await api.get('/api/maps/layers');
    return response.data.layers;
  },

  async getMapMonths(layerKey: string, year: number): Promise<number[]> {
    const response = await api.get(`/api/maps/${layerKey}/months`, { params: { year }, timeout: 60000 });
    return response.data.months;
  },

  async getMap(layerKey: string, year: number, month: number): Promise<MapGrid> {
    // A cache miss reads one NASA granule (~10-20 s); cached months return instantly.
    const response = await api.get(`/api/maps/${layerKey}`, { params: { year, month }, timeout: 120000 });
    return response.data;
  },

  async searchPlaces(q: string, signal?: AbortSignal): Promise<{ results: SearchResult[]; attribution: string }> {
    const response = await api.get('/api/geo/search', { params: { q, limit: 6 }, signal, timeout: 12000 });
    return response.data;
  },

  /** Which variables have real data at a point or in a box (checked against NASA grids). */
  async getCoverage(area: { lat: number; lon: number } | { min_lat: number; max_lat: number; min_lon: number; max_lon: number }): Promise<CoverageResponse> {
    const response = await api.get('/api/maps/coverage', { params: area, timeout: 90000 });
    return response.data;
  },

  async reverseGeocode(lat: number, lon: number): Promise<ReverseGeocode> {
    const response = await api.get('/api/geo/reverse', { params: { lat, lon }, timeout: 15000 });
    return response.data;
  },

  async getDemoPresets(): Promise<DemoPresetInfo[]> {
    const response = await api.get('/api/config/presets');
    return response.data;
  },

  // Variable discovery catalogue
  async getCatalogue(): Promise<Catalogue> {
    const response = await api.get('/api/discovery/catalogue');
    return response.data;
  },

  // All variables across datasets
  async getAllVariables(): Promise<Variable[]> {
    const response = await api.get('/api/config/variables');
    return response.data;
  },

  // Health check
  async checkHealth() {
    const response = await api.get('/api/health');
    return response.data;
  },

  // Get datasets
  async getDatasets(): Promise<Dataset[]> {
    const response = await api.get('/api/config/datasets');
    return response.data;
  },

  // Get variables for a dataset
  async getVariables(datasetKey: string): Promise<Variable[]> {
    const response = await api.get(`/api/config/variables/${datasetKey}`);
    return response.data;
  },

  // Get regions
  async getRegions(): Promise<Record<string, Region>> {
    const response = await api.get('/api/config/regions');
    return response.data;
  },

  // Run analysis
  async runAnalysis(request: AnalysisRequest): Promise<{ analysis_id: string; status: string }> {
    const response = await analysisApi.post('/api/analysis/run', request);
    return response.data;
  },

  // Get analysis result
  async getAnalysisResult(analysisId: string): Promise<AnalysisResult> {
    const response = await analysisApi.get(`/api/analysis/${analysisId}`);
    return response.data;
  },
};

export default apiService;
