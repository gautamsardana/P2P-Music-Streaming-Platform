#!/usr/bin/env bash
set -euo pipefail

NUM_PEERS=50

# 0) Remove any old peer containers so names won't collide
for i in $(seq 1 $NUM_PEERS); do
  docker rm -f peer$i >/dev/null 2>&1 || true
done

# 1) Tear down tracker (and any old Compose containers & network)
docker-compose down

# 2) Bring up only the tracker (this also creates the p2pnet network)
docker-compose up -d tracker

# 3) Prepare each peer's music folder on the host
for i in $(seq 1 $NUM_PEERS); do
  mkdir -p peers/peer$i/music
done

# 4) Launch each peer service with its own PEER_ID
for i in $(seq 1 $NUM_PEERS); do
  echo "Starting peer $i..."
  docker-compose run -d \
    --no-deps \
    --name peer$i \
    -e PEER_ID=$i \
    peer
done

echo "Launched $NUM_PEERS peers on network p2pnet"
