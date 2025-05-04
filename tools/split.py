import os
import sys
import shutil

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from chunk_utils import split_file

SOURCE_FILE = "tools/music/comf_numb.mp3"
NUM_PEERS = 3
DEST_DIR = "peers"

TEMP_DIR = "temp_split"

def distribute_chunks(temp_parts):
    for i, part in enumerate(temp_parts):
        peer_num = (i % NUM_PEERS) + 1
        peer_dir = os.path.join(DEST_DIR, f"peer{peer_num}", "music")
        os.makedirs(peer_dir, exist_ok=True)
        dest = os.path.join(peer_dir, os.path.basename(part))
        shutil.move(part, dest)
        print(f"{part} → Peer {peer_num}")

if __name__ == "__main__":
    print(f"Splitting {SOURCE_FILE} into chunks...")
    parts = split_file(SOURCE_FILE, TEMP_DIR)
    print(f"➡Distributing {len(parts)} chunks across {NUM_PEERS} peers...")
    distribute_chunks(parts)

    # cleanup temp dir
    shutil.rmtree(TEMP_DIR)
    print(f"Cleaned up temporary chunks from {TEMP_DIR}")
