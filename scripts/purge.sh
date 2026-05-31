#!/usr/bin/env bash
# purge.sh — Reset CRYO to a clean state.
#
# Usage:
#   ./scripts/purge.sh            # Reset DB + user data (keeps models/ccle/gdsc)
#   ./scripts/purge.sh --full     # Reset everything including downloaded datasets

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DATA="$ROOT/cryo-data"

FULL=false
for arg in "$@"; do
  [[ "$arg" == "--full" ]] && FULL=true
done

echo "==> Stopping containers..."
docker compose -f "$ROOT/docker-compose.yml" down 2>&1 | grep -v "^$" || true

echo "==> Dropping postgres volume..."
docker volume rm cryo_pgdata 2>/dev/null && echo "    pgdata dropped" || echo "    pgdata not found (already clean)"

echo "==> Cleaning user-generated data..."
rm -rf "$DATA/reports"/*
rm -rf "$DATA/uploads"/*
rm -rf "$DATA/collections"/*
rm -rf "$DATA/users"/*
rm -rf "$DATA/cache"/*
echo "    reports, uploads, collections, users, cache cleared"

if [[ "$FULL" == "true" ]]; then
  echo "==> --full: removing downloaded datasets and model cache..."
  rm -rf "$DATA/models"/*
  rm -rf "$DATA/ccle"/*
  rm -rf "$DATA/gdsc"/*
  echo "    models, ccle, gdsc cleared"
  echo "    NOTE: GEM models (Yeast8 ~12MB), CCLE (~308MB), GDSC (~38MB) will re-download on first use"
fi

echo ""
echo "==> Restarting services..."
docker compose -f "$ROOT/docker-compose.yml" up -d 2>&1 | grep -E "Started|Created|healthy|error" || true

echo ""
echo "Done. Fresh DB will be initialized from db/schema.sql on first postgres start."
echo "Default superuser credentials are in your .env file."
