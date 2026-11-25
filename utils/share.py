"""`askdad share`: get the newest scan file ready to send to the Ask Dad team.

Ask Dad saves each scan's JSON file in `~/.dadware/reports`, a folder Finder
hides, so a beta tester cannot find it alone. This command finds the newest
one, says what is in it, and on a yes puts it on the clipboard as a file and
shows it in Finder. The tester pastes it into an email or a Messages chat,
or drags it there from Finder.

Nothing is uploaded. Ask Dad makes no network calls; the person sends the
file, with their own mail app, after reading what it holds.
"""

import glob
import os
import subprocess
import sys
from typing import Callable, Optional

# The scan files a share can send, in order of preference. A storage scan is
# what a bug report almost always needs, and after `askdad all` the CPU file
# is a few seconds newer, so storage is looked for first. HTML reports are not
# sent: the JSON holds the same facts and more, at a fraction of the size.
SCAN_FILE_PATTERNS = ('storage_*.json', 'cpu_*.json')

PRIVACY_NOTE = (
    "This file lists the names and sizes of the folders and files I found,\n"
    "such as \"Movies/Vacation.mov\". It does not hold what is inside any file.\n"
    "Send it only to someone you trust."
)

# A CPU scan holds each running program's full command line, which can name
# folders, files and accounts.
PRIVACY_NOTE_CPU = (
    "This file lists the programs that were running and how much memory each\n"
    "used, with the command that started each one. Those commands can include\n"
    "folder and file names. Send it only to someone you trust."
)

SHARE_PROMPT = "Get it ready to send? [y/N] "

# AppleScript that puts a file (not its path as text) on the clipboard, so a
# paste into Mail or Messages attaches it. The path arrives as an argument,
# so no quoting of the path is needed.
_CLIPBOARD_SCRIPT = [
    '-e', 'on run argv',
    '-e', 'set the clipboard to (POSIX file (item 1 of argv))',
    '-e', 'end run',
]


def newest_scan_file(reports_dir: str) -> Optional[str]:
    """The newest storage scan in `reports_dir`; the newest CPU scan when
    there is no storage scan; None when there is neither."""
    for pattern in SCAN_FILE_PATTERNS:
        candidates = glob.glob(os.path.join(reports_dir, pattern))
        if candidates:
            return max(candidates, key=os.path.getmtime)
    return None


def copy_file_to_clipboard(path: str) -> bool:
    """Put the file on the macOS clipboard as a file. True when it worked."""
    try:
        result = subprocess.run(['osascript', *_CLIPBOARD_SCRIPT, path],
                                capture_output=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def reveal_in_finder(path: str) -> bool:
    """Open a Finder window with the file selected. True when it worked."""
    try:
        result = subprocess.run(['open', '-R', path], capture_output=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def ask_yes(prompt: str, read: Callable[[str], str] = input) -> bool:
    """A [y/N] question. Default no; EOF and Ctrl+C are no."""
    try:
        answer = read(prompt)
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    return answer.strip().lower() in ('y', 'yes')


def run_share(reports_dir: str, read: Callable[[str], str] = input) -> int:
    """The `askdad share` command. Returns the exit status."""
    path = newest_scan_file(reports_dir)
    if path is None:
        print("→ I don't have a scan to send yet. Run askdad first, then askdad share.")
        return 1

    print(f"→ The scan to send is {os.path.basename(path)}.")
    print()
    is_cpu = os.path.basename(path).startswith('cpu_')
    print(PRIVACY_NOTE_CPU if is_cpu else PRIVACY_NOTE)
    print()
    if not ask_yes(SHARE_PROMPT, read):
        print("→ OK, nothing was copied.")
        return 0

    copied = copy_file_to_clipboard(path)
    shown = reveal_in_finder(path)

    if copied:
        print("→ Done. Open a new email or a Messages chat and press Cmd+V.")
        print("  The scan file attaches.")
    if shown:
        prefix = "  If nothing attaches, drag" if copied else "→ Drag"
        print(f"{prefix} the selected file from the Finder window into your message.")
    if not copied and not shown:
        print("→ I couldn't copy the file or show it in Finder. It is here:")
        print(f"  {path}")
        return 1
    sys.stdout.flush()
    return 0
