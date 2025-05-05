#!/usr/bin/env python3
import time
import csv
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import subprocess


def fetch(peer_id, filename):
    start = time.time()
    # build the shell command to pipe "get <filename>\n" into peer.py
    cmd = f"printf 'get {filename}\\n' | python peer.py"
    try:
        subprocess.run(
            ["docker", "exec", f"peer{peer_id}", "python", "peer.py", "get", filename],
            check=True,
            capture_output=True
        )
        success = True
    except subprocess.CalledProcessError as e:
        if not e.output:
            success = True
        else:
            out = e.output.decode(errors="ignore").strip()
            print(f"failed to fetch {filename}: exit {e.returncode}, output: {out}")
            success = False

    end = time.time()
    return peer_id, start, end, end - start, success


def main():
    p = argparse.ArgumentParser(description="Cold-Start Simulation")
    p.add_argument("--file", "-f", required=True, help="Filename to GET")
    p.add_argument("--peers", "-n", type=int, default=50, help="Number of peers")
    p.add_argument("--output", "-o", default="cold_start.csv", help="CSV path")
    args = p.parse_args()

    with open(args.output, "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["peer_id", "start", "end", "duration", "success"])

        with ThreadPoolExecutor(max_workers=args.peers) as pool:
            futures = {
                pool.submit(fetch, i, args.file): i
                for i in range(1, args.peers + 1)
            }
            for fut in as_completed(futures):
                pid, start, end, dur, ok = fut.result()
                start_s = f"{start:.3f}"
                end_s = f"{end:.3f}"
                dur_s = f"{dur:.3f}"
                writer.writerow([pid, start_s, end_s, dur_s, ok])
                print(f"Peer{pid}: {dur_s}s  success={ok}")

    print(f"\nResults written to {args.output}")


if __name__ == "__main__":
    main()
