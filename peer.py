import os
import sys
import time
import threading
import socket
from concurrent.futures import ThreadPoolExecutor

import Pyro4
from config import TRACKER_HOST, TRACKER_PORT
from chunk_utils import combine_file, tracker_call

# ── Pyro4 configuration ────────────────────────────────────────────────────────
Pyro4.config.SERIALIZER = "pickle"
Pyro4.config.SERIALIZERS_ACCEPTED.add("pickle")
Pyro4.config.COMMTIMEOUT = 2

# ── Determine this peer’s ID ────────────────────────────────────────────────────
env_id = os.environ.get("PEER_ID")
if not env_id:
    print("⛔️  PEER_ID environment variable is required!")
    sys.exit(1)
PEER_NUM = env_id
print(f"[PEER {PEER_NUM}] starting up…")

# ── Paths & constants ──────────────────────────────────────────────────────────
MUSIC_DIR = os.path.join("peers", f"peer{PEER_NUM}", "music")
HEARTBEAT_INTERVAL = 10
MAX_WORKERS = 6

# ── Your container’s hostname for Pyro NAT advertising ─────────────────────────
HOSTNAME = socket.gethostname()


@Pyro4.expose
class PeerServer:
    def __init__(self, base_dir):
        self.base_dir = base_dir

    def get_chunk(self, chunk_name):
        path = os.path.join(self.base_dir, chunk_name)
        print(f"[PEER {PEER_NUM}] Request for chunk '{chunk_name}' → {path}")
        if not os.path.isfile(path):
            print(f"[PEER {PEER_NUM}] Chunk not found: {chunk_name}")
            raise FileNotFoundError(chunk_name)
        with open(path, "rb") as f:
            return f.read()


def discover_chunks():
    return [
        f for f in os.listdir(MUSIC_DIR)
        if os.path.isfile(os.path.join(MUSIC_DIR, f)) and ".part" in f
    ]


def run_heartbeat(tracker, my_uri):
    while True:
        try:
            tracker.heartbeat(my_uri)
        except Exception:
            pass
        time.sleep(HEARTBEAT_INTERVAL)


def download_chunk(tracker, my_uri, chunk_name, dest_path):
    try:
        peers = tracker.peersForChunk(chunk_name)
    except Exception as e:
        print(f"[{my_uri}] Tracker query failed for chunk {chunk_name}: {e}")
        return False

    # don't fetch from yourself
    peers = [p for p in peers if p != my_uri]
    if not peers:
        print(f"[{my_uri}] No peers found for chunk '{chunk_name}'")
        return False

    for peer_uri in peers:
        try:
            peer = Pyro4.Proxy(peer_uri)
            data = peer.get_chunk(chunk_name)
            if isinstance(data, bytes):
                with open(dest_path, "wb") as f:
                    f.write(data)
                tracker.updateChunkList(my_uri, chunk_name)
                print(f"[{my_uri}] Downloaded chunk '{chunk_name}' from {peer_uri}")
                return True
        except Exception as e:
            print(f"[{my_uri}] Failed to get '{chunk_name}' from {peer_uri}: {e}")

    print(f"[{my_uri}] All attempts failed for chunk '{chunk_name}'")
    return False


def parallel_download(tracker, my_uri, chunk_list):
    futures = []
    with ThreadPoolExecutor(MAX_WORKERS) as pool:
        for chunk in chunk_list:
            dest = os.path.join(MUSIC_DIR, chunk)
            futures.append(pool.submit(download_chunk, tracker, my_uri, chunk, dest))
    return [f.result() for f in futures]


def main():
    os.makedirs(MUSIC_DIR, exist_ok=True)

    # start Pyro daemon, listening on all interfaces, advertise container name
    daemon = Pyro4.Daemon(host="0.0.0.0", nathost=HOSTNAME)
    me = PeerServer(MUSIC_DIR)
    my_uri = daemon.register(me)
    print(f"[PEER {PEER_NUM}] serving chunks at {my_uri}")

    threading.Thread(target=daemon.requestLoop, daemon=True).start()

    # connect to tracker
    tracker = Pyro4.Proxy(f"PYRO:obj_tracker@{TRACKER_HOST}:{TRACKER_PORT}")

    # initial chunk registration
    chunks = discover_chunks()
    tracker.register_chunks(my_uri, chunks)
    print(f"[PEER {PEER_NUM}] online → {my_uri}  sharing chunks: {chunks}")

    # heartbeat thread
    threading.Thread(target=run_heartbeat, args=(tracker, my_uri), daemon=True).start()

    # interactive CLI
    while True:
        try:
            cmd = input("> ").strip()
        except EOFError:
            # keep the container alive when detached
            time.sleep(1)
            continue

        if cmd.startswith("get "):
            filename = cmd.split(" ", 1)[1]
            print(f"[PEER {PEER_NUM}] Resolving chunks for '{filename}'...")

            all_chunks = tracker_call(
                tracker.getChunksForFile,
                filename,
                description="Fetching chunks for file"
            )
            if not all_chunks:
                print(f"[{my_uri}] No chunks found or tracker not responding.")
                continue

            existing = set(discover_chunks())
            missing = [c for c in all_chunks if c not in existing]

            if missing:
                print(f"[PEER {PEER_NUM}] Downloading {len(missing)} missing parts: {missing}")
                results = parallel_download(tracker, my_uri, missing)
                if not all(results):
                    print(f"[{my_uri}] Some chunks failed to download. File incomplete.")
                    continue
            else:
                print(f"[PEER {PEER_NUM}] All {len(all_chunks)} parts present locally; skipping download.")

            # reassemble from *all* parts once they’re on disk
            paths = [os.path.join(MUSIC_DIR, part) for part in all_chunks]
            combine_file(paths, os.path.join(MUSIC_DIR, filename))
            print(f"[PEER {PEER_NUM}] File reassembled → {filename}")

        elif cmd == "files":
            print("Local:", discover_chunks())
        elif cmd == "exit":
            break


if __name__ == "__main__":
    main()
