#!/usr/bin/env python3
import os
import shutil
import argparse
import sys

# allow importing split_file
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from chunk_utils import split_file

def main():
    p = argparse.ArgumentParser(
        description="Give every music file exclusively to one seed peer"
    )
    p.add_argument("-n","--peers",  type=int,   required=True,
                   help="Total number of peers (1…N)")
    p.add_argument("-s","--seed",   type=int,   default=1,
                   help="Which peer ID is the sole seeder (1…N)")
    p.add_argument("--music-dir",   default="tools/music",
                   help="Directory containing source .mp3 files")
    p.add_argument("--dest-dir",    default="peers",
                   help="Root of peers/peerX/music directories")
    args = p.parse_args()

    # 1) Clear out all music folders for all peers
    for i in range(1, args.peers+1):
        folder = os.path.join(args.dest_dir, f"peer{i}", "music")
        if os.path.isdir(folder):
            shutil.rmtree(folder)

    # 2) Prepare temp workspace
    tmp = os.path.join("tools", "_starve_all")
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp)

    # 3) Process each mp3 under music-dir
    for fname in os.listdir(args.music_dir):
        if not fname.lower().endswith(".mp3"):
            continue
        src_mp3 = os.path.join(args.music_dir, fname)
        print(f"\nSplitting {fname} → {tmp}/")
        parts = split_file(src_mp3, tmp)
        print(f" → {len(parts)} parts")

        # copy all parts to the seed peer
        seed_dir = os.path.join(args.dest_dir, f"peer{args.seed}", "music")
        os.makedirs(seed_dir, exist_ok=True)
        for part in parts:
            shutil.copy(part, os.path.join(seed_dir, os.path.basename(part)))
            print(f"{os.path.basename(part)} → peer{args.seed}")

        # cleanup this file’s parts
        for part in parts:
            os.remove(part)

    # 4) remove temp dir
    shutil.rmtree(tmp)
    print(f"\nDone. All chunks of every MP3 are now on peer{args.seed} only.")

if __name__ == "__main__":
    main()
