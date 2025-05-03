#!/usr/bin/env python3
"""
Central tracker: keeps   file → [peer_uri]   map
Run once:  python tracker.py
"""

import time
import threading
from collections import defaultdict
import Pyro4
from config import TRACKER_HOST, TRACKER_PORT

Pyro4.config.SERIALIZER = "pickle"
Pyro4.config.SERIALIZERS_ACCEPTED.add("pickle")

@Pyro4.expose
class Tracker:
    def __init__(self, ttl=30):
        self._lock = threading.Lock()
        self.file_map = defaultdict(set)      # {file: set(peer_uri)}
        self.last_seen = {}                   # {peer_uri: timestamp}
        self.ttl = ttl                        # peer TTL for cleanup
        print("[TRACKER] Initialized tracker with TTL =", self.ttl)
        threading.Thread(target=self._reaper, daemon=True).start()

    def register(self, peer_uri, files):
        """POST /register"""
        with self._lock:
            print(f"[TRACKER] REGISTER: {peer_uri} is sharing files: {files}")
            for f in files:
                self.file_map[f].add(peer_uri)
            self.last_seen[peer_uri] = time.time()
        return True

    def peersForFile(self, filename):
        """GET /peersForFile/<file>"""
        with self._lock:
            print("[TRACKER] Entered query---")
            peers = list(self.file_map.get(filename, []))
            print(f"[TRACKER] QUERY: Who has '{filename}'? → {peers}")
            return peers

    def updateFileList(self, peer_uri, new_file):
        """POST /update"""
        with self._lock:
            print(f"[TRACKER] UPDATE: {peer_uri} downloaded and now owns '{new_file}'")
            self.file_map[new_file].add(peer_uri)
            self.last_seen[peer_uri] = time.time()
        return True

    def heartbeat(self, peer_uri):
        """Keep-alive ping"""
        with self._lock:
            self.last_seen[peer_uri] = time.time()
        return True

    def _reaper(self):
        """Background thread to prune dead peers"""
        while True:
            time.sleep(self.ttl)
            cutoff = time.time() - self.ttl
            with self._lock:
                dead = [p for p, t in self.last_seen.items() if t < cutoff]
                for p in dead:
                    print(f"[TRACKER] REAPER: Removing inactive peer {p}")
                    del self.last_seen[p]
                    for peers in self.file_map.values():
                        peers.discard(p)

def main():
    print("[TRACKER] Starting daemon...")
    daemon = Pyro4.Daemon(host=TRACKER_HOST, port=TRACKER_PORT)
    uri = daemon.register(Tracker(), objectId="obj_tracker")
    print(f"[TRACKER] Running → {uri}")
    daemon.requestLoop()

if __name__ == "__main__":
    main()
