#!/usr/bin/env python3
import os
import shutil
import random
import argparse
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from chunk_utils import split_file


def distribute_chunks(parts, num_peers, replication, dest_root):
    os.makedirs(dest_root, exist_ok=True)
    for part in parts:
        targets = random.sample(range(1, num_peers + 1), k=min(replication, num_peers))
        for peer in targets:
            peer_dir = os.path.join(dest_root, f"peer{peer}", "music")
            os.makedirs(peer_dir, exist_ok=True)
            shutil.copy(part, os.path.join(peer_dir, os.path.basename(part)))
            print(f"{os.path.basename(part)} → peer{peer}")


def main():
    p = argparse.ArgumentParser(
        description="Split all MP3s under tools/music/ and distribute chunks"
    )
    p.add_argument("-n", "--peers", type=int, required=True,
                   help="Number of peers (peer1…peerN)")
    p.add_argument("-r", "--replication", type=int, default=1,
                   help="How many peers should receive each chunk")
    p.add_argument("--music-dir", default="tools/music",
                   help="Where your source .mp3s live")
    p.add_argument("--dest-dir", default="peers",
                   help="Root of peers/peerX/music directories")
    args = p.parse_args()

    tmp = os.path.join("tools", "_chunks")
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp)

    # split each mp3 into parts under tmp/
    for fname in os.listdir(args.music_dir):
        if not fname.lower().endswith(".mp3"):
            continue
        src = os.path.join(args.music_dir, fname)
        print(f"\nSplitting {fname} → temp parts")
        parts = split_file(src, tmp)
        print(f" → {len(parts)} parts created")

        # distribute those parts
        distribute_chunks(parts, args.peers, args.replication, args.dest_dir)

        # clean up this run’s parts
        for part in parts:
            os.remove(part)

    shutil.rmtree(tmp)
    print("\nAll done! Temporary chunks cleared.")


if __name__ == "__main__":
    main()
