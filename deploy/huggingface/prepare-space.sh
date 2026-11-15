#!/bin/sh
# Build a folder containing exactly what the Hugging Face Space needs (backend only),
# ready to push. Usage, from the repository root:
#
#   sh deploy/huggingface/prepare-space.sh [target-folder]      (default: ../terrashift-space)
#
# The Space gets its own README (with the Space settings) so the GitHub README stays clean.
set -eu
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
DST=${1:-"$ROOT/../terrashift-space"}

mkdir -p "$DST"
# Refresh the copied files but keep the Space's own .git history.
rm -rf "$DST/backend" "$DST/modules"
cp "$ROOT/Dockerfile" "$ROOT/.dockerignore" "$ROOT/requirements.txt" "$ROOT/config.py" "$DST/"
cp "$ROOT/deploy/huggingface/README.md" "$DST/README.md"
cp -R "$ROOT/modules" "$DST/modules"
mkdir -p "$DST/backend"
cp -R "$ROOT/backend/api" "$DST/backend/api"
find "$DST" -name "__pycache__" -prune -exec rm -rf {} +
rm -f "$DST/backend/.env"

printf '.env\n__pycache__/\n*.pyc\nbackend/cache/\n' > "$DST/.gitignore"
echo "Space files ready in $DST"
