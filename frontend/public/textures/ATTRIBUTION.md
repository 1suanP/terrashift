# Earth texture sources and licences

| File | Content | Source | Licence |
|---|---|---|---|
| `earth-day-4k.jpg`, `earth-day-2k.jpg` | True-colour surface | NASA Blue Marble, as distributed in the `three-globe` package examples (`earth-blue-marble.jpg`, kept here as the build source) | NASA imagery: public domain. Credit: NASA |
| `earth-night-4k.jpg`, `earth-night-2k.jpg` | City lights | [Solar System Scope](https://www.solarsystemscope.com/textures/) `8k_earth_nightmap.jpg`, based on NASA Black Marble | CC BY 4.0, credit "Solar System Scope" |
| `earth-clouds-4k.jpg`, `earth-clouds-2k.jpg` | Cloud opacity | Solar System Scope `8k_earth_clouds.jpg`, based on NASA imagery | CC BY 4.0, credit "Solar System Scope" |
| `earth-surface-2k.png` | R,G = terrain normal map (DirectX convention), B = ocean mask | Solar System Scope `2k_earth_normal_map.tif` and `2k_earth_specular_map.tif` | CC BY 4.0, credit "Solar System Scope" |

The clouds are a single representative image. They are decorative, **not** current or
historical weather, and the app hides them whenever a NASA data layer is shown.

Changes made (allowed under CC BY 4.0): resized; night map base darkened so only light
sources remain; faint cloud haze removed; normal map and ocean mask packed into one PNG.
Rebuild with `python scripts/build-textures.py <folder with the source downloads>`.

All environmental data layers are separate and come from NASA GES DISC (GPM IMERG,
MERRA-2) through the backend `/api/maps` endpoints.
