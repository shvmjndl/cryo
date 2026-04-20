#!/bin/bash

CMD=$1

case "$CMD" in
  logs)
    docker logs cryo-api-1 -f
    ;;
  down)
    docker compose down
    ;;
  up|"")
    docker compose down && docker compose up -d && docker logs cryo-api-1 -f
    ;;
  *)
    echo "Usage: bash run.sh [up|down|logs]"
    ;;
esac