"""Mac app library scanner - finds and measures Mac app data libraries."""

import os
import subprocess
import time
from typing import Any, Dict, List, Optional, Tuple

from utils.formatters import format_size
from utils.path_utils import should_skip_path, get_file_size_disk, get_folder_size_generic

# Shown in place of a size when a library could not be measured. A refused
# read is never reported as 0 B: readers of the manifest (the HTML report,
# the AI prompt, the native app) would take a zero for an empty library.
NOT_MEASURED = 'not measured'

# `du` on a large Photos library on a slow disk takes well over 10 seconds.
# Generous, like the per-folder limit in scanners/hidden_storage.py.
PHOTOS_DU_TIMEOUT_SECONDS = 120


def _read_refused(path: str) -> Optional[str]:
    """Return the error text if macOS refuses to list `path`, else None.

    Without Full Disk Access, listing ~/Library/Messages or ~/Library/Mail
    raises PermissionError ("Operation not permitted"). The folder walk
    swallows that and returns 0 bytes, so the refusal has to be checked
    before the walk, or a blocked library reads as an empty one.
    """
    try:
        os.listdir(path)
    except PermissionError as e:
        return e.strerror or 'Permission denied'
    except OSError:
        return None
    return None


def _denied_result(lib_type: str, path: str, error: str) -> Dict[str, Any]:
    """The result for a library macOS would not let us read."""
    return {
        'type': lib_type,
        'path': path,
        'size_bytes': None,
        'size_human': NOT_MEASURED,
        'count': None,
        'status': 'denied',
        'error': error,
    }


def get_folder_size(folder_path: str, min_size_bytes: int = 0, max_depth: int = 10,
                     current_depth: int = 0, skip_hidden: bool = False) -> Tuple[int, int]:
    """
    Calculate folder size recursively, respecting depth limit.
    Skips heavy paths like Mobile Documents, CloudStorage, Containers.
    Uses actual disk usage (st_blocks) for all files.

    Thin wrapper around the shared utils.path_utils.get_folder_size_generic(),
    using the library scanner's sizing (get_file_size_disk) and skip
    (should_skip_path, which is not depth-aware) rules.
    """
    return get_folder_size_generic(
        folder_path,
        size_fn=get_file_size_disk,
        skip_fn=lambda path, depth: should_skip_path(path),
        min_size_bytes=min_size_bytes,
        max_depth=max_depth,
        current_depth=current_depth,
        skip_hidden=skip_hidden,
    )


def find_photos_libraries() -> List[str]:
    """
    Find Photos libraries using non-recursive search in allowlist paths only.
    Returns list of .photoslibrary bundle paths.
    """
    libraries = []
    home = os.path.expanduser('~')
    
    # Small allowlist of base paths - no recursive glob
    search_paths = [
        os.path.join(home, 'Pictures'),
        os.path.join(home, 'Library', 'Application Support', 'Photos'),
    ]
    
    # Also check for common direct paths
    direct_paths = [
        os.path.join(home, 'Pictures', 'Photos Library.photoslibrary'),
        os.path.join(home, 'Pictures', 'iPhoto Library.photolibrary'),  # Old iPhoto
    ]
    
    # Check direct paths first
    for lib_path in direct_paths:
        if os.path.exists(lib_path) and os.path.isdir(lib_path):
            libraries.append(lib_path)
    
    # Check allowlist paths using non-recursive os.scandir()
    for search_path in search_paths:
        if not os.path.exists(search_path):
            continue
        
        try:
            with os.scandir(search_path) as entries:
                for entry in entries:
                    if entry.is_dir() and entry.name.endswith('.photoslibrary'):
                        lib_path = entry.path
                        if lib_path not in libraries:
                            libraries.append(lib_path)
        except (OSError, PermissionError):
            continue
    
    return libraries


def get_photos_library_size(lib_path: str) -> Tuple[Optional[int], Optional[str], bool]:
    """
    Size a Photos library with `du -skx` (the package as one leaf).

    Returns (bytes or None, note, refused). `du` on a library it can only
    partly read exits non-zero but still prints a total; that total is kept,
    with a note, because it is a floor. When there is no total at all (a
    refusal, a timeout) the size is None, never 0. `refused` is True when
    macOS blocked the read (no Photos or Full Disk Access permission).
    """
    if not lib_path or not isinstance(lib_path, str):
        return None, 'Could not measure this library', False

    cmd = ['/usr/bin/du', '-skx', lib_path]
    try:
        from utils.subprocess_utils import log_subprocess_call
        log_subprocess_call("get_photos_library_size()", cmd)
        result = subprocess.run(cmd, capture_output=True, text=True,
                                timeout=PHOTOS_DU_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        return None, 'Timed out measuring this library', False
    except (FileNotFoundError, OSError, ValueError, TypeError):
        return None, 'Could not measure this library', False

    stderr = (result.stderr or '').lower()
    refused = 'not permitted' in stderr or 'permission denied' in stderr
    try:
        size_kb = int((result.stdout or '').split()[0])
    except (ValueError, IndexError):
        if refused:
            return None, 'Permission restricted - size unavailable', True
        return None, 'Could not measure this library', False

    if result.returncode != 0:
        return size_kb * 1024, 'Permission restricted - size may be incomplete', refused
    return size_kb * 1024, None, False


def scan_photos_library() -> Dict[str, Any]:
    """
    Scan for Photos libraries (.photoslibrary).
    Uses non-recursive search in allowlist paths only.
    Treats each library as a leaf and uses du -skx for size.

    The result's `status` is set here when something was not fully
    measured: 'denied' when macOS refused every library, 'error' when none
    could be measured for another reason (a timeout), and 'partial' when
    the total leaves something out. scan_all_mac_libraries() fills in
    'complete' otherwise.
    """
    libraries = []
    found_paths = find_photos_libraries()

    for lib_path in found_paths:
        size_bytes, note, refused = get_photos_library_size(lib_path)
        entry = {
            'path': lib_path,
            'name': os.path.basename(lib_path),
            'size_bytes': size_bytes,
            'size_human': format_size(size_bytes) if size_bytes is not None else NOT_MEASURED,
            'type': 'photos',
        }
        if note:
            entry['note'] = note
        if refused:
            entry['refused'] = True
        libraries.append(entry)

    # Largest first; unmeasured libraries last.
    libraries.sort(key=lambda x: x['size_bytes'] if x['size_bytes'] is not None else -1,
                   reverse=True)

    measured = [lib for lib in libraries if lib['size_bytes'] is not None]
    total_size = sum(lib['size_bytes'] for lib in measured)
    result = {
        'type': 'photos',
        'libraries': libraries,
        'total_size_bytes': total_size,
        'total_size_human': format_size(total_size),
        'count': len(libraries)
    }

    if libraries and not measured:
        result['total_size_bytes'] = None
        result['total_size_human'] = NOT_MEASURED
        if all(lib.get('refused') for lib in libraries):
            result['status'] = 'denied'
            result['error'] = 'Permission restricted - size unavailable'
        else:
            result['status'] = 'error'
            result['error'] = next(lib['note'] for lib in libraries if lib.get('note'))
    elif any(lib.get('note') for lib in libraries):
        result['status'] = 'partial'
    return result


def scan_music_library() -> Dict[str, Any]:
    """Scan for Music/iTunes libraries."""
    home = os.path.expanduser('~')
    music_paths = [
        os.path.join(home, 'Music', 'Music'),
        os.path.join(home, 'Music', 'iTunes'),
        os.path.join(home, 'Music')
    ]
    
    libraries = []
    total_size = 0

    # ~/Music contains ~/Music/Music and ~/Music/iTunes, so measuring all
    # three would count the inner folders twice. Keep only paths that are
    # not inside another candidate.
    music_paths = [
        p for p in music_paths
        if not any(q != p and p.startswith(q.rstrip('/') + '/') for q in music_paths)
    ]

    for music_path in music_paths:
        if os.path.exists(music_path) and os.path.isdir(music_path):
            try:
                size, _ = get_folder_size(music_path, min_size_bytes=0, max_depth=10, current_depth=0)
                libraries.append({
                    'path': music_path,
                    'name': os.path.basename(music_path),
                    'size_bytes': size,
                    'size_human': format_size(size),
                    'type': 'music'
                })
                total_size += size
            except (OSError, PermissionError):
                continue
    
    return {
        'type': 'music',
        'libraries': libraries,
        'total_size_bytes': total_size,
        'total_size_human': format_size(total_size),
        'count': len(libraries)
    }


def scan_messages() -> Dict[str, Any]:
    """Scan Messages library."""
    home = os.path.expanduser('~')
    messages_path = os.path.join(home, 'Library', 'Messages')
    
    if not os.path.exists(messages_path):
        return {
            'type': 'messages',
            'path': messages_path,
            'size_bytes': 0,
            'size_human': format_size(0),
            'count': 0
        }
    
    refused = _read_refused(messages_path)
    if refused:
        return _denied_result('messages', messages_path, refused)

    try:
        # Try with deeper depth for Messages as it can have nested structure
        # Don't skip hidden files - Messages uses hidden files
        size, count = get_folder_size(messages_path, min_size_bytes=0, max_depth=15, current_depth=0, skip_hidden=False)
        # If we got 0, try a more aggressive scan
        if size == 0:
            # Check if directory exists and has contents
            try:
                if os.listdir(messages_path):
                    # Directory exists but size is 0 - might be permission issue
                    # Try to get size of individual files
                    size = 0
                    for root, dirs, files in os.walk(messages_path):
                        for file in files:
                            try:
                                file_path = os.path.join(root, file)
                                # Use actual disk usage (st_blocks) instead of logical size
                                stat_info = os.stat(file_path)
                                size += stat_info.st_blocks * 512
                            except (OSError, PermissionError):
                                pass
                        # Limit depth manually
                        if root.count(os.sep) - messages_path.count(os.sep) >= 5:
                            dirs[:] = []
            except (OSError, PermissionError):
                pass
        
        return {
            'type': 'messages',
            'path': messages_path,
            'size_bytes': size,
            'size_human': format_size(size),
            'count': count
        }
    except PermissionError as e:
        return _denied_result('messages', messages_path, e.strerror or str(e))
    except OSError as e:
        return {
            'type': 'messages',
            'path': messages_path,
            'size_bytes': None,
            'size_human': NOT_MEASURED,
            'count': None,
            'status': 'error',
            'error': str(e),
        }


def scan_mail() -> Dict[str, Any]:
    """Scan Mail library."""
    home = os.path.expanduser('~')
    mail_path = os.path.join(home, 'Library', 'Mail')
    
    if not os.path.exists(mail_path):
        return {
            'type': 'mail',
            'path': mail_path,
            'size_bytes': 0,
            'size_human': format_size(0),
            'count': 0
        }
    
    refused = _read_refused(mail_path)
    if refused:
        return _denied_result('mail', mail_path, refused)

    try:
        # Don't skip hidden files for Mail
        size, count = get_folder_size(mail_path, min_size_bytes=0, max_depth=10, current_depth=0, skip_hidden=False)
        return {
            'type': 'mail',
            'path': mail_path,
            'size_bytes': size,
            'size_human': format_size(size),
            'count': count
        }
    except PermissionError as e:
        return _denied_result('mail', mail_path, e.strerror or str(e))
    except OSError as e:
        return {
            'type': 'mail',
            'path': mail_path,
            'size_bytes': None,
            'size_human': NOT_MEASURED,
            'count': None,
            'status': 'error',
            'error': str(e),
        }


# Time Machine is not a library here. Local Time Machine snapshots are what
# consume space on an APFS system, and scanners/snapshots.py reports them in
# their own section, ungraded, with honest copy about what can and cannot be
# measured. Backup drives are external volumes, which the volume scanner
# covers.


def scan_creative_libraries() -> Dict[str, Any]:
    """Scan creative app libraries (GarageBand, Logic Pro, Final Cut, etc.)."""
    home = os.path.expanduser('~')
    
    # Common creative app library locations
    creative_paths = [
        # GarageBand
        os.path.join(home, 'Library', 'Audio', 'Apple Loops'),
        os.path.join(home, 'Music', 'Audio Music Apps'),
        
        # Logic Pro
        os.path.join(home, 'Music', 'Audio Music Apps'),
        
        # Final Cut Pro
        os.path.join(home, 'Movies', 'Motion Templates'),
        os.path.join(home, 'Movies', 'Final Cut Events'),
        os.path.join(home, 'Movies', 'Final Cut Projects'),
        
        # Other creative apps
        os.path.join(home, 'Library', 'Application Support', 'Aperture'),
        os.path.join(home, 'Library', 'Application Support', 'Final Cut Pro'),
    ]
    
    libraries = []
    total_size = 0
    
    for lib_path in creative_paths:
        if os.path.exists(lib_path) and os.path.isdir(lib_path):
            try:
                size, _ = get_folder_size(lib_path, min_size_bytes=0, max_depth=5, current_depth=0)
                if size > 0:  # Only include if it has content
                    libraries.append({
                        'path': lib_path,
                        'name': os.path.basename(lib_path),
                        'size_bytes': size,
                        'size_human': format_size(size),
                        'type': 'creative'
                    })
                    total_size += size
            except (OSError, PermissionError):
                continue
    
    return {
        'type': 'creative',
        'libraries': libraries,
        'total_size_bytes': total_size,
        'total_size_human': format_size(total_size),
        'count': len(libraries)
    }


def scan_all_mac_libraries(timeout_seconds: float = 60) -> Dict[str, Any]:
    """
    Scan all Mac app libraries and return combined results.
    
    Args:
        timeout_seconds: Maximum time budget for the entire scan (default: 60s).
            Generous because a large Mail store takes a while, and a budget
            that runs out leaves the library grade computed from a subset.
    
    Returns:
        Dictionary with scan results, including 'scan_status' field ('complete', 'partial', or 'interrupted')
    """
    start_time = time.time()
    results = {}
    status = 'complete'
    interrupted_scans = []
    
    # List of scanner functions to run
    scanners = [
        ('photos', scan_photos_library),
        ('music', scan_music_library),
        ('messages', scan_messages),
        ('mail', scan_mail),
        ('creative', scan_creative_libraries),
    ]
    
    try:
        for scan_name, scan_func in scanners:
            # Check time budget before each scan
            elapsed = time.time() - start_time
            if elapsed >= timeout_seconds:
                status = 'partial'
                # Every library that has not run yet is skipped, not only the
                # one whose turn it was when the budget ran out. The Partial
                # Scan banner reads this list, so recording a single name
                # would under-report the gap.
                for remaining_name, _ in scanners:
                    if remaining_name not in results:
                        interrupted_scans.append(remaining_name)
                        results[remaining_name] = {
                            'type': remaining_name,
                            'status': 'skipped',
                            'reason': 'time-limited',
                            'total_size_bytes': 0,
                            'total_size_human': format_size(0),
                            'count': 0
                        }
                break
            
            try:
                result = scan_func()
                # A scanner that could not measure its library says so
                # ('denied', 'error', 'partial'); only fill in 'complete'
                # when it did not.
                result.setdefault('status', 'complete')
                results[scan_name] = result
            except KeyboardInterrupt:
                # User pressed Ctrl-C - re-raise to handle at top level
                raise
            except Exception as e:
                # Other errors - mark as failed but continue
                results[scan_name] = {
                    'type': scan_name,
                    'status': 'error',
                    'error': str(e),
                    'total_size_bytes': 0,
                    'total_size_human': format_size(0),
                    'count': 0
                }
    
    except KeyboardInterrupt:
        # Handle Ctrl-C at top level - return partial results gracefully
        status = 'interrupted'
        # Mark any remaining scans as skipped
        for scan_name, _ in scanners:
            if scan_name not in results:
                results[scan_name] = {
                    'type': scan_name,
                    'status': 'skipped',
                    'reason': 'scan-interrupted',
                    'total_size_bytes': 0,
                    'total_size_human': format_size(0),
                    'count': 0
                }
    
    # Total of what was measured: complete scans, plus the measured part of
    # a partial one. Unmeasured libraries carry None and add nothing.
    total_size = sum(
        (result.get('total_size_bytes', result.get('size_bytes')) or 0)
        for result in results.values()
        if result.get('status') in ('complete', 'partial')
    )
    
    results['total_size_bytes'] = total_size
    results['total_size_human'] = format_size(total_size)
    results['scan_status'] = status
    if interrupted_scans:
        results['interrupted_scans'] = interrupted_scans
    
    return results

