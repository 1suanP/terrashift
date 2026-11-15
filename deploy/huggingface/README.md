---
title: TerraShift API
emoji: 🌍
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
short_description: NASA Earth-change data API for the TerraShift website
---

# TerraShift API

The data service behind [TerraShift](https://github.com/1suanP/terrashift):
*Every shift tells a story.*

It searches NASA Earthdata (GPM IMERG, MERRA-2), downloads only the requested region and
months over OPeNDAP, and runs the trend tests. The website itself is hosted separately.

- Health check: `/api/health`
- Interactive API docs: `/api/docs`

Space secrets required: `EARTHDATA_USERNAME`, `EARTHDATA_PASSWORD`.
Optional variable: `ALLOWED_ORIGINS` (websites allowed to call the API).
