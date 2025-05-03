#!/usr/bin/env python3
"""
Peer node.
Usage:  python peer.py <peer_number>
"""
import os
import sys
import time
import threading
from concurrent.futures import ThreadPoolExecutor

import Pyro4
from config import TRACKER_HOST, TRACKER_PORT

Pyro4.config.SERIALIZER = "pickle"
Pyro4.config.SERIALIZERS_ACCEPTED.add("pickle")
Pyro4.config.COMMTIMEOUT = 2


PEER_NUM = sys.argv[1]
MUSIC_DIR = os.path.join("peers", f"peer{PEER_NUM}", "music")
HEARTBEAT_INTERVAL = 10  # seconds
MAX_WORKERS = 4  # simultaneous uploads


@Pyro4.expose
class PeerServer(object):
    def __init__(self, base_dir):
        self.base_dir = base_dir

    def music(self, filename):
        path = os.path.join(self.base_dir, filename)
        print(f"[PEER] Received request for file '{filename}' → {path}")
        if not os.path.isfile(path):
            print(f"[PEER] File '{filename}' not found")
            raise FileNotFoundError(filename)
        with open(path, "rb") as f:
            content = f.read()
            if not isinstance(content, bytes):
                raise TypeError(f"[PEER] INTERNAL ERROR: returning non-bytes type {type(content)}")
            print(f"[PEER] Returning file: {filename}, size: {len(content)} bytes")
            return content


def discover_files():
    return [f for f in os.listdir(MUSIC_DIR) if os.path.isfile(os.path.join(MUSIC_DIR, f))]


def run_heartbeat(tracker, my_uri):
    while True:
        try:
            tracker.heartbeat(my_uri)
        except Exception:
            pass
        time.sleep(HEARTBEAT_INTERVAL)


def get_peers_for_file(tracker, filename):
    for attempt in range(3):
        print(f"[PEER] Download Attempt {attempt}...")
        try:
            return tracker.peersForFile(filename)
        except Exception as e:
            print(f"[WARN] Tracker query failed (attempt {attempt + 1}): {e}")
            time.sleep(1)
    return []


def download(tracker, my_uri, filename):
    print(f"[{my_uri}] Trying to download '{filename}'")

    try:
        peers = get_peers_for_file(tracker, filename)
    except Exception as e:
        print(f"[{my_uri}] Tracker query failed: {e}")
        return

    peers = [p for p in peers if p != my_uri]
    if not peers:
        print(f"[{my_uri}] No peers found for file '{filename}'")
        return

    for peer_uri in peers:
        try:
            peer = Pyro4.Proxy(peer_uri)
            data = peer.music(filename)
            print(f"[{my_uri}] Peer {peer_uri} returned type: {type(data)}")

            if not isinstance(data, bytes):
                print(f"[{my_uri}] Error: peer {peer_uri} returned non-bytes object")
                continue  # try next peer

            path = os.path.join(MUSIC_DIR, filename)
            with open(path, "wb") as f:
                f.write(data)

            tracker.updateFileList(my_uri, filename)
            print(f"[{my_uri}] Successfully downloaded '{filename}' from {peer_uri}")
            return

        except Exception as e:
            print(f"[{my_uri}] Failed to download from {peer_uri}: {e}")

    print(f"[{my_uri}] Download failed")

    path = os.path.join(MUSIC_DIR, filename)
    if os.path.exists(path) and os.path.getsize(path) == 0:
        print(f"[{my_uri}] Removing empty file '{filename}'")
        os.remove(path)


def main():
    os.makedirs(MUSIC_DIR, exist_ok=True)

    if len(sys.argv) < 2:
        print("Usage: peer.py <peer_number>")
        sys.exit(1)
    peer_number = sys.argv[1]

    # ---------- Pyro init ----------
    daemon = Pyro4.Daemon()
    me = PeerServer(MUSIC_DIR)
    my_uri = daemon.register(me)  # uri string
    threading.Thread(target=daemon.requestLoop, daemon=True).start()

    tracker = Pyro4.Proxy(f"PYRO:obj_tracker@{TRACKER_HOST}:{TRACKER_PORT}")

    # ---------- initial registration ----------
    files = discover_files()
    tracker.register(my_uri, files)
    print(f"[Peer {peer_number}] online → {my_uri}  sharing {files}")

    # ---------- heartbeat ----------
    threading.Thread(target=run_heartbeat, args=(tracker, my_uri), daemon=True).start()

    # ---------- CLI loop ----------
    pool = ThreadPoolExecutor(MAX_WORKERS)
    while True:
        cmd = input("> ").strip()
        if cmd.startswith("get "):
            filename = cmd.split(" ", 1)[1]
            pool.submit(download, tracker, my_uri, filename)
        elif cmd == "files":
            print("Local:", discover_files())
        elif cmd == "exit":
            break


if __name__ == "__main__":
    main()
