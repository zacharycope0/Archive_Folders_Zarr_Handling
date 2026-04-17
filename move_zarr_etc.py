"""
move_zarr_etc.py
----------------
Archives a folder to a destination drive, preserving file structure.

Rules:
  - .zarr directories  → tarred as <name>.zarr.tar (NOT extracted)
  - everything else    → copied as-is with shutil

This keeps zarr chunk overhead off the destination drive while leaving
all other files in their normal accessible form.

DEL_AFTER_MOVE: if True, deletes source files/folders after verified transfer.
"""

import os
import subprocess
import shutil
import csv
from pathlib import Path

# =============================================================================
# USER VARS
# =============================================================================

DIR_HOME = Path(os.environ.get("DIR_HOME", Path.home() / "Code_WSL"))
FILE_STRUCTURE = "downloads/psps/input_data/wfpi/2026_master"

# Source folder to archive (can be any folder — zarrs inside will be auto-detected)
SRC = DIR_HOME / FILE_STRUCTURE

# Destination root on the SSD (file structure under SRC will be mirrored here)
DST = Path("/mnt/d/00_WSL_BACKUP") / FILE_STRUCTURE

# If True, deletes each source item after it is verified successfully transferred
DEL_AFTER_MOVE = True
# =============================================================================


def win_to_wsl(path: Path) -> Path:
    """Convert Windows path (D:\\foo) to WSL mount path (/mnt/d/foo)."""
    parts = path.parts
    if len(parts) > 0 and len(parts[0]) >= 2 and parts[0][1] == ":":
        drive_letter = parts[0][0].lower()
        rest = Path(*parts[1:]) if len(parts) > 1 else Path()
        return Path(f"/mnt/{drive_letter}") / rest
    return path


def get_size_bytes(path: Path) -> int:
    """Return total size in bytes using du."""
    result = subprocess.run(
        ["du", "-sb", str(path)],
        capture_output=True, text=True, check=True
    )
    return int(result.stdout.split()[0])


def format_size(n: int) -> str:
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if n < 1024:
            return f"{n:.2f} {unit}"
        n /= 1024
    return f"{n:.2f} PB"


def tar_zarr(src_zarr: Path, dst_dir: Path) -> Path:
    """
    Tar a .zarr directory into dst_dir/<name>.zarr.tar
    No compression — zarr chunks are already compressed internally.
    Returns the path to the created tar.
    """
    tar_path = dst_dir / f"{src_zarr.name}.tar"
    print(f"    Tarring zarr → {tar_path.name}")
    subprocess.run(
        ["tar", "-cf", str(tar_path), "-C", str(src_zarr.parent), src_zarr.name],
        check=True
    )
    return tar_path


def copy_item(src_item: Path, dst_item: Path):
    """Copy a file or non-zarr directory to dst."""
    if src_item.is_file():
        dst_item.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(src_item), str(dst_item))
    elif src_item.is_dir():
        shutil.copytree(str(src_item), str(dst_item))


def transfer_file(src_file: Path, dst_file: Path) -> list[dict]:
    """Transfer a single file. Returns a one-entry log."""
    dst_file.parent.mkdir(parents=True, exist_ok=True)
    print(f"  [file] {src_file.name}")
    shutil.copy2(str(src_file), str(dst_file))

    src_size = src_file.stat().st_size
    dst_size = dst_file.stat().st_size
    size_ok = src_size == dst_size
    status = "OK" if size_ok else "SIZE_MISMATCH"
    print(f"         Size: {format_size(src_size)}  [{status}]")

    if not size_ok:
        print(f"  Warning: size mismatch for {src_file.name} — source NOT deleted.")

    entry = {
        "type": "file",
        "src": str(src_file),
        "dst": str(dst_file),
        "src_size_bytes": src_size,
        "dst_size_bytes": dst_size,
        "status": status,
    }

    if DEL_AFTER_MOVE and size_ok:
        src_file.unlink()
        print(f"         Source deleted.")

    return [entry]


def transfer(src_root: Path, dst_root: Path) -> list[dict]:
    """
    Walk src_root, mirroring structure to dst_root.
    Zarrs are tarred; everything else is copied.
    Returns a log of transferred items for the CSV report.
    """
    log = []

    for dirpath, dirnames, filenames in os.walk(src_root):
        current = Path(dirpath)
        rel = current.relative_to(src_root.parent)  # preserve src folder name in dst
        dst_current = dst_root / rel

        # --- Handle .zarr directories ---
        zarr_dirs = [d for d in dirnames if d.endswith(".zarr")]
        for zarr_name in zarr_dirs:
            src_zarr = current / zarr_name
            src_size = get_size_bytes(src_zarr)
            dst_current.mkdir(parents=True, exist_ok=True)

            print(f"\n  [zarr] {src_zarr.relative_to(src_root.parent)}")
            print(f"         Size: {format_size(src_size)}")

            tar_path = tar_zarr(src_zarr, dst_current)
            tar_size = tar_path.stat().st_size

            # Tar size should be close to src size (within 5% tolerance for metadata diff)
            size_ok = abs(tar_size - src_size) / max(src_size, 1) < 0.05
            status = "OK" if size_ok else "SIZE_MISMATCH"
            print(f"         Tar size: {format_size(tar_size)}  [{status}]")

            if not size_ok:
                print(f"  Warning: size mismatch for {zarr_name} — source NOT deleted.")

            log.append({
                "type": "zarr",
                "src": str(src_zarr),
                "dst": str(tar_path),
                "src_size_bytes": src_size,
                "dst_size_bytes": tar_size,
                "status": status,
            })

            if DEL_AFTER_MOVE and size_ok:
                shutil.rmtree(src_zarr)
                print(f"         Source deleted.")

            dirnames.remove(zarr_name)  # don't recurse into zarr

        # --- Handle regular files ---
        for fname in filenames:
            src_file = current / fname
            dst_file = dst_current / fname
            dst_current.mkdir(parents=True, exist_ok=True)

            print(f"  [file] {src_file.relative_to(src_root.parent)}")
            shutil.copy2(str(src_file), str(dst_file))

            src_size = src_file.stat().st_size
            dst_size = dst_file.stat().st_size
            size_ok = src_size == dst_size
            status = "OK" if size_ok else "SIZE_MISMATCH"

            log.append({
                "type": "file",
                "src": str(src_file),
                "dst": str(dst_file),
                "src_size_bytes": src_size,
                "dst_size_bytes": dst_size,
                "status": status,
            })

            if DEL_AFTER_MOVE and size_ok:
                src_file.unlink()

    return log


def write_report(log: list[dict], report_dir: Path):
    """Write transfer log CSV into report_dir."""
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"{SRC.name}_transfer_report.csv"
    with open(report_path, "w", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["type", "src", "dst", "src_size_bytes", "dst_size_bytes", "status"]
        )
        writer.writeheader()
        writer.writerows(log)
    print(f"\nTransfer report written to: {report_path}")
    return report_path


def write_transfer_readme(src: Path, dst: Path):
    """
    Leave a TRANSFER_README.txt in the source parent directory so it's easy
    to find where the data went without re-running the script.
    """
    readme_dir = src if src.is_dir() else src.parent
    readme_path = readme_dir / "TRANSFER_README.txt"

    from datetime import datetime
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    entry = (
        f"Date        : {timestamp}\n"
        f"Transferred : {src}\n"
        f"Destination : {dst}\n"
        f"DEL_AFTER_MOVE: {DEL_AFTER_MOVE}\n"
    )

    if readme_path.exists():
        with open(readme_path, "a") as f:
            f.write("\n" + entry)
    else:
        header = (
            "TRANSFER README\n"
            + "=" * 50 + "\n"
            + "Written by move_zarr_etc.py. "
            + "See _transfer_report.csv for per-file details.\n"
            + "=" * 50 + "\n\n"
        )
        readme_path.write_text(header + entry)

    print(f"TRANSFER_README.txt written to: {readme_path}")


def main():
    src = SRC
    dst = win_to_wsl(DST)

    if not src.exists():
        raise FileNotFoundError(f"Source not found: {src}")

    total_src_size = get_size_bytes(src)
    print(f"Source: {src}  ({'file' if src.is_file() else 'directory'})")
    print(f"Destination: {dst}")
    print(f"Total source size: {format_size(total_src_size)}")
    print(f"DEL_AFTER_MOVE: {DEL_AFTER_MOVE}\n")
    print("Starting transfer...\n")

    if src.is_file():
        log = transfer_file(src, dst)
        report_dir = dst.parent
    else:
        dst.mkdir(parents=True, exist_ok=True)
        log = transfer(src, dst)
        report_dir = dst

    # Summary
    ok = [r for r in log if r["status"] == "OK"]
    bad = [r for r in log if r["status"] != "OK"]
    print(f"\n{'='*50}")
    print(f"Transfer complete: {len(ok)} OK, {len(bad)} mismatches")
    if bad:
        print("  Mismatches (source NOT deleted):")
        for r in bad:
            print(f"    {r['src']}")

    write_report(log, report_dir)
    write_transfer_readme(src, dst)


if __name__ == "__main__":
    main()
