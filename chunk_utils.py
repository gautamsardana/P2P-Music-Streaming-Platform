import os
import time

from config import CHUNK_SIZE


def split_file(filepath, output_dir, chunk_size=CHUNK_SIZE):
    os.makedirs(output_dir, exist_ok=True)
    parts = []

    base_name = os.path.basename(filepath)
    name, ext = os.path.splitext(base_name)

    with open(filepath, "rb") as f:
        i = 0
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            partname = f"{name}.part{i}{ext}"
            full_path = os.path.join(output_dir, partname)
            with open(full_path, "wb") as pf:
                pf.write(chunk)
            parts.append(full_path)
            i += 1

    return parts


def combine_file(parts, output_path):
    with open(output_path, "wb") as f:
        for part in sorted(parts):
            with open(part, "rb") as pf:
                f.write(pf.read())


def tracker_call(callable_fn, *args, retries=3, delay=1, description="Tracker call"):
    for attempt in range(retries):
        try:
            return callable_fn(*args)
        except Exception as e:
            print(f"[WARN] {description} failed (attempt {attempt + 1}): {e}")
            time.sleep(delay)
    print(f"[ERROR] {description} failed after {retries} attempts.")
    return None
