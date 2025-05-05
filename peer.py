import os
import sys
import time
import threading
import socket
from concurrent.futures import ThreadPoolExecutor
from config import TRACKER_HOST, TRACKER_PORT, ORIGINAL_MUSIC_DIR, CC_ALGO
import ssl

# Monkey-patch socket.socket to set TCP congestion control
_orig_socket = socket.socket
def _socket_with_cc(family=socket.AF_INET, type=socket.SOCK_STREAM, proto=0, fileno=None):
    s = _orig_socket(family, type, proto, fileno)
    try:
        # choose 'reno', 'cubic', 'bbr', etc.
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_CONGESTION, CC_ALGO)
    except Exception:
        pass  # if the kernel inside the Docker VM doesn't support it, ignore
    return s
socket.socket = _socket_with_cc

import Pyro4
from chunk_utils import combine_file, tracker_call

# Pyro4 conf
Pyro4.config.SERIALIZER = "pickle"
Pyro4.config.SERIALIZERS_ACCEPTED.add("pickle")
Pyro4.config.COMMTIMEOUT = 10

# Determine this peer’s ID
env_id = os.environ.get("PEER_ID")
if not env_id:
    print("PEER_ID environment variable is required!")
    sys.exit(1)
PEER_NUM = env_id
print(f"[PEER {PEER_NUM}] starting up…")

# Paths & constants
MUSIC_DIR = os.path.join("peers", f"peer{PEER_NUM}", "music")
HEARTBEAT_INTERVAL = 10
MAX_WORKERS = 100

# Your container’s hostname for Pyro NAT advertising
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
        fname for fname in os.listdir(MUSIC_DIR)
        if os.path.isfile(os.path.join(MUSIC_DIR, fname)) and ".part" in fname
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


def parallel_download(tracker, my_uri, parts):
    with ThreadPoolExecutor(MAX_WORKERS) as pool:
        futures = [
            pool.submit(download_chunk, tracker, my_uri, c, os.path.join(MUSIC_DIR, c))
            for c in parts
        ]
    return [f.result() for f in futures]


def handle_get_command(tracker, my_uri, filename):
    """Invoke the same logic as interactive 'get', then exit."""
    # 1) Resolve & download missing parts
    start = time.time()
    print(f"[PEER {PEER_NUM}] (CLI) Resolving '{filename}'...")
    all_chunks = tracker_call(
        tracker.getChunksForFile,
        filename,
        description="Get chunk list"
    )
    if not all_chunks:
        print(f"[{my_uri}] No chunks found or tracker down.")
        return False

    existing = set(discover_chunks())
    missing = [c for c in all_chunks if c not in existing]
    if missing:
        print(f"[PEER {PEER_NUM}] Downloading missing parts: {missing}")
        results = parallel_download(tracker, my_uri, missing)
        if not all(results):
            print(f"[{my_uri}] Download failures; aborting.")
            return False
    else:
        print(f"[PEER {PEER_NUM}] All parts present; skipping download.")

    # 2) Combine all known parts into the final file
    paths = [os.path.join(MUSIC_DIR, c) for c in all_chunks]
    output_path = os.path.join(MUSIC_DIR, filename)
    combine_file(paths, output_path)
    print(f"[PEER {PEER_NUM}] Reassembled → {filename}")
    end = time.time()
    dur = f"{end-start:.3f}"
    print(f"[PEER {PEER_NUM}] Time = {dur}")

    # 3) Size‐validation against the original master file
    orig = os.path.join(ORIGINAL_MUSIC_DIR, filename)
    if os.path.isfile(orig):
        got = os.path.getsize(output_path)
        want = os.path.getsize(orig)
        if got != want:
            print(f"[PEER {PEER_NUM}] Size mismatch: got {got} bytes, expected {want} bytes")
            return False
        else:
            print(f"[PEER {PEER_NUM}] Size check: {got} bytes (matches original)")
    else:
        print(f"[PEER {PEER_NUM}] Warning: original not found at {orig} — skipping size check")

    return True




def main():
    # 1) Ensure the local folder exists
    os.makedirs(MUSIC_DIR, exist_ok=True)

    # 2) Start Pyro daemon
    daemon = Pyro4.Daemon(host="0.0.0.0", nathost=HOSTNAME)
    server = PeerServer(MUSIC_DIR)
    my_uri = daemon.register(server)
    print(f"[PEER {PEER_NUM}] serving → {my_uri}")
    threading.Thread(target=daemon.requestLoop, daemon=True).start()

    # 3) Connect to tracker & register initial chunks
    tracker = Pyro4.Proxy(f"PYRO:obj_tracker@{TRACKER_HOST}:{TRACKER_PORT}")
    initial = discover_chunks()
    tracker.register_chunks(my_uri, initial)
    print(f"[PEER {PEER_NUM}] registered {len(initial)} parts")

    # 4) Start heartbeat
    threading.Thread(target=run_heartbeat, args=(tracker, my_uri), daemon=True).start()

    # 5) If called as CLI: python peer.py get <file>
    if len(sys.argv) >= 3 and sys.argv[1] == "get":
        success = handle_get_command(tracker, my_uri, sys.argv[2])
        sys.exit(0 if success else 1)

    # 6) Otherwise interactive loop
    while True:
        try:
            cmd = input("> ").strip()
        except EOFError:
            # keep the container alive when detached
            time.sleep(1)
            continue

        if cmd.startswith("get "):
            _, filename = cmd.split(" ", 1)
            handle_get_command(tracker, my_uri, filename)
        elif cmd == "files":
            print("Local parts:", discover_chunks())
        elif cmd == "exit":
            break


if __name__ == "__main__":
    main()
