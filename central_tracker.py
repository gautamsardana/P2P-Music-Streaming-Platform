import Pyro4

@Pyro4.expose
class Tracker:
    def __init__(self):
        # file_name -> {chunk_id: [peer1, peer2, ...]}
        self.file_registry = {}
        # peer_id -> (ip, port)
        self.peer_registry = {}

    def register_peer(self, peer_id, ip, port, chunk_map):
        print(f"Registering peer: {peer_id} @ {ip}:{port}")
        self.peer_registry[peer_id] = (ip, port)

        for file_name, chunks in chunk_map.items():
            if file_name not in self.file_registry:
                self.file_registry[file_name] = {}
            for chunk_id in chunks:
                if chunk_id not in self.file_registry[file_name]:
                    self.file_registry[file_name][chunk_id] = []
                if peer_id not in self.file_registry[file_name][chunk_id]:
                    self.file_registry[file_name][chunk_id].append(peer_id)

        return True

    def get_peers_with_chunks(self, file_name):
        if file_name in self.file_registry:
            return self.file_registry[file_name]
        return {}

    def get_peer_address(self, peer_id):
        return self.peer_registry.get(peer_id, None)


def start_tracker():
    daemon = Pyro4.Daemon()
    uri = daemon.register(Tracker)
    print("Tracker URI:", uri)
    ns = Pyro4.locateNS()
    ns.register("tracker.server", uri)
    print("Tracker registered with name server.")
    daemon.requestLoop()


if __name__ == "__main__":
    start_tracker()
