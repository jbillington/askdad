"""Grading system for storage report card."""

from typing import Any, Dict, List, Optional

from utils.formatters import format_size
from utils.path_utils import find_folder


def _field(obj: Any, key: str, default: Any = None) -> Any:
    """Read `key` from `obj`, whether `obj` is a plain dict (the shape
    askdad.py, personality/ and renderers/html.py call grading functions
    with) or one of the scanners.models dataclasses (the shape
    scanners.storage builds internally before converting to a dict on the
    way out). Lets grading functions accept either without callers
    caring which one they have.
    """
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _as_dict(obj: Any) -> Any:
    """Return a plain-dict view of `obj` if it exposes `to_dict()` (a
    scanners.models dataclass), otherwise return `obj` unchanged (already a
    dict, or something dict-like). Used where a helper we can't touch
    (utils.path_utils.find_folder) needs real dicts.
    """
    if isinstance(obj, dict):
        return obj
    to_dict = getattr(obj, 'to_dict', None)
    if callable(to_dict):
        return to_dict()
    return obj


def score_to_letter(score: float) -> str:
    """Convert numeric score (0-100) to letter grade."""
    if score >= 90:
        return 'A'
    elif score >= 80:
        return 'B'
    elif score >= 70:
        return 'C'
    elif score >= 60:
        return 'D'
    else:
        return 'F'


def grade_free_space(free_percent: float) -> Dict[str, Any]:
    """
    Grade based on free space percentage.

    These are the letter bands the score formula below actually produces
    once run through score_to_letter(). Verify with:
        grade_free_space(19) -> score 68.0, letter 'D'

    A: >=32.5% free
    B: 25-32.5% free
    C: 20-25% free
    D: 15-20% free
    F: <15% free
    """
    if free_percent >= 40:
        score = 100
    elif free_percent >= 25:
        score = 80 + (free_percent - 25) * (20 / 15)  # 80-100
    elif free_percent >= 15:
        score = 60 + (free_percent - 15) * 2  # 60-80
    elif free_percent >= 10:
        score = 40 + (free_percent - 10) * 4  # 40-60
    else:
        score = free_percent * 4  # 0-40
    
    return {
        'letter': score_to_letter(score),
        'score': max(0, min(100, score)),
        'max': 100
    }


def grade_home_folders_clutter(top_folders: List[Any]) -> Dict[str, Any]:
    """
    Grade home folders based on clutter in Downloads, Desktop, etc.

    Scores are a flat step function of problem_count, spaced so that every
    letter is reachable - each count lands inside its own score_to_letter()
    band rather than on a boundary.

        problem_count 0 -> 100 (A)   no problem folders, well organized
        problem_count 1 ->  85 (B)   some clutter but manageable
        problem_count 2 ->  72 (C)   multiple problem areas
        problem_count 3 ->  62 (D)   critical clutter issues
        problem_count 4+ ->  40 (F)

    problem_count accumulates, and both folders use the same two tiers:
    Downloads >10 GB adds 2, >5 GB adds 1; Desktop >10 GB adds 2, >5 GB adds
    1. The maximum is 4, which is what makes the F band reachable.

    This grade counts toward the composite score at 0.2 - see the weights in
    renderers/html.py.

    `top_folders` may be a list of plain dicts or scanners.models.FolderInfo
    objects - utils.path_utils.find_folder() only understands dicts, so
    entries are normalized before being handed to it.
    """
    downloads_size = 0
    desktop_size = 0
    problem_count = 0

    normalized_folders = [_as_dict(f) for f in top_folders]

    downloads_folder = find_folder(normalized_folders, 'Downloads')
    if downloads_folder is not None:
        downloads_size = downloads_folder.get('size_bytes', 0)
        if downloads_size > 10 * 1000**3:  # >10 GB
            problem_count += 2
        elif downloads_size > 5 * 1000**3:  # >5 GB
            problem_count += 1

    desktop_folder = find_folder(normalized_folders, 'Desktop')
    if desktop_folder is not None:
        desktop_size = desktop_folder.get('size_bytes', 0)
        # Two tiers, mirroring Downloads. With Desktop capped at one point,
        # problem_count could only reach 3, which would leave the F band
        # unreachable no matter how the scores were spaced.
        if desktop_size > 10 * 1000**3:  # >10 GB
            problem_count += 2
        elif desktop_size > 5 * 1000**3:  # >5 GB
            problem_count += 1
    
    # Score bands. These are spaced so every letter is actually reachable:
    # each score sits inside a letter band, not on its edge (60, for
    # example, would land in D and leave no count that earns a C), and
    # three and four problems get different letters.
    if problem_count == 0:
        score = 100   # A
    elif problem_count == 1:
        score = 85    # B
    elif problem_count == 2:
        score = 72    # C
    elif problem_count == 3:
        score = 62    # D
    else:
        score = 40    # F
    
    return {
        'letter': score_to_letter(score),
        'score': score,
        'max': 100,
        'downloads_size': downloads_size,
        'desktop_size': desktop_size,
        'problem_count': problem_count
    }


def grade_home_folders_ratio(home_folders_bytes: float, total_used_bytes: float) -> Dict[str, Any]:
    """
    Grade based on ratio of home folder usage to total used storage.
    
    Lower ratio (home folders are small relative to total) = better grade.

    Letter bands the score formula actually produces:

    A: <40% of used space is in home folders
    B: 40-50%
    C: 50-60%
    D: 60-70%
    F: >=70%
    """
    if total_used_bytes == 0:
        return {
            'letter': 'N/A',
            'score': 0,
            'max': 100
        }
    
    ratio_percent = (home_folders_bytes / total_used_bytes) * 100
    
    if ratio_percent < 30:
        score = 100
    elif ratio_percent < 50:
        score = 80 + (50 - ratio_percent) * 1  # 80-100
    elif ratio_percent < 70:
        score = 60 + (70 - ratio_percent) * 1  # 60-80
    elif ratio_percent < 85:
        score = 40 + (85 - ratio_percent) * 1.33  # 40-60
    else:
        score = max(0, 40 - (ratio_percent - 85) * 2.67)  # 0-40
    
    return {
        'letter': score_to_letter(score),
        'score': max(0, min(100, score)),
        'max': 100,
        'ratio_percent': ratio_percent
    }


def grade_library_size(library_size_bytes: float, library_type: str, total_used_bytes: float) -> Dict[str, Any]:
    """
    Grade individual Mac app library size.

    Different thresholds for different library types.
    Also considers library size relative to total used space.

    NOTE: the A/B/C/D values in the `thresholds` dict below are the
    interpolation points of the score curve, NOT the letter boundaries.
    Each zone spans 20 score points, which covers two letter bands, so the
    real cutoffs land on the midpoints:

        A: size <  (A+B)/2        B: (A+B)/2 .. B
        C: B .. (B+C)/2           D: (B+C)/2 .. C
        F: size >= C

    So for photos (A=50, B=100, C=200) an A runs to 75 GB and F starts at
    200 GB; the D=300 entry never acts as a letter boundary at all. The
    percent-of-used penalty applied afterwards shifts these down further.
    """
    # Decimal GB, matching format_size() and Finder, so a library is graded
    # against the same bucket its printed size implies (1024-based GB would
    # make every bucket about 7% larger than its label).
    library_size_gb = library_size_bytes / (1000**3)
    library_percent = (library_size_bytes / total_used_bytes * 100) if total_used_bytes > 0 else 0
    
    # Thresholds by library type (in GB)
    thresholds = {
        'photos': {'A': 50, 'B': 100, 'C': 200, 'D': 300},  # Photos can be large
        'music': {'A': 20, 'B': 50, 'C': 100, 'D': 200},
        'messages': {'A': 5, 'B': 10, 'C': 20, 'D': 50},
        'mail': {'A': 5, 'B': 10, 'C': 20, 'D': 50},
        'creative': {'A': 20, 'B': 50, 'C': 100, 'D': 200}
    }
    
    thresh = thresholds.get(library_type, thresholds['music'])
    
    # Grade based on absolute size
    if library_size_gb < thresh['A']:
        size_score = 100
    elif library_size_gb < thresh['B']:
        size_score = 80 + (thresh['B'] - library_size_gb) / (thresh['B'] - thresh['A']) * 20
    elif library_size_gb < thresh['C']:
        size_score = 60 + (thresh['C'] - library_size_gb) / (thresh['C'] - thresh['B']) * 20
    elif library_size_gb < thresh['D']:
        size_score = 40 + (thresh['D'] - library_size_gb) / (thresh['D'] - thresh['C']) * 20
    else:
        size_score = max(0, 40 - (library_size_gb - thresh['D']) / 10)
    
    # Penalize if library is a large percentage of total used space
    if library_percent > 50:
        size_score -= 20
    elif library_percent > 30:
        size_score -= 10
    elif library_percent > 20:
        size_score -= 5
    
    return {
        'letter': score_to_letter(size_score),
        'score': max(0, min(100, size_score)),
        'max': 100,
        'size_gb': library_size_gb,
        'percent_of_used': library_percent
    }


def calculate_storage_metrics(scan_data: Any) -> Dict[str, Any]:
    """
    Calculate key metrics for storage report card.

    Returns:
    - sum_top_10_folders: Sum of top 10 largest folders
    - sum_top_25_files: Sum of top 25 largest files
    - reclaimable_percent: Percentage of used space that could be freed by deleting top 25 files

    `scan_data` may be a plain dict (the shape askdad.py/personality/ and
    renderers/html.py always use, since scan_storage() returns a dict) or a
    scanners.models.StorageScan (the shape scan_storage() builds internally
    before converting to a dict). Its `top_folders`/`top_files` entries may
    likewise be dicts or FolderInfo/FileInfo objects - `_field()` reads
    either uniformly, so no conversion is needed either way.
    """
    top_folders = _field(scan_data, 'top_folders', []) or []
    top_files = _field(scan_data, 'top_files', []) or []
    volume_info = _field(scan_data, 'volume_info', {}) or {}
    used_bytes = _field(volume_info, 'used_bytes', 0)

    # Sum of top 10 folders
    top_10_folders = top_folders[:10]
    sum_top_10_folders = sum(_field(folder, 'size_bytes', 0) for folder in top_10_folders)

    # Sum of top 25 files
    top_25_files = top_files[:25]
    sum_top_25_files = sum(_field(file, 'size_bytes', 0) for file in top_25_files)

    # Reclaimable percentage
    reclaimable_percent = (sum_top_25_files / used_bytes * 100) if used_bytes > 0 else 0

    return {
        'sum_top_10_folders_bytes': sum_top_10_folders,
        'sum_top_10_folders_human': format_size(sum_top_10_folders),
        'sum_top_25_files_bytes': sum_top_25_files,
        'sum_top_25_files_human': format_size(sum_top_25_files),
        'reclaimable_percent': reclaimable_percent
    }


def calculate_composite_storage_grade(grades: Dict[str, Dict[str, Any]],
                                       weights: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
    """
    Calculate composite storage grade from individual component grades.

    Args:
        grades: Dict of grade components with 'score' key
        weights: Dict of weights for each component (default: equal weighting)

    Returns:
        Composite grade with letter and score
    """
    if weights is None:
        # Default equal weighting
        weights = {key: 1.0 for key in grades.keys()}
        total_weight = sum(weights.values())
        weights = {k: v / total_weight for k, v in weights.items()}
    
    weighted_score = sum(
        grades[key].get('score', 0) * weights.get(key, 0)
        for key in grades.keys()
    )
    
    return {
        'letter': score_to_letter(weighted_score),
        'score': weighted_score,
        'max': 100
    }



# The libraries the report card lists, in the order it lists them.
LIBRARY_NAMES = {
    'photos': 'Photos',
    'music': 'Music',
    'messages': 'Messages',
    'mail': 'Mail',
    'creative': 'Creative Apps',
}

# The folders the clutter grade looks at.
CLUTTER_FOLDERS = ('Downloads', 'Desktop')

# Each component's share of the overall grade before renormalizing.
COMPONENT_WEIGHTS = {
    'free_space': 0.5,
    'home_folders_ratio': 0.15,
    'home_folders_clutter': 0.2,
    'mac_libraries': 0.15,
}


def overall_comment(score: float) -> str:
    """The few words beside the overall letter."""
    if score >= 90:
        return "Excellent!"
    if score >= 80:
        return "Good job!"
    if score >= 70:
        return "Room for improvement"
    if score >= 60:
        return "Needs work"
    return "Critical issues"


def grade_storage_report(scan_data: Dict[str, Any]) -> Dict[str, Any]:
    """Every grade on the storage report card, from one scan.

    The one place the letters are worked out. The HTML report draws them and
    the JSON manifest carries them, so the two cannot disagree.

    Returns a dict with:
        overall: {'letter', 'score', 'max', 'comment'}
        components: one entry per component that counted, each the component's
            grade plus 'weight' (the weights add up to 1). 'mac_libraries' is
            present only when the libraries were scored.
        libraries: one entry per library worth a row, keyed by type, each
            {'name', 'letter', 'score', 'size_bytes', 'size_human', 'status',
            'reason', 'graded'}. 'letter' is '-' when the library has no grade.
            'status' is the scanner's own word for the library, with 'denied'
            for one macOS would not let the scan read.
        clutter_scored: whether the clutter grade counted toward the overall.
            False when macOS blocked Downloads or Desktop.
        clutter_blocked_folders: the folders of the two it blocked.
        libraries_scored: whether the libraries counted toward the overall.
        libraries_not_scored_reason: None, 'needs_full_disk_access',
            'incomplete' or 'not_scanned'.
    """
    volume_info = scan_data.get('volume_info') or {}
    used_bytes = volume_info.get('used_bytes', 0)
    free_percent = volume_info.get('free_percent', 0)

    free_space_grade = grade_free_space(free_percent)
    home_folders_total = scan_data.get('home_folders_total_bytes', 0)
    home_folders_ratio_grade = grade_home_folders_ratio(home_folders_total, used_bytes)

    # Grade home folders clutter separately (Downloads, Desktop, etc.)
    top_folders = scan_data.get('top_folders', [])
    home_folders_clutter_grade = grade_home_folders_clutter(top_folders)
    # A folder macOS would not let the scan open looks empty, and an empty
    # Downloads earns an A. So when Downloads or Desktop was blocked the
    # clutter grade is not scored, the same rule as a blocked library.
    folder_access = (scan_data.get('permission_status') or {}).get('folders') or {}
    clutter_blocked = [name for name in CLUTTER_FOLDERS
                       if (folder_access.get(name) or {}).get('status') == 'denied']
    clutter_scored = not clutter_blocked

    # Grade Mac libraries
    mac_libraries = scan_data.get('mac_libraries', {})
    missing_permissions = set(
        (scan_data.get('permission_status') or {}).get('missing_permissions') or []
    )
    libraries: Dict[str, Dict[str, Any]] = {}
    library_scores = []

    for lib_type, lib_name in LIBRARY_NAMES.items():
        lib_data = mac_libraries.get(lib_type, {})
        lib_status = lib_data.get('status', 'complete')

        # An unmeasured library carries None, not 0 (scanners/mac_libraries.py).
        if lib_type in ['photos', 'music', 'creative']:
            lib_size = lib_data.get('total_size_bytes') or 0
        else:
            lib_size = lib_data.get('size_bytes') or 0

        # Show library if it has size, if it was skipped/interrupted, or if
        # it came back empty only because we lack permission to read it -
        # an invisible zero would make the grade look complete.
        # Only when a library scan actually ran. With --no-mac-libraries
        # there is nothing to be blocked from, and "needs Full Disk Access"
        # would be the wrong explanation for a section the user turned off.
        blocked = bool(mac_libraries) and (
            lib_status == 'denied' or lib_type in missing_permissions)
        if not (lib_size > 0 or lib_status != 'complete' or blocked):
            continue

        graded = lib_size > 0 and lib_type != 'messages'
        if graded:
            grade = grade_library_size(lib_size, lib_type, used_bytes)
            library_scores.append(grade['score'])
        else:
            # Messages is the user's own history: a big one is not a problem
            # to fix, and an F for it reads as scolding. Show the size, leave
            # it out of the grade. A skipped or interrupted library has
            # nothing to grade.
            grade = {'letter': '-', 'score': 0}

        libraries[lib_type] = {
            'name': lib_name,
            'letter': grade['letter'],
            'score': grade['score'],
            'size_bytes': lib_size if lib_size > 0 else 0,
            'size_human': format_size(lib_size) if lib_size > 0 else '',
            'status': lib_status,
            'reason': lib_data.get('reason', ''),
            'graded': graded,
        }

    # Average library grade (only from completed scans with size > 0)
    avg_library_score = sum(library_scores) / len(library_scores) if library_scores else 0

    # A library that never ran is left out of the average above rather than
    # averaged in as a zero, so a truncated scan does not drag the score
    # down - it quietly shrinks the evidence behind it. Scoring that subset
    # as though every library had been measured would overstate it, so an
    # incomplete library scan drops the component and lets the weights
    # renormalize: the composite reflects only what the scan actually saw.
    libraries_incomplete = any(
        info.get('status') not in ('complete', None)
        for info in libraries.values()
    )

    # A library blocked by Full Disk Access reports status 'denied' with
    # no size. Older manifests (before Nov 22, 2026) saved it as
    # 'complete' with zero bytes instead, so that case is still matched
    # against permission_status. Either way the reader is told the
    # library needs Full Disk Access, rather than seeing one library's
    # grade presented as though it covered them all.
    #
    # Only libraries that measured nothing because they were refused. One
    # that reported 'error' or 'skipped' is telling the truth about itself
    # and keeps its own status.
    blocked_and_empty = {
        lib_type for lib_type, info in libraries.items()
        if info['size_bytes'] == 0
        and (info.get('status') == 'denied'
             or (info.get('status') == 'complete' and lib_type in missing_permissions))
    }
    if blocked_and_empty:
        libraries_incomplete = True
        for lib_type in blocked_and_empty:
            libraries[lib_type]['status'] = 'denied'
            libraries[lib_type]['reason'] = 'needs Full Disk Access'

    libraries_scored = bool(library_scores) and not libraries_incomplete
    if libraries_scored:
        not_scored_reason = None
    elif blocked_and_empty:
        not_scored_reason = 'needs_full_disk_access'
    elif libraries:
        not_scored_reason = 'incomplete'
    else:
        not_scored_reason = 'not_scanned'

    # Home folders clutter counts toward the composite, so an F on
    # Downloads and Desktop moves the big letter at the top. It is the one
    # component measuring something a reader can act on in ten minutes,
    # which is the whole promise of the report.
    component_grades = {
        'free_space': free_space_grade,
        'home_folders_ratio': home_folders_ratio_grade,
    }
    if clutter_scored:
        component_grades['home_folders_clutter'] = home_folders_clutter_grade
    if libraries_scored:
        component_grades['mac_libraries'] = {
            'letter': score_to_letter(avg_library_score),
            'score': avg_library_score,
        }
    # Renormalize to 1.0. Without this, dropping a component silently
    # subtracts its weight from the top-line score instead of
    # redistributing it, so --no-mac-libraries, a flag that only means
    # "don't look here", would cost points.
    weights = {key: COMPONENT_WEIGHTS[key] for key in component_grades}
    total_weight = sum(weights.values())
    weights = {k: v / total_weight for k, v in weights.items()}
    composite_grade = calculate_composite_storage_grade(component_grades, weights)

    overall = dict(composite_grade)
    overall['comment'] = overall_comment(composite_grade['score'])
    components = {key: dict(grade, weight=weights[key])
                  for key, grade in component_grades.items()}

    return {
        'overall': overall,
        'components': components,
        'libraries': libraries,
        'libraries_scored': libraries_scored,
        'libraries_not_scored_reason': not_scored_reason,
        'clutter_scored': clutter_scored,
        'clutter_blocked_folders': clutter_blocked,
    }
