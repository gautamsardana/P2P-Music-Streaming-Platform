import time
import threading
from collections import defaultdict
import socket
from config import CC_ALGO
import ssl

_orig_socket = socket.socket
def _socket_with_cc(family=socket.AF_INET, type=socket.SOCK_STREAM, proto=0, fileno=None):
    s = _orig_socket(family, type, proto, fileno)
    try:
        # choose 'reno' ot 'cubic'.
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_CONGESTION, CC_ALGO)
    except Exception:
        pass
    return s
socket.socket = _socket_with_cc

import Pyro4
from config import TRACKER_HOST, TRACKER_PORT

Pyro4.config.SERVERTYPE = "thread"            # use the thread‐pool server
Pyro4.config.THREADPOOL_SIZE = 100            # max worker threads
Pyro4.config.THREADPOOL_SIZE_MIN = 20         # minimum threads to keep alive
Pyro4.config.COMMTIMEOUT = 2                  # existing

Pyro4.config.SERIALIZER = "pickle"
Pyro4.config.SERIALIZERS_ACCEPTED.add("pickle")


@Pyro4.expose
class Tracker:
    def __init__(self, ttl=30):
        self._lock = threading.Lock()
        self.chunk_map = defaultdict(set)
        self.last_seen = {}
        self.ttl = ttl
        print("[TRACKER] Initialized tracker with TTL =", self.ttl)
        threading.Thread(target=self._reaper, daemon=True).start()

    def register_chunks(self, peer_uri, chunk_names):
        """POST /register_chunks"""
        with self._lock:
            print(f"[TRACKER] REGISTER: {peer_uri} has chunks: {chunk_names}")
            for chunk in chunk_names:
                self.chunk_map[chunk].add(peer_uri)
            self.last_seen[peer_uri] = time.time()
        return True

    def peersForChunk(self, chunk_name):
        """GET /peersForChunk/<chunk>"""
        with self._lock:
            peers = list(self.chunk_map.get(chunk_name, []))
            print(f"[TRACKER] QUERY: Who has chunk '{chunk_name}'? → {peers}")
            return peers

    def updateChunkList(self, peer_uri, new_chunk):
        """POST /update_chunk"""
        with self._lock:
            print(f"[TRACKER] UPDATE: {peer_uri} downloaded and now owns chunk '{new_chunk}'")
            self.chunk_map[new_chunk].add(peer_uri)
            self.last_seen[peer_uri] = time.time()
        return True

    def getChunksForFile(self, filename_prefix):
        """ Returns all known chunk filenames that belong to a given base file """
        with self._lock:
            chunks = [fname for fname in self.chunk_map if fname.startswith(filename_prefix.replace('.mp3', '.part'))]
            print(f"[TRACKER] Chunks for '{filename_prefix}' → {chunks}")
            return sorted(chunks)

    def heartbeat(self, peer_uri):
        """Keep-alive ping"""
        with self._lock:
            self.last_seen[peer_uri] = time.time()
        return True

    def _reaper(self):
        while True:
            time.sleep(self.ttl)
            cutoff = time.time() - self.ttl
            with self._lock:
                dead = [p for p, t in self.last_seen.items() if t < cutoff]
                for p in dead:
                    print(f"[TRACKER] REAPER: Removing inactive peer {p}")
                    del self.last_seen[p]
                    for peers in self.chunk_map.values():
                        peers.discard(p)


def main():
    print("[TRACKER] Starting daemon...")
    daemon = Pyro4.Daemon(host="0.0.0.0", port=TRACKER_PORT)
    uri = daemon.register(Tracker(), objectId="obj_tracker")
    print(f"[TRACKER] Running → {uri}")
    daemon.requestLoop()


if __name__ == "__main__":
    main()
