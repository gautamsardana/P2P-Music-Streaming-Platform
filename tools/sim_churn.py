#!/usr/bin/env python3
import time, random, argparse, csv, subprocess, sys
from concurrent.futures import ThreadPoolExecutor

print("[CHURN] sim_churn.py loaded")

def stop_peer(peer_id):
    subprocess.run(["docker", "stop", f"peer{peer_id}"], stdout=subprocess.DEVNULL)
    print(f"[CHURN] Stopped peer{peer_id}")

def start_peer(peer_id):
    subprocess.run(["docker", "start", f"peer{peer_id}"], stdout=subprocess.DEVNULL)
    print(f"[CHURN] Started peer{peer_id}")

def main():
    p = argparse.ArgumentParser(description="Simulate churn at a fixed rate")
    p.add_argument("-n","--peers",  type=int,   required=True)
    p.add_argument("-r","--rate",   type=float, required=True)
    p.add_argument("-d","--duration", type=float, default=60.0)
    p.add_argument("-o","--output", default="churn_events.csv")
    args = p.parse_args()

    print(f"[CHURN] starting with args: peers={args.peers}, rate={args.rate}, duration={args.duration}")

    interval = 1.0 / args.rate

    # Open the CSV file once and keep handle
    csvfile = open(args.output, "w", newline="")
    writer = csv.writer(csvfile)
    writer.writerow(["timestamp_s","peer_id","action","active_count"])
    csvfile.flush()

    all_peers = list(range(1, args.peers+1))
    active = set(all_peers)
    pool = ThreadPoolExecutor(max_workers=10)

    start_time = time.time()
    next_event = start_time + interval
    end_time = start_time + args.duration

    while time.time() < end_time:
        now = time.time()
        if now >= next_event:
            # schedule non-blocking churn
            if active and (len(active) == args.peers or random.random() < 0.5):
                pid = random.choice(list(active))
                pool.submit(stop_peer, pid)
                action = "leave"
                active.remove(pid)
            else:
                pid = random.choice([p for p in all_peers if p not in active])
                pool.submit(start_peer, pid)
                action = "join"
                active.add(pid)

            ts = round(now - start_time, 3)
            writer.writerow([ts, pid, action, len(active)])
            csvfile.flush()
            next_event += interval
        else:
            time.sleep(min(0.01, next_event - now))

    pool.shutdown(wait=True)
    csvfile.close()
    print("[CHURN] Done. Events logged to", args.output)

if __name__ == "__main__":
    main()
