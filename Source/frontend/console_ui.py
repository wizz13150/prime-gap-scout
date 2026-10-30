"""Small, dependency-free terminal dashboard.  This module never runs a worker.

Dashboard.update() accepts measured state; rate is positions/second, position is
a completed count, and end is the exclusive range endpoint.  No GPU API is used.
"""

from __future__ import annotations

import atexit
import csv
import heapq
import io
import math
import os
import shutil
import sys
import time
from decimal import Decimal, localcontext

try:
    from pgn_dashboard import render as _released_rc7_projection, RichConsole
except ImportError:
    _released_rc7_projection = None


def _text(value):
    value = str(value if value is not None else "--")
    value = value.replace("\u2026", "...").replace("\u2014", "-").replace("\u2013", "-")
    return "".join(c if 32 <= ord(c) < 127 else " " for c in value)


def _cut(value, width, tail=False):
    text = _text(value)
    if len(text) <= width:
        return text
    if width <= 3:
        return text[: max(0, width)]
    return "..." + text[-width + 3 :] if tail else text[: width - 3] + "..."


def _integer(value, default=None):
    try:
        if isinstance(value, bool):
            return default
        return int(value)
    except (ValueError, TypeError, OverflowError):
        return default


def _number(value, default=None):
    try:
        value = float(value)
        return value if math.isfinite(value) else default
    except (ValueError, TypeError, OverflowError):
        return default


def _scientific(value):
    if value is None:
        return "--"
    with localcontext() as context:
        context.prec = max(32, len(str(abs(value))) + 2)
        mantissa, exponent = format(Decimal(value), ".5e").split("e")
    return mantissa + "e" + str(int(exponent))


def _duration(seconds):
    value = _number(seconds)
    if value is None or value < 0:
        return "--:--:--"
    seconds = int(value)
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    clock = f"{hours:02}:{minutes:02}:{seconds:02}"
    return f"{days}d {clock}" if days else clock


def _rate(value):
    if value is None or value < 0:
        return "-- Gpos/s"
    return f"{value / 1e9:,.0f} Gpos/s"


def _merit(value, width=8):
    value = _number(value)
    if value is None:
        return "--"
    fixed = f"{value:.4f}"
    return fixed if len(fixed) <= width else f"{value:.2e}"


def _raw_gpu(state):
    """The existing runner emits name,uuid,memory.total,driver_version CSV."""
    raw = state.get("rawgpuinfoCSV", state.get("rawgpuinfo_csv", state.get("gpu_info", "")))
    if not raw:
        return {}
    try:
        row = next(csv.reader(io.StringIO(str(raw))))
        if len(row) != 4:
            return {}
        return {
            "gpu_name": row[0].strip(),
            "vram_mib": _integer(row[2].strip()),
            "driver": row[3].strip(),
        }
    except (csv.Error, StopIteration):
        return {}


class Dashboard:
    """Fixed-position ANSI dashboard, with plain snapshots for redirected output.

    ``writer`` may be a text stream or a callable taking one string.  A custom
    callable is a plain-text sink.  Refresh is limited to five frames per second;
    force=True and finish() can immediately publish a final state.
    """

    def __init__(self, writer=None):
        self._stream = sys.stdout if writer is None else writer
        self._write_fn = self._stream if callable(self._stream) else self._stream.write
        self._state = {}
        self._previous = []
        self._painted = False
        self._last_paint = -math.inf
        self._size = None
        self._closed = False
        self._console_mode = None
        self._rate_samples = []
        self._rate_window_matured = False
        stream_name = str(getattr(self._stream, "name", "")).upper()
        visible_console = (
            stream_name.endswith("CONOUT$") or os.environ.get("PGN_VISIBLE_CONSOLE") == "1"
        )
        self._tty = bool(getattr(self._stream, "isatty", lambda: False)()) or visible_console
        if os.name == "nt":
            self._ansi = self._tty and self._windows_vt()
        else:
            self._ansi = self._tty and (visible_console or os.environ.get("TERM", "") != "dumb")
        self._color = self._ansi and "NO_COLOR" not in os.environ
        atexit.register(self.finish)

    def _windows_vt(self):
        try:
            import ctypes
            import msvcrt

            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel.GetConsoleMode.argtypes = (ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint))
            kernel.GetConsoleMode.restype = ctypes.c_int
            kernel.SetConsoleMode.argtypes = (ctypes.c_void_p, ctypes.c_uint)
            kernel.SetConsoleMode.restype = ctypes.c_int
            handle = msvcrt.get_osfhandle(self._stream.fileno())
            mode = ctypes.c_uint()
            if not kernel.GetConsoleMode(handle, ctypes.byref(mode)):
                return False
            if not kernel.SetConsoleMode(handle, mode.value | 0x0004):
                return False
            self._console_mode = (kernel, handle, mode.value)
            return True
        except (OSError, ValueError, AttributeError, ImportError):
            return False

    def _dimensions(self):
        from pgn_terminal_input import terminal_size

        size = terminal_size(stream=self._stream, fallback=(110, 30))
        # Interactive output owns no-wrap and uses explicit row positioning.
        return max(1, size.columns), max(1, size.lines)

    def _write(self, value):
        encoding = getattr(self._stream, "encoding", None)
        if encoding:
            try:
                value.encode(encoding)
            except (UnicodeEncodeError, LookupError):
                # Redirected legacy Windows streams can be cp1252. Preserve
                # all numeric values and ANSI controls, replace presentation
                # glyphs only; a dashboard must never crash the search.
                replacements = {ord(c): "+" for c in "╭╮╰╯┌┐└┘├┤┬┴┼"}
                replacements.update({ord(c): "-" for c in "─━–—"})
                replacements.update({ord("│"): "|", ord("≥"): ">=", ord("…"): "...", ord("·"): "/"})
                value = value.translate(replacements).encode("ascii", "replace").decode("ascii")
        self._write_fn(value)
        flush = getattr(self._stream, "flush", None)
        if flush:
            flush()

    @staticmethod
    def _table(width, title, records):
        # H10 lower primes have 21 digits.  Keep those integers intact.
        gap_width = max(7, max((len(str(r[0])) for r in records), default=0))
        merit_width = 8
        lower_width = width - gap_width - merit_width - 6
        top = "+- " + title + " " + "-" * max(0, width - len(title) - 5) + "+"
        heading = (
            f"| {'GAP':>{gap_width}} {'MERIT':>{merit_width}} {'LOWER_PRIME':<{lower_width}} |"
        )
        lines = [(top, "cyan"), (heading, "cyan")]
        for index in range(5):
            if index < len(records):
                gap, merit, lower = records[index]
                gap_text = str(gap)
                # Gap/prime values are never shortened; valid H10 values fit.
                row = f"| {gap_text:>{gap_width}} {_merit(merit):>{merit_width}} {str(lower):<{lower_width}} |"
                lines.append((row, "green"))
            else:
                lines.append(("| " + " " * (width - 4) + " |", "dim"))
        lines.append(("+" + "-" * (width - 2) + "+", "dim"))
        return lines

    def _render(self, width, height):
        state = dict(_raw_gpu(self._state))
        state.update({k: v for k, v in self._state.items() if v is not None})
        start = _integer(state.get("start"))
        end = _integer(state.get("end"))
        completed = max(0, _integer(state.get("position"), 0))
        elapsed = max(0.0, _number(state.get("elapsed"), 0.0))
        tests = _integer(state.get("tests"), 0)
        total = end - start if start is not None and end is not None else 0
        current = start + completed if start is not None else None
        measured_rate = _number(state.get("rate"))
        if measured_rate is None and elapsed > 0:
            measured_rate = completed / elapsed
        fraction = min(1.0, max(0.0, completed / total)) if total > 0 else 0.0
        eta = (
            max(0, total - completed) / measured_rate
            if measured_rate and measured_rate > 0 and total > 0
            else None
        )
        if total > 0 and completed >= total:
            eta = 0
        records = []
        for record in state.get("gaps", ()) or ():
            try:
                gap, merit, lower = record
            except (ValueError, TypeError):
                continue
            gap, lower = _integer(gap), _integer(lower)
            if gap is not None and lower is not None:
                records.append((gap, merit, lower))
        best = heapq.nsmallest(5, records, key=lambda r: (-r[0], r[2]))
        latest = list(reversed(records[-5:]))
        name = state.get("gpu_name", "Waiting for GPU...")
        index = _text(state.get("gpu_index", 0))
        memory = _integer(state.get("vram_mib"))
        memory_text = f"{memory:,} MiB" if memory is not None else "-- MiB"
        status = _text(state.get("status", "READY"))
        rate_text = _rate(measured_rate)
        count_text = f"{len(records):,}"
        first, last = str(start) if start is not None else "--", (
            str(end) if end is not None else "--"
        )
        exact_current = str(current) if current is not None else "--"
        minimum_panel = max(7, max((len(str(r[0])) for r in best + latest), default=0)) + 8 + 21 + 6
        small = width < 90 or width < minimum_panel * 2 + 2
        required_height = 25 if small else 23
        if self._tty and (width < 54 or height < required_height):
            return [
                (_cut("PGN 68 | PRIME GAP SEARCH", width), "cyan"),
                (_cut(f"Resize: 55+ columns, {required_height}+ rows", width), "yellow"),
                (_cut(f"Status {status} | {rate_text} | gaps {count_text}", width), "yellow"),
                (_cut(f"Current {exact_current}", width), "plain"),
            ][:height]
        lines = [
            ("PGN 68  |  PRIME GAP SEARCH" + ("  |  Ctrl+C to stop" if not small else ""), "cyan")
        ]
        if small:
            lines.append((f"GPU {index}  {_cut(name, max(12, width - 9))}", "plain"))
            lines.append(
                (
                    _cut(f"{memory_text} | {status} | {rate_text} | gaps {count_text}", width),
                    "yellow",
                )
            )
        else:
            columns = (3, width - 71, 11, 12, 15, 11)
            border = "+" + "+".join("-" * (n + 2) for n in columns) + "+"

            def device_row(values):
                return (
                    "|"
                    + "|".join(" " + _cut(v, n).ljust(n) + " " for v, n in zip(values, columns))
                    + "|"
                )

            lines.extend(
                [
                    (border, "dim"),
                    (device_row(("GPU", "MODEL", "MEM", "STATUS", "RATE", "GAPCOUNT")), "cyan"),
                    (
                        device_row((index, name, memory_text, status, rate_text, count_text)),
                        "yellow",
                    ),
                    (border, "dim"),
                ]
            )
        lines.append((f"Range  {first} -> {last}  |  Run size {total} positions", "plain"))
        minimum_gap = state.get("effective_gap_min", state.get("min_gap"))
        minimum_gap = "—" if minimum_gap is None else str(minimum_gap)
        lines.append(
            (f"       {_scientific(start)} -> {_scientific(end)}  |  minimum gap {minimum_gap}", "dim")
        )
        lines.append((f"Current {exact_current}  ({_scientific(current)})", "plain"))
        if small:
            lines.append((f"Elapsed {_duration(elapsed)} | ETA {_duration(eta)}", "plain"))
        else:
            lines.append(
                (
                    f"Elapsed {_duration(elapsed):<14} ETA {_duration(eta):<14} Progress {fraction * 100:6.2f}%",
                    "plain",
                )
            )
        bar_width = max(12, min(64, width - 13))
        filled = int(fraction * bar_width)
        lines.append(
            ("[" + "#" * filled + "-" * (bar_width - filled) + f"] {fraction * 100:6.2f}%", "cyan")
        )
        if small:
            lines.append((f"PRP tests {tests:,} | Gaps {count_text}", "plain"))
        else:
            lines.append(
                (
                    f"PRP tests {tests:,} | Completed {_scientific(completed)} / {_scientific(total)}",
                    "plain",
                )
            )
        if small:
            for title, group in (
                ("BEST 5 - largest gaps", best),
                ("LAST 5 - newest first", latest),
            ):
                table = self._table(width, title, group)
                # Compact form uses the next panel title as its closing edge.
                lines.extend(table[:-1])
        else:
            left_width = (width - 2) // 2
            right_width = width - left_width - 2
            left = self._table(left_width, "BEST 5 - largest gaps", best)
            right = self._table(right_width, "LAST 5 - newest first", latest)
            for (a, ac), (b, bc) in zip(left, right):
                lines.append((a + "  " + b, "green" if ac == "green" or bc == "green" else ac))
        driver = _text(state.get("driver", "--"))
        host = _text(state.get("host", "local"))
        lines.append(
            (_cut(f"Driver {driver} | Host {host} | Local search - no PGN network", width), "dim")
        )
        lines.append(
            ("Output " + _cut(state.get("outputfile", "--"), max(1, width - 7), tail=True), "dim")
        )
        lines.append((_cut(state.get("key_help", "P pause/resume | Ctrl+C stop"), width), "cyan"))
        return lines

    def update(self, state: dict, force=False):
        if self._closed:
            return
        self._state.update(state)
        elapsed = _number(self._state.get("elapsed"))
        completed = _integer(self._state.get("position"))
        tests = _integer(self._state.get("tests"), 0)
        if elapsed is not None and completed is not None:
            sample = (elapsed, completed, tests)
            if self._rate_samples:
                previous = self._rate_samples[-1]
                if elapsed <= 0 or completed < previous[1] or tests < previous[2]:
                    self._rate_samples = []
                    self._rate_window_matured = False
                elif elapsed < previous[0]:
                    # The final measured worker wall can correct a provisional
                    # timestamp backwards without starting a new calculation.
                    # Replace only the invalid suffix, preserving the observed
                    # history and the actual (unclamped) final time/counters.
                    while self._rate_samples and self._rate_samples[-1][0] > elapsed:
                        self._rate_samples.pop()
                    if not self._rate_samples:
                        self._rate_window_matured = False
            if not self._rate_samples or elapsed > self._rate_samples[-1][0]:
                self._rate_samples.append(sample)
            elif elapsed == self._rate_samples[-1][0]:
                self._rate_samples[-1] = sample
            if self._rate_samples and elapsed - self._rate_samples[0][0] >= 60:
                self._rate_window_matured = True
            # The displayed window remains 60 seconds. Keep a second minute
            # of real samples so a late final-time correction can move its
            # cutoff backwards without losing the interpolation bracket.
            while len(self._rate_samples) > 2 and self._rate_samples[1][0] <= elapsed - 120:
                self._rate_samples.pop(0)
        now = time.monotonic()
        from pgn_terminal_input import get_hover_region, get_hit_map

        hover = get_hover_region()
        hover_changed = hover != getattr(self, "_last_hover", None)
        geometry = get_hit_map().viewport
        geometry_invalid = geometry.width == 0 or geometry.height == 0
        if (
            not force
            and not hover_changed
            and not geometry_invalid
            and now - self._last_paint < 0.2
        ):
            return
        self._last_hover = hover
        self._last_paint = now
        size = self._dimensions()
        if _released_rc7_projection is not None:
            data = dict(_raw_gpu(self._state))
            data.update({key: value for key, value in self._state.items() if value is not None})
            data["_ui_rate_samples"] = tuple(self._rate_samples)
            data["_ui_rate_window_matured"] = self._rate_window_matured
            buffer = io.StringIO()
            console = RichConsole(
                file=buffer,
                width=size[0],
                height=max(1, size[1]),
                force_terminal=self._ansi,
                color_system="truecolor" if self._color else None,
                legacy_windows=False,
                safe_box=False,
                highlight=False,
                markup=False,
            )
            projection = _released_rc7_projection(data, size[0], max(1, size[1]))
            console.print(projection)
            self._frame_hit_regions = getattr(projection, "pgn_hit_regions", [])
            frame = [(line, "plain") for line in buffer.getvalue().splitlines()[: max(1, size[1])]]
        else:
            frame = self._render(*size)
        if self._ansi:
            changed_size = size != self._size
            output = ["\x1b[?25l\x1b[2J\x1b[H"] if not self._painted or changed_size else []
            colors = {
                "cyan": "\x1b[96m",
                "green": "\x1b[92m",
                "yellow": "\x1b[93m",
                "dim": "\x1b[2m",
                "plain": "",
            }
            for row in range(max(len(frame), len(self._previous))):
                line = frame[row] if row < len(frame) else ("", "plain")
                if (
                    changed_size
                    or not self._painted
                    or row >= len(self._previous)
                    or line != self._previous[row]
                ):
                    text, color = line
                    # With no-wrap, the cursor stays on the final painted cell.
                    # Clear BEFORE painting so EL cannot erase the right border.
                    output.append(
                        f"\x1b[{row + 1};1H\x1b[2K"
                        + (colors.get(color, "") if self._color else "")
                        + text
                        + "\x1b[0m"
                    )
            if output:
                self._write("".join(output))
        elif force or frame != self._previous:
            # A pipe/file has no cursor.  Keep snapshots readable, without ANSI.
            self._write("\n".join(text for text, _ in frame) + "\n")
        if self._tty:
            try:
                from pgn_terminal_input import HitMap, HitRegion, Rect, set_hit_map

                regions = [
                    HitRegion(
                        Rect(r["x"], r["y"], r["width"], r["height"]),
                        r["target"],
                        key=r["key"],
                        disabled=bool(r.get("disabled")),
                        index=r.get("index"),
                        scrollable=bool(r.get("scrollable")),
                    )
                    for r in getattr(self, "_frame_hit_regions", [])
                ]
                set_hit_map(HitMap(size[0], size[1], regions))
            except ImportError:
                pass
        self._previous, self._size, self._painted = frame, size, True

    def finish(self):
        if self._closed:
            return
        try:
            if self._state:
                self.update({}, force=True)
            if self._ansi and self._painted:
                row = min(len(self._previous), self._size[1])
                suffix = "" if row >= self._size[1] else "\n"
                self._write(f"\x1b[{max(1, row)};1H\x1b[0m\x1b[?25h" + suffix)
        except (OSError, ValueError):
            pass  # An already-closed output stream must not prevent restoration.
        finally:
            if self._console_mode:
                kernel, handle, mode = self._console_mode
                kernel.SetConsoleMode(handle, mode)
                self._console_mode = None
            self._closed = True
            atexit.unregister(self.finish)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.finish()
