/**
 * Location search with autocomplete (Photon / OpenStreetMap via the backend),
 * coordinate input, keyboard navigation, and session search history.
 */
import { useCallback, useEffect, useId, useMemo, useRef, useState } from 'react';
import type { KeyboardEvent as ReactKeyboardEvent } from 'react';
import apiService from '../services/api';
import type { SearchResult } from '../services/api';
import { parseCoordinates } from '../lib/coordinates';
import { formatLatLon } from '../lib/geo';
import { IconClose, IconPin, IconReset } from './icons';

export interface PlacePick {
  name: string;
  subtitle: string;
  kind: SearchResult['kind'] | 'coordinates';
  lat: number;
  lon: number;
  bbox: SearchResult['bbox'];
  country: string | null;
  country_code: string | null;
  state: string | null;
  attribution: string;
  key: string;
}

interface Props {
  onSelect: (p: PlacePick) => void;
  recent: PlacePick[];
  onClearRecent: () => void;
  hasSelection: boolean;
  onClearSelection: () => void;
  onResetView: () => void;
}

const DEBOUNCE_MS = 300;
const MIN_CHARS = 2;
const KIND_LABEL: Record<PlacePick['kind'], string> = {
  country: 'Country', state: 'State / province', region: 'Region', city: 'City', district: 'District', place: 'Place', coordinates: 'Coordinates',
};

/** Country flag emoji from an ISO code (falls back to a pin icon). */
const flag = (code: string | null) =>
  code && /^[A-Z]{2}$/.test(code) ? String.fromCodePoint(...[...code].map((c) => 0x1f1a5 + c.charCodeAt(0))) : null;

const toPick = (r: SearchResult, attribution: string): PlacePick => ({
  ...r,
  attribution,
  key: r.osm_id || `${r.name}|${r.lat.toFixed(3)}|${r.lon.toFixed(3)}`,
});

type Status = 'idle' | 'loading' | 'done' | 'error';

export const SearchBar = ({ onSelect, recent, onClearRecent, hasSelection, onClearSelection, onResetView }: Props) => {
  const inputRef = useRef<HTMLInputElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const listId = useId();
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const [status, setStatus] = useState<Status>('idle');
  const [results, setResults] = useState<PlacePick[]>([]);
  const [searchedFor, setSearchedFor] = useState('');
  const [active, setActive] = useState(0);
  const [error, setError] = useState('');
  const abortRef = useRef<AbortController | null>(null);
  const timerRef = useRef(0);
  const enterPending = useRef(false);
  const chooseRef = useRef<(p: PlacePick) => void>(() => {});

  const trimmed = query.trim();
  const coords = useMemo(() => parseCoordinates(trimmed), [trimmed]);
  const coordPick: PlacePick | null = coords
    ? {
        name: formatLatLon(coords),
        subtitle: coords.swapped ? 'Read as longitude, latitude' : 'Latitude, longitude',
        kind: 'coordinates', lat: coords.lat, lon: coords.lon, bbox: null,
        country: null, country_code: null, state: null, attribution: '',
        key: `coords|${coords.lat.toFixed(4)}|${coords.lon.toFixed(4)}`,
      }
    : null;

  const showRecent = trimmed.length === 0;
  const items: PlacePick[] = showRecent ? recent : coordPick ? [coordPick] : results;

  const runSearch = useCallback(async (q: string) => {
    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    setStatus('loading');
    setError('');
    try {
      const { results: found, attribution } = await apiService.searchPlaces(q, ctrl.signal);
      if (ctrl.signal.aborted) return;
      const picks = found.map((r) => toPick(r, attribution));
      setResults(picks);
      setSearchedFor(q);
      setActive(0);
      setStatus('done');
      if (enterPending.current) {
        enterPending.current = false;
        if (picks[0]) chooseRef.current(picks[0]); // latest handler, not the first render's
      }
    } catch (e: unknown) {
      if (ctrl.signal.aborted || (e as { code?: string })?.code === 'ERR_CANCELED') return;
      enterPending.current = false;
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(detail || 'Search is unavailable right now. You can still type coordinates or click the globe.');
      setStatus('error');
    }
  }, []);

  // Debounced autocomplete (skipped for coordinates, which need no lookup)
  useEffect(() => {
    window.clearTimeout(timerRef.current);
    if (coords || trimmed.length < MIN_CHARS) {
      abortRef.current?.abort();
      setStatus('idle');
      setResults([]);
      setActive(0);
      return;
    }
    timerRef.current = window.setTimeout(() => runSearch(trimmed), DEBOUNCE_MS);
    return () => window.clearTimeout(timerRef.current);
  }, [trimmed, coords, runSearch]);

  // Close when clicking elsewhere
  useEffect(() => {
    const onDown = (e: PointerEvent) => {
      if (!wrapRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('pointerdown', onDown);
    return () => document.removeEventListener('pointerdown', onDown);
  }, []);

  // "/" focuses the search box from anywhere
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      if (e.key === '/' && !target?.closest('input, textarea, select, [contenteditable]')) {
        e.preventDefault();
        inputRef.current?.focus();
        setOpen(true);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  const choose = (p: PlacePick) => {
    onSelect(p);
    setQuery(p.name);
    setOpen(false);
    inputRef.current?.blur();
  };
  useEffect(() => { chooseRef.current = choose; });

  const onKeyDown = (e: ReactKeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      setOpen(true);
      if (!items.length) return;
      setActive((i) => (e.key === 'ArrowDown' ? (i + 1) % items.length : (i - 1 + items.length) % items.length));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (items[active]) choose(items[active]);
      else if (items[0]) choose(items[0]);
      else if (!coords && trimmed.length >= MIN_CHARS) {
        // typed faster than the debounce: search now and take the first match
        enterPending.current = true;
        window.clearTimeout(timerRef.current);
        runSearch(trimmed);
      }
    } else if (e.key === 'Escape') {
      e.preventDefault();
      e.stopPropagation();
      if (open && (items.length || status !== 'idle')) setOpen(false);
      else if (query) setQuery('');
      else inputRef.current?.blur();
    }
  };

  const clear = () => {
    setQuery('');
    setResults([]);
    setStatus('idle');
    setOpen(true);
    inputRef.current?.focus();
  };

  const noResults = !showRecent && !coordPick && status === 'done' && results.length === 0 && searchedFor === trimmed;
  const showList = open && (items.length > 0 || noResults || status === 'error' || status === 'loading' || (showRecent && hasSelection));
  const activeId = items[active] ? `${listId}-opt-${active}` : undefined;

  return (
    <div className="search" ref={wrapRef}>
      <div className={`search-box ${open ? 'focused' : ''}`}>
        <svg className="search-icon" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden="true">
          <circle cx="11" cy="11" r="7" /><path d="m20 20-3.6-3.6" />
        </svg>
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => { setQuery(e.target.value); setOpen(true); setActive(0); }}
          onFocus={() => setOpen(true)}
          onKeyDown={onKeyDown}
          placeholder="Search for a city, country or location..."
          aria-label="Search for a place or coordinates"
          role="combobox"
          aria-expanded={showList}
          aria-controls={listId}
          aria-activedescendant={activeId}
          aria-autocomplete="list"
          autoComplete="off"
          spellCheck={false}
        />
        {status === 'loading' && <span className="spinner small" aria-label="Searching" />}
        {query && (
          <button className="search-clear" onClick={clear} aria-label="Clear search" data-tip="Clear search">
            <IconClose width={15} height={15} />
          </button>
        )}
        {!query && <kbd className="search-kbd" aria-hidden="true">/</kbd>}
      </div>

      {showList && (
        <div className="glass search-drop" role="presentation">
          {showRecent && recent.length > 0 && (
            <div className="search-head">
              <span>Recent searches</span>
              <button className="link-btn" onClick={onClearRecent}>Clear</button>
            </div>
          )}
          <ul id={listId} role="listbox" aria-label="Search results">
            {items.map((p, i) => {
              const f = flag(p.country_code);
              return (
                <li
                  key={`${p.key}-${i}`}
                  id={`${listId}-opt-${i}`}
                  role="option"
                  aria-selected={i === active}
                  className={`search-item ${i === active ? 'active' : ''}`}
                  onPointerEnter={() => setActive(i)}
                  onPointerDown={(e) => { e.preventDefault(); choose(p); }}
                >
                  <span className="search-item-icon">
                    {p.kind === 'coordinates' ? <IconPin width={16} height={16} /> : f ?? <IconPin width={16} height={16} />}
                  </span>
                  <span className="search-item-text">
                    <span className="search-item-name">{p.name}</span>
                    {p.subtitle && <span className="search-item-sub">{p.subtitle}</span>}
                  </span>
                  <span className="search-item-kind">{KIND_LABEL[p.kind]}</span>
                </li>
              );
            })}
          </ul>
          {status === 'loading' && !items.length && <div className="search-msg"><span className="spinner small" /> Searching…</div>}
          {noResults && (
            <div className="search-msg">
              No places found for “{trimmed}”. Check the spelling, try a country or region name, or type coordinates like <code>3.14, 101.69</code>.
            </div>
          )}
          {status === 'error' && <div className="search-msg error">{error}</div>}
          {showRecent && recent.length === 0 && (
            <div className="search-msg">Type a place name, or coordinates such as <code>3.14, 101.69</code> or <code>51°30′N 0°7′W</code>.</div>
          )}
          <div className="search-foot">
            <div className="search-actions">
              {hasSelection && <button className="link-btn" onClick={() => { onClearSelection(); setOpen(false); }}>Clear selected location</button>}
              <button className="link-btn" onClick={() => { onResetView(); setOpen(false); }}><IconReset width={13} height={13} /> Reset view</button>
            </div>
            {!showRecent && !coordPick && <span className="search-attrib">Search by Photon · © OpenStreetMap contributors</span>}
          </div>
        </div>
      )}
    </div>
  );
};
