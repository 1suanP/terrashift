/** The featured variables in the explorer. Ids refer to the discovery catalogue. */
export interface FeaturedVariable {
  id: string; // catalogue id ("dataset/variable", or an unavailable entry id)
  label: string;
  icon: 'precipitation' | 'temperature' | 'soil' | 'evaporation' | 'streamflow';
}

export const FEATURED: FeaturedVariable[] = [
  { id: 'GPM_3IMERGM/precipitation', label: 'Precipitation', icon: 'precipitation' },
  { id: 'M2TMNXSLV/T2M', label: 'Temperature', icon: 'temperature' },
  { id: 'M2TMNXLND/GWETTOP', label: 'Soil moisture', icon: 'soil' },
  { id: 'M2TMNXFLX/EVAP', label: 'Evaporation', icon: 'evaporation' },
  { id: 'streamflow', label: 'Streamflow', icon: 'streamflow' },
];

export const DEFAULT_VARIABLE = FEATURED[0].id;

export const DEFAULT_PERIOD = { start: 2014, end: 2023 };
