"""
analyze_folders.py
------------------
Walks a root directory and outputs a CSV with the size of every subfolder.
Useful for identifying what's eating disk space before deciding what to archive.

Output CSV columns:
  path         : full path to the folder
  size_bytes   : total size in bytes
  size_gb      : total size in GB (rounded to 3 decimal places)
  n_files      : number of files inside
  is_zarr      : True if the folder is a .zarr store
"""

import os
import csv
import subprocess
from pathlib import Path

# =============================================================================
# USER VARS
# =============================================================================

# Root directory to analyze
SCAN_ROOT = Path(os.environ.get("DIR_HOME", Path.home() / "Code_WSL"))

# How many levels deep to scan (1 = direct children only, 2 = one level deeper, etc.)
MAX_DEPTH = 3

# Output CSV path
OUTPUT_CSV = Path(os.environ.get("DIR_HOME", Path.home() / "Code_WSL")) / "folder_sizes.csv"

# Only report folders larger than this (bytes). 0 = report everything.
MIN_SIZE_BYTES = 0

# =============================================================================


def get_du(path: Path) -> int:
    """Return total size of path in bytes using du."""
    result = subprocess.run(
        ["du", "-sb", str(path)],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        return 0
    return int(result.stdout.split()[0])


def count_files(path: Path) -> int:
    """Count files recursively under path."""
    result = subprocess.run(
        ["find", str(path), "-type", "f"],
        capture_output=True, text=True
    )
    return result.stdout.count("\n")


def get_subfolders(root: Path, max_depth: int):
    """Yield (path, depth) for all subdirectories up to max_depth."""
    for dirpath, dirnames, _ in os.walk(root):
        current = Path(dirpath)
        depth = len(current.relative_to(root).parts)
        if depth > max_depth:
            dirnames.clear()  # prune walk
            continue
        if depth == 0:
            continue  # skip root itself
        yield current, depth
        # Don't recurse into zarr stores — treat them as atomic units
        if current.suffix == ".zarr":
            dirnames.clear()


def main():
    print(f"Scanning: {SCAN_ROOT}")
    print(f"Max depth: {MAX_DEPTH}\n")

    rows = []
    folders = list(get_subfolders(SCAN_ROOT, MAX_DEPTH))
    total = len(folders)

    for i, (folder, depth) in enumerate(folders, 1):
        size = get_du(folder)
        if size < MIN_SIZE_BYTES:
            continue
        n_files = count_files(folder)
        is_zarr = folder.suffix == ".zarr"

        rows.append({
            "path": str(folder),
            "size_bytes": size,
            "size_gb": round(size / 1024**3, 3),
            "n_files": n_files,
            "is_zarr": is_zarr,
        })

        tag = " [zarr]" if is_zarr else ""
        print(f"  [{i}/{total}] {folder.name}{tag}  {round(size/1024**3, 2)} GB")

    # Sort by size descending
    rows.sort(key=lambda r: r["size_bytes"], reverse=True)

    # Write CSV
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["path", "size_bytes", "size_gb", "n_files", "is_zarr"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nDone. Results written to: {OUTPUT_CSV}")
    print(f"Top 5 largest folders:")
    for r in rows[:5]:
        print(f"  {r['size_gb']:.2f} GB  {r['path']}")


if __name__ == "__main__":
    main()
