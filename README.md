<p align="center">
  <img src="frontend/public/favicon.svg" width="72" alt="TerraShift logo" />
</p>

<h1 align="center">TerraShift</h1>
<p align="center"><em>Every shift tells a story.</em></p>

TerraShift is an interactive platform for exploring and understanding Earth's environmental
changes through NASA data. It was built for the 2026 NASA Space Apps Challenge
*Earth System Trend Detective*.

Earth is always changing: rainfall moves, soils dry out, regions warm. The data that records
these shifts is public, but it is hard to reach and harder to interpret. TerraShift makes it
approachable. Search for or click any place on a realistic 3D globe, choose a variable such as
precipitation, temperature, soil moisture or evaporation, and TerraShift downloads that place's
monthly NASA record, tests it for a statistically significant trend, and explains the result in
plain language.

## Features

- **Realistic 3D Earth** (React + Three.js): NASA Blue Marble surface, day/night lighting with
  city lights, terrain relief, ocean sun glint, drifting clouds, thin atmosphere, 23.4° tilt.
- **NASA data layers on the globe**: monthly maps of precipitation (GPM IMERG), temperature,
  soil moisture and evaporation (MERRA-2), with a time slider, animation and legends.
- **Location search**: cities, countries, states, regions and typed coordinates, with
  autocomplete, keyboard navigation and session history.
- **Click or draw a region**: point selection or a latitude/longitude box.
- **Coverage check**: before offering an analysis, TerraShift checks the dataset's real grid
  (for example, land-only variables have no data over the ocean).
- **Trend analysis**: linear regression with 95% confidence interval, Mann-Kendall test,
  Sen's slope, optional seasonal-cycle removal, and a plain-language interpretation.
- **Modes**: Explore, Discover (catalogue of 26 variables and trend questions), Guided
  (step-by-step), Expert (full control) and Demo (ready-made investigations).

Nothing is simulated in TerraShift: every map, value and trend comes from NASA data retrieved at run time.

## Architecture

```
frontend/  React 19 + TypeScript + Vite + Three.js   (http://localhost:5173)
backend/   FastAPI REST API                           (http://localhost:8000, docs at /api/docs)
modules/   Python data pipeline and statistics (shared by the API)
config.py  Datasets, variables, regions and demo presets (single source of truth)
tests/     pytest suite for the pipeline, statistics and API
```

Data flow: NASA CMR search (`earthaccess`) → OPeNDAP subset (only the selected variable,
region and months) → regional monthly mean → unit conversion → trend tests.

## Data sources

| Dataset | Short name | Used for |
|---|---|---|
| GPM IMERG Monthly V07 | `GPM_3IMERGM` | precipitation (2000 to present) |
| MERRA-2 single-level | `M2TMNXSLV` | air and surface temperature, humidity, pressure, wind, water vapour |
| MERRA-2 land surface | `M2TMNXLND` | soil moisture, land evaporation, runoff, leaf area, land precipitation |
| MERRA-2 surface flux | `M2TMNXFLX` | evaporation, wind speed |
| MERRA-2 aerosol | `M2TMNXAER` | aerosol and dust optical depth |
| MERRA-2 ocean surface | `M2TMNXOCN` | open-water skin temperature |

All are served by NASA GES DISC and require a free [Earthdata Login](https://urs.earthdata.nasa.gov/users/new).
After creating the account, approve the **NASA GESDISC DATA ARCHIVE** application in your
Earthdata profile (Applications → Authorized Apps), otherwise downloads fail with HTTP 403.

## Requirements

- Python 3.11 or newer (developed and tested with 3.14)
- Node.js 20 or newer (developed with Node 26) and npm
- A NASA Earthdata Login account

## Setup

```bash
# 1. Backend
python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example backend/.env         # then put your Earthdata username and password in backend/.env

# 2. Frontend
cd frontend
npm ci
cd ..
```

## Run

Open two terminals from the project root.

```bash
# Terminal 1 - API on http://localhost:8000
source .venv/bin/activate
cd backend
uvicorn api.main:app --port 8000
```

```bash
# Terminal 2 - website on http://localhost:5173
cd frontend
npm run dev
```

Then open http://localhost:5173.

To serve an optimized build instead of the dev server: `cd frontend && npm run build && npm run preview -- --port 5173`.

If the API runs somewhere other than `http://localhost:8000`, create `frontend/.env.local`
with `VITE_API_URL=https://your-api-host` before building. Allowed browser origins are set in
`backend/api/main.py` (CORS).

## What to expect

- The first view of a globe data layer downloads each month from NASA (about 10 s per month).
  Maps are cached in `backend/cache/`, so later views are instant.
- A trend analysis downloads one file per month: roughly 80 s for 10 years of MERRA-2 data and
  about 3.5 minutes for 10 years of GPM precipitation. Shorter periods are faster.
- Monthly data, not real-time weather. NASA publishes GPM monthly data a few months late.

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest                     # all tests mock NASA and the geocoders; no network needed
cd frontend && node scripts/check-geo.ts && node scripts/check-coordinates.ts
```

## Statistics

- **Linear regression** (`scipy.stats.linregress`): change per year, 95% confidence interval, p-value.
- **Mann-Kendall test** (`pymannkendall`): monotonic trend without assuming a straight line or normal data.
- **Sen's slope**: median of pairwise slopes, robust to outliers.
- **Seasonal-cycle removal** (default on): each month minus that calendar month's average.
- A trend is called **statistically significant** only when the regression p-value is below
  0.05 **and** Mann-Kendall agrees on the direction. A result describes the selected place and
  period only.

## Credits and licences

- NASA data: GPM IMERG and MERRA-2 from NASA GES DISC.
- Earth surface imagery: NASA Blue Marble (public domain).
- City lights, clouds, terrain normal map and ocean mask: [Solar System Scope](https://www.solarsystemscope.com/textures/),
  CC BY 4.0, based on NASA imagery. Details in `frontend/public/textures/ATTRIBUTION.md`.
  The clouds are a representative image, not current weather.
- Place search: [Photon](https://photon.komoot.io) by komoot. Reverse geocoding: [Nominatim](https://nominatim.org).
  Both use data © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright) (ODbL).
  TerraShift uses the public servers within their usage policies (debounced, cached, rate-limited
  through the backend). Deployments with more traffic should run their own instance.

NASA does not endorse any non-U.S. Government entity and is not responsible for information
contained on non-U.S. Government websites.
