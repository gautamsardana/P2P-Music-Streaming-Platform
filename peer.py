import os
import sys
import time
import threading
from concurrent.futures import ThreadPoolExecutor

import Pyro4
from config import TRACKER_HOST, TRACKER_PORT
from chunk_utils import combine_file
from chunk_utils import tracker_call

Pyro4.config.SERIALIZER = "pickle"
Pyro4.config.SERIALIZERS_ACCEPTED.add("pickle")
Pyro4.config.COMMTIMEOUT = 2

PEER_NUM = sys.argv[1]
MUSIC_DIR = os.path.join("peers", f"peer{PEER_NUM}", "music")
HEARTBEAT_INTERVAL = 10
MAX_WORKERS = 6


@Pyro4.expose
class PeerServer(object):
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
    return [f for f in os.listdir(MUSIC_DIR)
            if os.path.isfile(os.path.join(MUSIC_DIR, f)) and ".part" in f]


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

    peers = [p for p in peers if p != my_uri]
    if not peers:
        print(f"[{my_uri}] No peers found for chunk '{chunk_name}'")
        return False

    for peer_uri in peers:
        try:
            peer = Pyro4.Proxy(peer_uri)
            data = peer.get_chunk(chunk_name)
            if not isinstance(data, bytes):
                continue
            with open(dest_path, "wb") as f:
                f.write(data)
            tracker.updateChunkList(my_uri, chunk_name)
            print(f"[{my_uri}] Downloaded chunk '{chunk_name}' from {peer_uri}")
            return True
        except Exception as e:
            print(f"[{my_uri}] Failed to get '{chunk_name}' from {peer_uri}: {e}")

    print(f"[{my_uri}] All attempts failed for chunk '{chunk_name}'")
    return False


def parallel_download(tracker, my_uri, base_filename, total_parts):
    futures = []
    pool = ThreadPoolExecutor(MAX_WORKERS)
    downloaded_parts = []

    for chunk in total_parts:
        dest = os.path.join(MUSIC_DIR, chunk)
        downloaded_parts.append(dest)
        futures.append(pool.submit(download_chunk, tracker, my_uri, chunk, dest))

    results = [f.result() for f in futures]
    if all(results):
        combine_file(downloaded_parts, os.path.join(MUSIC_DIR, base_filename))
        print(f"[{my_uri}] All chunks downloaded and reassembled into {base_filename}")
    else:
        print(f"[{my_uri}] Some chunks failed to download. File incomplete.")


def main():
    os.makedirs(MUSIC_DIR, exist_ok=True)

    if len(sys.argv) < 2:
        print("Usage: peer.py <peer_number>")
        sys.exit(1)

    # Pyro init
    daemon = Pyro4.Daemon()
    me = PeerServer(MUSIC_DIR)
    my_uri = daemon.register(me)
    threading.Thread(target=daemon.requestLoop, daemon=True).start()

    tracker = Pyro4.Proxy(f"PYRO:obj_tracker@{TRACKER_HOST}:{TRACKER_PORT}")

    # initial chunk registration
    chunks = discover_chunks()
    tracker.register_chunks(my_uri, chunks)
    print(f"[Peer {PEER_NUM}] online → {my_uri}  sharing chunks: {chunks}")

    # heartbeat
    threading.Thread(target=run_heartbeat, args=(tracker, my_uri), daemon=True).start()

    # CLI
    while True:
        cmd = input("> ").strip()
        if cmd.startswith("get "):
            filename = cmd.split(" ", 1)[1]
            print(f"[PEER {PEER_NUM}] Resolving chunks for '{filename}'...")

            all_chunks = tracker_call(tracker.getChunksForFile, filename, description="Fetching chunks for file")
            if not all_chunks:
                print(f"[{my_uri}] No chunks found or tracker not responding.")
                continue

            my_chunks = [c for c in all_chunks if my_uri not in tracker_call(tracker.peersForChunk, c,
                                                                             description=f"Checking owners of {c}") or []]

            if not all_chunks:
                print(f"[PEER {PEER_NUM}] No chunks found for '{filename}' on tracker.")
                continue

            print(f"[PEER {PEER_NUM}] Found {len(all_chunks)} chunks: {all_chunks}")
            parallel_download(tracker, my_uri, filename, all_chunks)


        elif cmd == "files":
            print("Local:", discover_chunks())
        elif cmd == "exit":
            break


if __name__ == "__main__":
    main()
