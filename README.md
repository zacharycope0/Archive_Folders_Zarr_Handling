# zarr_tools

Utilities for managing large zarr datasets in WSL2.

## Scripts

### `analyze_folders.py`
Walks a root directory and outputs a CSV showing the size of every subfolder.
Useful for identifying what's eating disk space before archiving.

**User vars to set:**
| Var | Default | Description |
|-----|---------|-------------|
| `SCAN_ROOT` | `$DIR_HOME` | Root directory to scan |
| `MAX_DEPTH` | `3` | How many levels deep to scan |
| `OUTPUT_CSV` | `$DIR_HOME/folder_sizes.csv` | Where to write results |
| `MIN_SIZE_BYTES` | `0` | Skip folders smaller than this |

```bash
python analyze_folders.py
```

---

### `move_zarr_etc.py`
Archives a folder to a destination drive, preserving file structure.

- `.zarr` directories → tarred as `<name>.zarr.tar` (not extracted)
- Everything else → copied as-is

Zarrs are kept as `.tar` on the destination to avoid the tens-of-thousands
of small chunk files that make exFAT drives slow and waste cluster space.

**User vars to set:**
| Var | Default | Description |
|-----|---------|-------------|
| `SRC` | example path | Source folder to archive |
| `DST` | `/mnt/d/wsl_archive` | Destination root on SSD |
| `DEL_AFTER_MOVE` | `False` | Delete source after verified transfer |

```bash
python move_zarr_etc.py
```

A `_transfer_report.csv` is written to the destination after each run,
logging every file/zarr transferred and its verification status.

---

### `move_zarr.py`
Original single-zarr mover (tar-based). Kept for moving individual zarrs.

---

## Notes

- Windows paths (`D:\foo`) are auto-converted to WSL paths (`/mnt/d/foo`)
- No compression is used on zarr tars — zarr chunks are already compressed internally
- `DEL_AFTER_MOVE` only deletes source items that passed the size check
