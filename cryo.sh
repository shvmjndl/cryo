#!/bin/bash

set -euo pipefail

CMD="${1:-up}"
PROJECT_NAME="${COMPOSE_PROJECT_NAME:-$(basename "$PWD")}"
NETWORK_NAME="${PROJECT_NAME}_default"
API_CONTAINER="${PROJECT_NAME}-api-1"

get_services() {
  docker compose config --services 2>/dev/null
}

container_exists() {
  docker container inspect "$1" >/dev/null 2>&1
}

cleanup_stale_containers() {
  local service
  local container

  while IFS= read -r service; do
    [ -n "$service" ] || continue
    container="${PROJECT_NAME}-${service}-1"
    if container_exists "$container"; then
      docker rm -f "$container" >/dev/null
    fi
  done < <(get_services)
}

repair_default_network() {
  local compose_label

  if ! docker network inspect "$NETWORK_NAME" >/dev/null 2>&1; then
    return
  fi

  compose_label="$(docker network inspect --format '{{index .Labels "com.docker.compose.network"}}' "$NETWORK_NAME" 2>/dev/null || true)"
  if [ "$compose_label" != "default" ]; then
    docker network rm "$NETWORK_NAME" >/dev/null 2>&1 || true
  fi
}

compose_down() {
  docker compose down --remove-orphans >/dev/null 2>&1 || true
  cleanup_stale_containers
  repair_default_network
}

case "$CMD" in
  logs)
    docker logs "$API_CONTAINER" -f
    ;;
  down)
    compose_down
    ;;
  up|"")
    compose_down
    docker compose build
    docker compose up -d
    docker logs "$API_CONTAINER" -f
    ;;
  *)
    echo "Usage: bash cryo.sh [up|down|logs]"
    exit 1
    ;;
esac
