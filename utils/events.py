"""The machine interface: one JSON object per line on stdout.

`askdad --json` is how another program (the Mac app, an agent, a script)
runs a scan. In that mode stdout carries events and nothing else, so a reader
can parse every line. Everything a person would have read in the terminal
goes to stderr instead, except Dad's narration, which becomes `say` events.

The contract (commands, events, manifest fields, versioning) is written down
in docs/CONTRACT.md. Change that file with this one.
"""
import json
import sys

# Raised when a field is removed or changes meaning. Adding a field does not
# raise it: readers ignore keys they do not know.
SCHEMA_VERSION = 1

# Narrated lines start with this marker (see utils/narration.py and the
# scanners' "→ scanning..." lines). In JSON mode they are the `say` events.
NARRATION_MARK = '→'

_event_stream = None
_error_sent = False


def enabled():
    """True once enable() has run: stdout belongs to events."""
    return _event_stream is not None


def emit(event, **fields):
    """Write one event line. Does nothing outside JSON mode."""
    global _error_sent
    if _event_stream is None:
        return
    if event == 'error':
        _error_sent = True
    record = {'event': event}
    record.update(fields)
    _event_stream.write(json.dumps(record, ensure_ascii=False) + '\n')
    _event_stream.flush()


def error_sent():
    """True once an `error` event has gone out, so a caller further up does
    not add a vaguer one for the same failure."""
    return _error_sent


class _HumanStream:
    """Stands in for sys.stdout in JSON mode.

    Text is collected a line at a time. A narrated line becomes a `say`
    event; any other line goes to stderr, where a person debugging can still
    read it and a program can ignore it. A carriage return ends a line too,
    so a progress line that redraws itself is never glued to the next one.
    """

    def __init__(self, fallback):
        self._fallback = fallback
        self._buffer = ''

    def write(self, text):
        self._buffer += text.replace('\r', '\n')
        while '\n' in self._buffer:
            line, self._buffer = self._buffer.split('\n', 1)
            self._route(line)
        return len(text)

    def _route(self, line):
        stripped = line.strip()
        if not stripped:
            return
        if stripped.startswith(NARRATION_MARK):
            emit('say', text=stripped[len(NARRATION_MARK):].strip())
        else:
            self._fallback.write(line + '\n')

    def flush(self):
        self._fallback.flush()

    def close_line(self):
        """Send on whatever was printed without a final newline."""
        if self._buffer:
            pending, self._buffer = self._buffer, ''
            self._route(pending)

    def isatty(self):
        # Nobody is reading this as a terminal: no pauses, no prompts.
        return False


def enable():
    """Hand stdout to events and send human output elsewhere.

    Call once, before anything is printed. Safe to call twice.
    """
    global _event_stream
    if _event_stream is not None:
        return
    _event_stream = sys.stdout
    sys.stdout = _HumanStream(sys.stderr)


def disable():
    """Give stdout back. For tests, which enable JSON mode in-process."""
    global _event_stream, _error_sent
    if _event_stream is None:
        return
    _error_sent = False
    human = sys.stdout
    if isinstance(human, _HumanStream):
        human.close_line()
    sys.stdout = _event_stream
    _event_stream = None
