#!/usr/bin/env python3
import os
import shutil
import random
import argparse
import sys

# allow importing your split_file helper
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from chunk_utils import split_file

def main():
    p = argparse.ArgumentParser(
        description="Partial‐Availability: randomly drop some chunks globally"
    )
    p.add_argument("-n","--peers",     type=int,   required=True,
                   help="Total number of peers (1…N)")
    p.add_argument("-r","--replication",type=int,   default=3,
                   help="Replicas per chunk when not dropped")
    p.add_argument("-m","--missing",    type=float, default=0.1,
                   help="Fraction of chunks to drop globally (0.0–1.0)")
    p.add_argument("--music-dir",       default="tools/music",
                   help="Source .mp3 directory")
    p.add_argument("--dest-dir",        default="peers",
                   help="Root of peers/peerX/music")
    args = p.parse_args()

    # 1) wipe out any existing peer music dirs
    for i in range(1, args.peers+1):
        d = os.path.join(args.dest_dir, f"peer{i}", "music")
        if os.path.isdir(d):
            shutil.rmtree(d)

    # 2) temp workspace
    tmp = os.path.join("tools", "_partial")
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp)

    # 3) process each .mp3
    for fname in os.listdir(args.music_dir):
        if not fname.lower().endswith(".mp3"):
            continue
        src = os.path.join(args.music_dir, fname)
        print(f"\nSplitting {fname} …")
        parts = split_file(src, tmp)
        print(f" → {len(parts)} parts generated")

        for part in parts:
            # drop globally with probability missing
            if random.random() < args.missing:
                print(f"  • DROPPED {os.path.basename(part)} (globally missing)")
                continue
            # otherwise replicate to r peers
            targets = random.sample(range(1, args.peers+1),
                                    k=min(args.replication, args.peers))
            for peer in targets:
                dest_dir = os.path.join(args.dest_dir, f"peer{peer}", "music")
                os.makedirs(dest_dir, exist_ok=True)
                shutil.copy(part, os.path.join(dest_dir, os.path.basename(part)))
                print(f"  → {os.path.basename(part)} → peer{peer}")

        # clean up this file’s parts
        for part in parts:
            os.remove(part)

    # 4) cleanup temp
    shutil.rmtree(tmp)
    print("\nDone. Partial‐availability distribution complete.")

if __name__ == "__main__":
    main()
