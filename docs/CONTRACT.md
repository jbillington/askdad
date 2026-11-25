# The askdad contract

How another program runs Ask Dad and reads the result. The readers are the Mac app, agents and scripts.

`askdad` is run once for each scan. It prints progress as JSON lines, writes the result to a JSON file (the manifest), and exits. There is no server and no port, and it makes no network calls.

Contract version: **1**. The code is `utils/events.py` and `build_manifest()` in `askdad.py`.

## Commands

| Command | What it does | Result |
|---|---|---|
| `askdad storage --json` | Storage scan | A manifest file |
| `askdad cpu --json` | Memory and CPU scan | A manifest file |
| `askdad all --json` | Both | Two manifest files |
| `askdad permissions --json` | What this run can read, with no scan | Inline in the `result` event |

`askdad --json` with no command is the storage scan. `--json` works before or after the command.

In JSON mode `askdad`:

- prints only JSON on stdout, one object per line;
- asks no question and waits for no key;
- opens no browser and no settings pane;
- scans the startup disk (`/`) unless `--volume PATH` is given. The volume picker does not run. A path that does not exist is an error.

The other scan flags work as they do without `--json`: `--volume`, `--top`, `--min-size`, `--skip-protected`, `--no-mac-libraries`, `--library-timeout`, `--test-reports`, `--timings`. `--terminal` cannot be combined with `--json`, because it skips the manifest.

The scanner is read-only. It writes two files for each scan, the manifest and the HTML report, in `~/.dadware/reports/`. A run from a git checkout writes them to `test-reports/` in the checkout instead. The first storage scan also leaves an empty marker file, `~/.dadware/.permissions-introduced`.

## Streams and exit codes

| | |
|---|---|
| stdout | Events only. Every line is one JSON object. |
| stderr | Text for a person: warnings, timings, tracebacks. Not part of the contract. Ignore it or log it. |
| Exit 0 | The scan finished and a `result` event was sent. |
| Exit 1 | The scan failed. An `error` event was sent first. |
| Exit 2 | The command line was wrong. Nothing is on stdout; the usage message is on stderr. |

To cancel a scan, end the process. No report file is written until the scan finishes, so a cancelled scan leaves no partial report.

## Events

Each line has an `event` key. A reader must ignore events and keys it does not know.

```json
{"event": "start", "command": "storage", "askdad_version": "1.0-beta.2", "schema_version": 1}
{"event": "say", "text": "digging through the attic..."}
{"event": "progress", "items": 412000, "elapsed": 80.2}
{"event": "result", "type": "storage", "manifest": "/Users/x/.dadware/reports/storage_2026-11-22_10-33.json", "html": "/Users/x/.dadware/reports/storage_2026-11-22_10-33.html"}
```

| Event | When | Keys |
|---|---|---|
| `start` | First line, always | `command`, `askdad_version`, `schema_version` |
| `say` | Dad says what he is doing. Any number, at any time | `text`: one line, ready to show. It can hold a path |
| `progress` | During the storage walk, about every two seconds | `items`: files and folders seen so far. `elapsed`: seconds. There is no total, so no percentage |
| `result` | A scan finished. Once for each scan, so twice for `all` | `type`: `storage`, `cpu` or `permissions`. For scans: `manifest` and `html`, both absolute paths. For `permissions`: `permissions` (below) |
| `error` | The run failed. At most one | `code`, and `text` for a person |

Error codes: `volume_not_found`, `scan_failed`, `cancelled` (the process received an interrupt), `internal_error`.

For `all`, a CPU scan that fails does not fail the run: the storage `result` is sent, there is no CPU `result`, and the exit code is 0.

### The permissions result

```json
{"event": "result", "type": "permissions", "permissions": {
  "full_disk_access": {
    "has_access": false,
    "missing_permissions": ["messages", "mail", "photos"],
    "details": {"messages": {"has_access": false, "reason": "permission_denied"}}
  },
  "folders": {
    "Desktop":   {"status": "granted", "path": "/Users/x/Desktop"},
    "Documents": {"status": "denied",  "path": "/Users/x/Documents", "reason": "tcc"},
    "Downloads": {"status": "not_found", "path": "/Users/x/Downloads"}
  }
}}
```

A folder's `status` is `granted`, `denied`, `not_found` or `error`. A `denied` folder has `reason` `tcc` (macOS privacy) or `posix` (file permissions).

This command reads Desktop, Documents and Downloads. The first time a program does that, macOS shows its permission dialog, and the command waits for the answer. A storage scan does the same at its start.

Full Disk Access is judged by trying to read Messages, Mail and the Photos library. macOS has no call that answers the question directly. The Photos library also opens with the separate Photos permission, so `photos` can be readable while Messages and Mail are not. Take Messages and Mail as the sign of Full Disk Access.

## The manifest

One JSON file for each scan. The `result` event gives its path.

```json
{
  "schema_version": 1,
  "askdad_version": "1.0-beta.2",
  "report_id": "storage_2026-11-22_10-33",
  "generated_at": "2026-11-22T10:33:41.120394",
  "scan_results": {"storage": {}},
  "grades": {},
  "personality": {"status": "warn", "comments": ["..."], "tips": ["..."]},
  "personality_comments": ["..."],
  "report_files": {"html": "/Users/x/.dadware/reports/storage_2026-11-22_10-33.html"}
}
```

`scan_results` has one key, `storage` or `cpu`. `generated_at` is local time with no zone. File names carry the time to the minute, so a second scan of the same kind in the same minute replaces the first.

A manifest written before version 1 has no `schema_version`, `askdad_version`, `grades` or `personality`. Read a missing `schema_version` as 0.

Sizes ending in `_bytes` are bytes on disk. Each has a `_human` twin ("48.3 GB") formatted the way the reports show it.

### Dad's comments

`personality.status` is `ok`, `warn` or `critical`. `comments` are Dad's remarks about this Mac and `tips` are what he suggests, both as finished sentences. `personality_comments` is the same list as `personality.comments`, kept for older readers.

### Grades (storage, startup disk only)

`grades` is present for a storage scan of the startup disk. A scan of another drive has no grades, and neither does a CPU scan.

```json
"grades": {
  "overall": {"letter": "C", "score": 71.06, "max": 100, "comment": "Room for improvement"},
  "components": {
    "free_space":           {"letter": "D", "score": 62.0, "max": 100, "weight": 0.5},
    "home_folders_ratio":   {"letter": "A", "score": 100,  "max": 100, "weight": 0.15},
    "home_folders_clutter": {"letter": "C", "score": 72,   "max": 100, "weight": 0.2},
    "mac_libraries":        {"letter": "A", "score": 100,  "weight": 0.15}
  },
  "libraries": {
    "photos":   {"name": "Photos",   "letter": "A", "score": 100, "size_bytes": 48318382080, "size_human": "48.3 GB", "status": "complete", "reason": "", "graded": true},
    "messages": {"name": "Messages", "letter": "-", "score": 0,   "size_bytes": 6442450944,  "size_human": "6.4 GB",  "status": "complete", "reason": "", "graded": false}
  },
  "libraries_scored": true,
  "libraries_not_scored_reason": null,
  "clutter_scored": true,
  "clutter_blocked_folders": []
}
```

- A letter is `A`, `B`, `C`, `D` or `F`. `home_folders_ratio` can be `N/A`. A library with no grade has `-`.
- `components` holds only what counted toward the overall grade, and the weights add up to 1. When the libraries could not be scored, `mac_libraries` is absent and the other weights grow to fill the gap.
- `clutter_scored` is false when macOS blocked Downloads or Desktop, which the scan could then not measure. `home_folders_clutter` is then absent from `components`, and `clutter_blocked_folders` names the blocked folders. Older manifests do not have these two keys; there, a clutter grade was given even for a blocked folder.
- `libraries_not_scored_reason` is `needs_full_disk_access`, `incomplete`, `not_scanned` or null.
- `libraries` lists a library when it has a size, was skipped, or could not be read. A library's `status` is `complete`, `partial` (the size is a floor), `skipped`, `error`, `interrupted` or `denied` (macOS would not let the scan read it). A library with no size has `size_bytes` 0 here, so read `status` before showing the size. `graded` is false for Messages (its size is shown, never graded) and for any library with no size.
- A component can carry extra keys, such as `ratio_percent` or `downloads_size`.

How each grade is worked out is in `docs/GRADING.md`.

### Storage scan

`scan_results.storage`:

| Key | What it is |
|---|---|
| `volume` | The path that was scanned |
| `scan_scope` | `home_volume` (the startup disk) or `other_volume`. Another drive has none of the keys marked "startup disk" below |
| `home_path` | The home folder at scan time. A folder is a home folder if its path is under this |
| `volume_info` | `total_bytes`, `used_bytes`, `free_bytes`, `used_percent`, `free_percent`, and `_human` twins |
| `top_folders` | Largest folders, biggest first. Each: `path`, `size_bytes`, `size_human`, sometimes `path_display` (a friendlier name, such as "Trash"), `subfolders` and `top_files` |
| `top_files` | Largest files. Each: `path`, `size_bytes`, `size_human`, `mtime` (seconds since 1970), `is_sparse`, `is_docker` |
| `home_folders_total_bytes` | The home folders added up |
| `metrics` | `sum_top_10_folders_bytes`, `sum_top_25_files_bytes`, `reclaimable_percent` |
| `excluded_count` | Items left out on purpose (dotfiles, caches, the system) |
| `denied_count` | Items the file system refused to show |
| `denied_paths` | The refused paths by name: `[{"path": "...", "reason": "tcc"}]`. At most 200, so it can be shorter than `denied_count` |
| `unreadable_paths` | Folders that could not be listed for another reason, such as a cloud drive that did not answer: `[{"path": "...", "error": "Operation timed out"}]`. Everything inside them is missing from the numbers. At most 200. Older manifests do not have this key |
| `skipped_count` | `excluded_count` plus `denied_count` |
| `duration_seconds` | The whole run |
| `trash` | `locations` (each with `label`, `path`, `size_bytes`, `item_count` and a `status`: `measured`, `empty`, `missing`, `no_permission` or `error`), `total_size_bytes`, `item_count`, `permission_denied` |
| `permission_status` | Startup disk. `has_access`, `missing_permissions`, `details`, and `folders` (the same shape as the permissions result) |
| `mac_libraries` | Startup disk. `photos`, `music`, `messages`, `mail`, `creative`, `time_machine`, each with a size and a `status` (`complete`, `partial`, `denied`, `error` or `skipped`), plus `scan_status` for the whole group. A library that was refused or not measured has a size of `null`, with `size_human` "not measured" |
| `hidden_caches` | Startup disk. `entries` (app caches and logs, each with `path`, `app_name`, `size_bytes`, `category`), `roots`, `total_size_bytes`, `scan_status`, `permission_denied` |
| `snapshots` | Startup disk. Local APFS snapshots: `snapshots` (each with `name`, `created`, `age_days`, `is_os_update`), `count`, `oldest_age_days`, `status` |

A `denied_paths` reason is `tcc` or `posix`. `tcc` is macOS privacy protection, which Full Disk Access or a folder permission lifts. `posix` is ordinary file permissions, such as another user's home folder, and no privacy setting changes it. Only the `tcc` paths are worth mentioning beside an offer of Full Disk Access.

A measurement that was blocked is never reported as a real zero. Before showing a size, look for a `null` size, a `denied` or `no_permission` status, `permission_denied`, or an entry in `missing_permissions`.

### Memory and CPU scan

`scan_results.cpu`:

| Key | What it is |
|---|---|
| `total_memory_bytes`, `total_memory_gb`, `total_used_gb` | Installed and used memory |
| `memory_pressure` | `pressure` (the level, as a word), `pressure_source`, and the parts in bytes and GB: `free`, `active`, `inactive`, `wired`, `compressed`, `available`; `swapins`, `swapouts` |
| `memory_hogs` | Apps grouped across their processes: `name`, `process_count`, `total_mb` |
| `top_memory_processes`, `top_processes` | Single processes by memory and by CPU: `name`, `memory_mb`, `cpu_percent` |
| `all_processes` | Every process, same keys |
| `process_metrics` | Counts and totals by size band |
| `duration_seconds` | The whole run |

Process names come from the Mac being scanned. Treat every path and name in a manifest as untrusted text and escape it before display.

## Versioning

`schema_version` is one whole number, in the `start` event and in the manifest.

- Adding a key, an event, an error code or a status value does not change the version. Readers must ignore what they do not know.
- Removing a key, renaming one or changing what one means raises the version by one.
- A reader that meets a version higher than it knows should say so and stop, since it cannot tell what changed.

## Not built yet

These are planned and are not part of version 1. Do not rely on them.

- A way to hand the scanner sizes that only a Mac app can measure, such as a folder total from Finder. Until then a refused area stays not measured.
- A cleanup candidates command.
- A flag to skip the HTML report.
- A long-running mode over stdin and stdout, for faster repeated questions. It would carry these same events.
