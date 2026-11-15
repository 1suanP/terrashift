# TerraShift backend (FastAPI + NASA data pipeline) as a container.
# Optional: for container hosts (Google Cloud Run, Render, Fly.io, a VPS...).
# The free deployment uses Vercel instead (see README, "Deploy").
# The website (frontend/) is deployed separately, e.g. on Vercel.
#
# Required secrets at run time (never bake them into the image):
#   EARTHDATA_USERNAME, EARTHDATA_PASSWORD   - NASA Earthdata Login
# Optional:
#   ALLOWED_ORIGINS  - comma-separated websites allowed to call the API (CORS)
#   PORT             - listening port (default 7860)

FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Run as an unprivileged user.
RUN useradd --create-home --uid 1000 user

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY --chown=user config.py ./
COPY --chown=user modules ./modules
COPY --chown=user backend ./backend
RUN mkdir -p /app/backend/cache && chown -R user:user /app/backend/cache

USER user
ENV HOME=/home/user \
    PORT=7860 \
    ALLOWED_ORIGINS=https://terrashift-ptsw.vercel.app

WORKDIR /app/backend
EXPOSE 7860
CMD ["sh", "-c", "exec uvicorn api.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
