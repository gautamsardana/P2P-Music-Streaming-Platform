#!/usr/bin/env bash
set -euo pipefail

NUM_PEERS=$1
RATE=$2    # e.g. 200kbit
BURST="32mbit"

for i in $(seq 1 $NUM_PEERS); do
  CONTAINER=peer$i
  echo "Shaping $CONTAINER to $RATE …"
  docker exec $CONTAINER sh -c "tc qdisc del dev eth0 root 2>/dev/null || true"
  docker exec $CONTAINER sh -c \
    "tc qdisc add dev eth0 root tbf rate $RATE burst $BURST latency 1ms"
done

echo "Applied $RATE egress cap with minimal latency buffer."
