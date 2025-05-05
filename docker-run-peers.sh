#!/usr/bin/env bash
set -euo pipefail

NUM_PEERS=50

# remove old peers
for i in $(seq 1 $NUM_PEERS); do
  docker rm -f peer$i >/dev/null 2>&1 || true
done

# tear down tracker & network
docker-compose down --remove-orphans

# start tracker (also creates p2pnet)
docker-compose up -d tracker

# prepare folders
for i in $(seq 1 $NUM_PEERS); do
  mkdir -p peers/peer$i/music
done

# launch peers
for i in $(seq 1 $NUM_PEERS); do
  echo "Starting peer $i..."
  docker-compose run -d \
    --no-deps \
    --name peer$i \
    -e PEER_ID=$i \
    peer
done

echo "Launched $NUM_PEERS peers on network p2pnet"
