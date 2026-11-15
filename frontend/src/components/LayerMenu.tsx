/** Layer menu: choose the data layer and base-map options. */
import type { MapLayerInfo } from '../services/api';
import { PALETTES, legendGradient } from '../lib/colorScales';
import type { SunMode } from './EarthGlobe';
import { IconClose } from './icons';

interface Props {
  layers: MapLayerInfo[];
  activeKey: string | null; // the variable's layer, if it has one
  dataOn: boolean;
  onData: (key: string | null) => void;
  clouds: boolean;
  cloudsHidden: boolean;
  onClouds: (v: boolean) => void;
  sunMode: SunMode;
  onSunMode: (m: SunMode) => void;
  grid: boolean;
  onGrid: (v: boolean) => void;
  onClose: () => void;
}

export const LayerMenu = (p: Props) => {
  const available = p.layers.filter((l) => PALETTES[l.key]);
  const selected = p.dataOn ? p.activeKey : null;
  return (
    <section className="glass layer-menu" aria-label="Map layers">
      <header className="panel-head">
        <div className="eyebrow">Layers</div>
        <button className="icon-btn subtle" onClick={p.onClose} aria-label="Close layers"><IconClose /></button>
      </header>

      <div className="lm-group" role="radiogroup" aria-label="Data layer">
        <div className="lm-title">NASA data layer</div>
        <label className={`lm-option ${selected === null ? 'on' : ''}`}>
          <input type="radio" name="data-layer" checked={selected === null} onChange={() => p.onData(null)} />
          <span className="lm-swatch none" />
          <span>None (Earth only)</span>
        </label>
        {available.map((l) => {
          const pal = PALETTES[l.key];
          return (
            <label key={l.key} className={`lm-option ${selected === l.key ? 'on' : ''}`} data-tip={`${l.name}, ${l.units}. ${l.source}. ${l.resolution_label}.`}>
              <input type="radio" name="data-layer" checked={selected === l.key} onChange={() => p.onData(l.key)} />
              <span className="lm-swatch" style={{ background: legendGradient(pal) }} />
              <span>{pal.short}</span>
              <span className="lm-unit">{pal.units}</span>
            </label>
          );
        })}
      </div>

      <div className="lm-group">
        <div className="lm-title">Base map</div>
        <label className="lm-toggle" data-tip="A representative NASA-based cloud image that drifts slowly. It is not today's weather.">
          <input type="checkbox" checked={p.clouds} onChange={(e) => p.onClouds(e.target.checked)} />
          <span>Clouds</span>
          {p.cloudsHidden && p.clouds && <em>hidden while a data layer is on</em>}
        </label>
        <label className="lm-toggle">
          <input type="checkbox" checked={p.grid} onChange={(e) => p.onGrid(e.target.checked)} />
          <span>Latitude / longitude lines</span>
        </label>
      </div>

      <div className="lm-group" role="radiogroup" aria-label="Sunlight">
        <div className="lm-title">Sunlight</div>
        <div className="seg">
          <button className={p.sunMode === 'camera' ? 'on' : ''} onClick={() => p.onSunMode('camera')}
            data-tip="The side you are looking at is always in daylight.">Follow view</button>
          <button className={p.sunMode === 'real' ? 'on' : ''} onClick={() => p.onSunMode('real')}
            data-tip="Day and night as they are right now (UTC), with city lights on the night side.">Real time</button>
        </div>
      </div>
    </section>
  );
};
