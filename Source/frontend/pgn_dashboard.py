"""Mining dashboard projection of measured search and session data.

Source: Horizon-Development/runtime/cli/riecoin-cpu/dashboard.py,
SHA256 87DF619F014A134E864CE85881E8479C9BB712B08126BE7AC594BCDF5E2408CA.
The four pure rendering helpers below are copied verbatim. The same Rich
Panel/Table/Layout composition is projected onto measured prime-gap data.
The CPU terminal-key backend, wallet, shares and network model are not imported.
"""

import math
from decimal import Decimal, localcontext, ROUND_CEILING

from rich import box
from rich.align import Align
from rich.console import Console as RichConsole, Group
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

MUTED = "bright_black"


def safe(value):
    return "".join(c for c in str(value) if c.isprintable())[:240]


def number(value):
    return "—" if value is None else "{:,.0f}".format(value)


def compact_number(value):
    if value is None:
        return "—"
    scaled = value
    unit = 0
    suffixes = ("", "k", "M", "G", "T", "P", "E")
    while scaled >= 999.5 and unit < len(suffixes) - 1:
        scaled /= 1000
        unit += 1
    if not unit:
        return str(value)
    digits = 2 if scaled < 10 else 1 if scaled < 100 else 0
    return (
        ("{:,.%df}" % digits).format(scaled).rstrip("0").rstrip(".") + suffixes[unit]
        if digits
        else "{:,.0f}".format(scaled) + suffixes[unit]
    )


def metric(title, value, detail, height=5):
    body = Text(value, style="bold cyan", justify="center")
    if detail:
        rows = [body, Text(detail, style=MUTED, justify="center")]
        if height >= 5:
            rows.insert(0, Text(""))
        body = Group(*rows)
    return Panel(
        Align.center(body, vertical="middle", height=height - 2),
        height=height,
        title=Text(title, style="bold white"),
        title_align="center",
        border_style=MUTED,
        box=box.ROUNDED,
        padding=(0, 1),
    )


def _num(value, default=None):
    try:
        f = float(value)
        return f if math.isfinite(f) else default
    except (TypeError, ValueError, OverflowError):
        return default


def _int(value, default=None):
    try:
        return int(value) if not isinstance(value, bool) else default
    except (TypeError, ValueError, OverflowError):
        return default


def _duration(value):
    n = _num(value)
    if n is None or n < 0:
        return "—"
    days, n = divmod(int(n), 86400)
    hours, n = divmod(n, 3600)
    minutes, seconds = divmod(n, 60)
    result = f"{hours:02}:{minutes:02}:{seconds:02}"
    return f"{days}d {result}" if days else result


def _science(value, precision=8):
    if value is None:
        return "—"
    with localcontext() as ctx:
        ctx.prec = max(32, len(str(abs(value))) + 2)
        a, b = format(Decimal(value), f".{precision}e").split("e")
    return a + "e" + str(int(b))


def _speed(value):
    return "— Gpos/s" if value is None else f"{value/1e9:,.0f} Gpos/s"


def rolling_average(samples, matured=False):
    """Observed-counter rate; mature windows use bracketing interpolation.

    Interpolation estimates the count at the cutoff from two real samples.
    It never modifies worker times or completion counters.
    """
    if len(samples) < 2:
        return None, 0.0, False
    first, last = samples[0], samples[-1]
    observed = max(0.0, last[0] - first[0])
    mature = bool(matured or observed >= 60)
    if mature:
        cutoff = last[0] - 60
        for left, right in zip(samples, samples[1:]):
            if left[0] <= cutoff <= right[0] and right[0] > left[0]:
                # Subtract integer counters before converting to floating
                # point, preserving large cumulative-count precision.
                between = (right[1] - left[1]) * (cutoff - left[0]) / (right[0] - left[0])
                return ((last[1] - left[1]) - between) / 60.0, 60.0, True
        # An attached viewer may not yet possess a complete bracket. Do not
        # invent a rate; retain the mature label while collecting samples.
        return None, 60.0, True
    return ((last[1] - first[1]) / observed if observed > 0 else None), observed, False


def target_gap_label(start, end, target):
    """Display goal only: smallest even gap meeting merit at each range end."""

    def threshold(n):
        if n is None or n <= 1:
            return None
        with localcontext() as ctx:
            ctx.prec = 50
            half_gap = Decimal(str(target)) * Decimal(n).ln() / Decimal(2)
            return 2 * int(half_gap.to_integral_value(rounding=ROUND_CEILING))

    lo = threshold(start)
    hi = threshold(end - 1 if end is not None and start is not None and end > start else start)
    prefix = f"Target merit {target:g} | "
    if lo is None or hi is None:
        return prefix + "gap —"
    if lo == hi:
        return prefix + f"gap >= {lo}"
    return prefix + f"target gap {lo}–{hi}"


def merit_style(merit, target=32.0):
    """Color the actual unrounded merit; a target is never a found result."""
    if merit is None:
        return MUTED
    if merit >= target:
        return "bold #ffd700"
    if merit >= target - 1:
        return "bold #c0c0c0"
    if merit >= target - 2:
        return "bold #cd7f32"
    if merit >= target - 3:
        return "bold bright_red"
    return "green"


def _gap_table(rows, limit=10, compact=False, target=32.0, recent=False, best_lowers=None):
    table = Table(
        box=None if compact else box.SIMPLE,
        expand=True,
        header_style="bold cyan",
        border_style=MUTED,
        padding=(0, 1),
        show_edge=False,
    )
    table.add_column("GAP", justify="right", min_width=5, no_wrap=True)
    table.add_column("MERIT", justify="right", min_width=7, no_wrap=True)
    table.add_column("LOWER_PRIME", min_width=21, ratio=2, no_wrap=True)
    for index in range(limit):
        if index < len(rows):
            gap, merit, lower = rows[index]
            base_style = (
                ("green" if lower in (best_lowers or ()) else "white") if recent else "green"
            )
            medal = merit is not None and merit >= target - 3
            row_style = merit_style(merit, target) if medal else base_style
            merit_color = row_style
            table.add_row(
                Text(str(gap), style=row_style),
                Text("—" if merit is None else f"{merit:.4f}", style=merit_color),
                Text(str(lower), style=row_style),
                style=row_style,
            )
        else:
            table.add_row("—", "—", "—", style=MUTED)
    return table


def render(state, width=110, height=30):
    """Pure Rich composition, using only current frontend measurements."""
    from pgn_ui_views import sci

    start, end = _int(state.get("start")), _int(state.get("end"))
    completed = max(0, _int(state.get("position"), 0))
    tests = max(0, _int(state.get("tests"), 0))
    elapsed = max(0.0, _num(state.get("elapsed"), 0.0))
    paused = max(0.0, _num(state.get("paused_seconds"), 0.0))
    total = max(0, end - start) if start is not None and end is not None else 0
    current = start + completed if start is not None else None
    rate = _num(state.get("speed_rate")) if "speed_rate" in state else _num(state.get("rate"))
    proportion = min(1.0, max(0.0, completed / total)) if total else 0.0
    from pgn_compute_eta import forecast_seconds
    eta = forecast_seconds(state)
    status = safe(state.get("status", "READY"))
    color = (
        "green"
        if status in ("SEARCHING", "COMPLETE")
        else "red" if status == "FAILED" else "yellow"
    )
    bits_label = str(start.bit_length()) if start is not None else "?"
    if (
        start is not None
        and end is not None
        and end > start
        and (end - 1).bit_length() != start.bit_length()
    ):
        bits_label += "–" + str((end - 1).bit_length())
    title = Text.assemble(
        ("SCOUT", "bold cyan"),
        ("  /  PRIME GAP SEARCH", "bold white"),
        ("   " + bits_label + " BIT", MUTED),
    )
    status_text = Text.assemble((status, "bold " + color), ("   " + _duration(elapsed), "white"))
    header = Table.grid(expand=True)
    header.add_column(ratio=1)
    header.add_column(justify="right")
    header.add_row(title, status_text)
    intro = Panel(header, border_style="cyan", box=box.ROUNDED, padding=(0, 1))
    header_height = 1 if width >= 104 and height < 32 else 3
    if header_height == 1:
        intro = header
    # The shared metric renderer is unchanged; a lower four-card breakpoint fits a 100-col
    # standalone search console without inventing wallet/network sections.
    columns = 4 if width >= 92 else 2
    card_height = 4 if height >= 36 and columns == 4 else 3
    samples = state.get("_ui_rate_samples", ())
    if "average_rate" in state:
        average = _num(state.get("average_rate"))
        span = min(60.0, max(0.0, _num(state.get("observed_active_seconds"), 0.0)))
        average_mature = span >= 60
    else:
        average, span, average_mature = rolling_average(
            samples, state.get("_ui_rate_window_matured", False)
        )
    observed_tenths = math.floor(span * 10) / 10
    avg_detail = (
        ("Observed " + f"{observed_tenths:.1f}" + " / 60 s")
        if not average_mature
        else "Observed active calculation"
    )
    avg_title = "Avg · 60 sec"
    paused_detail = (
        "Paused · last active"
        if status == "PAUSED"
        else "Observed backend" if "speed_rate" in state else "Init included"
    )
    tests_rate = (
        _num(state.get("compute_tests_rate"))
        if "compute_tests_rate" in state
        else tests / elapsed if elapsed > 0 else None
    )
    cards = [
        metric("Speed", _speed(rate), paused_detail if card_height >= 4 else "", card_height),
        metric(avg_title, _speed(average), avg_detail if card_height >= 4 else "", card_height),
        metric(
            "Tests/s",
            "—" if tests_rate is None else compact_number(tests_rate) + " tests/s",
            "Whole active wall" if card_height >= 4 else "",
            card_height,
        ),
        metric(
            "ETA",
            _duration(eta),
            f"{proportion*100:.2f}% complete" if card_height >= 4 else "",
            card_height,
        ),
    ]
    metrics = Table.grid(expand=True, padding=(0, 1))
    for _ in range(columns):
        metrics.add_column(ratio=1)
    for i in range(0, 4, columns):
        metrics.add_row(*cards[i : i + columns])
    device = safe(state.get("gpu_name", "Waiting for GPU…"))
    index = safe(state.get("gpu_index", 0))
    host = safe(state.get("host", "local"))
    local = host.lower() in ("local", "localhost", "")
    host_label = "Local" if local else host
    if (
        not local
        and str(state.get("transport", "")).lower() == "tailscale"
        and "tailscale" not in host.lower()
    ):
        host_label += " · Tailscale"
    arch = state.get("compute_capability", state.get("arch", state.get("compute", "—")))
    arch = safe(arch)
    if arch != "—" and not arch.lower().startswith("sm"):
        arch = "sm_" + arch.replace(".", "")
    memory = _int(state.get("vram_mib"))
    memory_text = "—" if memory is None else f"{memory:,} MiB"
    driver = safe(state.get("driver", "—"))
    driver_api = _int(state.get("cuda_driver_api_version"))
    if driver_api is None and driver.isdecimal() and int(driver) >= 1000:
        driver_api = int(driver)
    driver_label = (
        ("CUDA API " + str(driver_api // 1000) + "." + str((driver_api % 1000) // 10))
        if driver_api is not None
        else "Driver " + driver
    )
    core = _num(state.get("clock_sm_mhz"))
    mem = _num(state.get("clock_mem_mhz"))
    clock = lambda v: "—" if v is None else f"{v:,.0f} MHz"
    details = Table.grid(expand=True, padding=(0, 2))
    details.add_column(ratio=1)
    details.add_column(ratio=1)
    details.add_row(
        Text("GPU " + index + "  " + device, overflow="ellipsis", no_wrap=True),
        Text.assemble(
            ("Host  " + host_label, "green"),
            ("   Run size ", "white"),
            (sci(total), "bold cyan"),
            (" positions", "white"),
        ),
    )
    details.add_row(
        Text("CUDA " + arch + "   " + driver_label, no_wrap=True, overflow="ellipsis"),
        Text(
            "VRAM " + memory_text + "   Core " + clock(core) + " / Mem " + clock(mem),
            no_wrap=True,
            overflow="ellipsis",
        ),
    )
    from pgn_threshold_policy import safe_view

    threshold_info = safe_view(
        state.get("configuration") or {},
        start,
        end,
        current,
        binding=state.get("threshold_binding"),
    )
    threshold = _int(
        state.get("minimum_gap", state.get("gap_min")), threshold_info.get("count_gap", 960)
    )
    target_merit = _num(state.get("target_merit"), 32.0)
    target_label = target_gap_label(start, end, target_merit)
    tight = height < 36 and width >= 92
    exact = lambda v: "—" if v is None else str(v)
    if width >= 92:
        details.add_row(
            Text("Start  " + exact(start) + "  (" + _science(start) + ")", no_wrap=True),
            Text("End  " + exact(end) + "  (" + _science(end) + ")", no_wrap=True),
        )
        if not tight:
            details.add_row(
                Text(
                    "Current "
                    + exact(current)
                    + "  ("
                    + _science(current, 5 if width < 104 else 8)
                    + ")",
                    no_wrap=True,
                ),
                Text(target_label, no_wrap=True),
            )
        device_height = 6 if tight else 7
    else:
        details = Table.grid(expand=True)
        details.add_column()
        for label, text in [
            ("GPU", index + "  " + device),
            ("Host", host_label + "   Run size " + sci(total) + " positions"),
            (
                "VRAM",
                memory_text
                + "   "
                + driver_label
                + "   Core "
                + clock(core)
                + " / Mem "
                + clock(mem),
            ),
            ("Start", safe(start) + "  (" + _science(start) + ")"),
            ("End", safe(end) + "  (" + _science(end) + ")"),
            ("Current", safe(current) + "  (" + _science(current) + ")"),
        ]:
            details.add_row(Text(label + "  " + text, no_wrap=True, overflow="ellipsis"))
        device_height = 9
    current_prefix = "At " + exact(current) + "  " if tight else ""
    bar_width = max(8, width - 16 - len(current_prefix))
    done = int(proportion * bar_width)
    bar = Text.assemble(
        (current_prefix, "white"),
        ("━" * done, "bold cyan"),
        ("━" * (bar_width - done), MUTED),
        (f"  {proportion*100:6.2f}%", "bold white"),
    )
    device_title = (
        "DEVICE & RANGE  ·  end exclusive"
        + ("  ·  " + target_label if tight else "")
        + "  ·  "
        + threshold_info["actual_label"]
    )
    device_panel = Panel(
        Group(details, bar),
        title=device_title,
        title_align="left",
        border_style=MUTED,
        box=box.ROUNDED,
        padding=(0, 1),
    )
    records = []
    for row in state.get("gaps", ()) or ():
        try:
            gap, merit, lower = row
            gap, lower = _int(gap), _int(lower)
            merit = _num(merit)
        except (TypeError, ValueError):
            continue
        if gap is not None and lower is not None:
            records.append((gap, merit, lower))
    # Console discovery tables follow the counted threshold. File-detail
    # filtering is owned by the frontend and may have a different setting.
    display_records = [r for r in records if r[0] >= threshold]
    from pgn_statistics import statistics_rows
    statistics = state.get("range_statistics")
    if statistics is None and status.upper() == "IDLE" and completed == 0 and not state.get("resume_folder"):
        first_bin = ((threshold + 99) // 100) * 100
        statistics = dict(count_total=0, threshold_counts={str(n): 0 for n in
            [threshold] + [n for n in range(first_bin, first_bin + 600, 100) if n > threshold]},
            merit_band_counts={}, at_or_above_target=0, statistics_target=target_merit)
    stat_rows = statistics_rows(statistics, target_merit) if statistics else []
    stats_table = Table.grid(expand=True, padding=(0, 1))
    stats_table.add_column(ratio=1, no_wrap=True)
    stats_table.add_column(justify="right", no_wrap=True)
    for label, count, section in stat_rows:
        stats_table.add_row(Text(label, style="bold cyan" if section else "white"),
                            Text("" if section else number(count), style="bold cyan"))
    if not statistics:
        stats_table.add_row(str(state.get("statistics_notice", "Statistics unavailable")), "—")
    footer_height = 3
    counter_height = 3
    fixed = (
        header_height
        + card_height * (4 // columns)
        + device_height
        + counter_height
        + footer_height
    )
    from pgn_ui_options import display_rows

    result_limit = display_rows(state.get("display_rows", 10))
    # Keep exact prime coordinates legible. Narrow terminals stack the panels;
    # they never silently shorten scientific results to an ambiguous prefix.
    three_column_width = 2 * (len(str(end or start or 10**20)) + 24) + 36
    side_by_side = width >= three_column_width
    table_min = result_limit + (3 if tight else 5)
    stats_min = len(stat_rows) + 2 if stat_rows else 3
    result_min = max(table_min, stats_min) if side_by_side else table_min * 2 + stats_min
    result_height = max(result_min, height - fixed)
    panel_height = result_height if side_by_side else max(table_min, result_height // 2)
    best = sorted(display_records, key=lambda r: (-r[0], r[2]))[:result_limit]
    latest = list(reversed(display_records[-result_limit:]))
    goal_label = f"{target_merit:g}"
    best_panel = Panel(
        _gap_table(best, limit=result_limit, compact=tight, target=target_merit),
        height=panel_height,
        title="BEST " + str(result_limit) + "  ·  ≥" + str(threshold) + "  ·  target " + goal_label,
        title_align="left",
        border_style=MUTED,
        box=box.ROUNDED,
        padding=(0, 1),
    )
    recent = Panel(
        _gap_table(
            latest,
            limit=result_limit,
            compact=tight,
            target=target_merit,
            recent=True,
            best_lowers={r[2] for r in best},
        ),
        height=panel_height,
        title="RECENT " + str(result_limit) + "  ·  gaps ≥" + str(threshold),
        title_align="left",
        border_style=MUTED,
        box=box.ROUNDED,
        padding=(0, 1),
    )
    if side_by_side:
        results = Table.grid(expand=True, padding=(0, 1))
        result_width = (width - 36) // 2
        results.add_column(width=result_width)
        results.add_column(width=width - 36 - result_width)
        results.add_column(width=30)
        statistics_panel = Panel(stats_table, title="STATISTICS", height=panel_height,
            title_align="left", border_style=MUTED, box=box.ROUNDED, padding=(0, 0))
        results.add_row(best_panel, recent, statistics_panel)
    else:
        panel_height = table_min
        best_panel.height = recent.height = panel_height
        results = Group(best_panel, recent, Panel(stats_table, title="STATISTICS", height=stats_min))
    counters = Table.grid(expand=True, padding=(0, 1))
    counters.add_column(ratio=2)
    counters.add_column(ratio=1)
    gap_count = _int(state.get("gap_count"), len(records))
    counters.add_row(
        Text.assemble(
            ("Positions ", "white"),
            (compact_number(completed), "bold cyan"),
            (" / " + sci(total), MUTED),
        ),
        Text.assemble(("Tests ", "white"), (compact_number(tests), "bold cyan")),
    )
    counts = Panel(
        counters,
        title="RANGE PROGRESS",
        title_align="left",
        border_style=MUTED,
        box=box.ROUNDED,
        padding=(0, 1),
    )
    key_help = safe(state.get("key_help", "P Pause/resume | M Menu | Q Quit"))
    key_help = " | ".join(
        item for item in key_help.split(" | ") if not item.strip().upper().startswith("F ")
    )
    if status != "IDLE" and not any(item.strip().upper().startswith("P ") for item in key_help.split(" | ")):
        key_help = "P Pause/resume | " + key_help
    from pgn_ui_views import _footer, _footer_specs
    from pgn_ui_workflow import pause_control

    raw_specs, _ = _footer_specs(key_help.replace(" | ", " · "))
    primary_control = pause_control(state)
    buttons = [
        dict(label=label, shortcut=shortcut, key=key, enabled=True)
        for label, shortcut, key in raw_specs
        if key not in ("ESC", "p", primary_control["key"])
    ]
    buttons.insert(0, primary_control)
    footer, button_height, button_regions, _ = _footer(buttons, width, height, include_back=False)
    assert button_height == 3
    if width < 66 or height < fixed + result_min:
        notice = Panel(
            Text(
                f"Best, Recent and complete Statistics.\nUse {three_column_width} columns for three panels, or {66} × {fixed+result_min} for stacked panels.\nSearch continues; "
                + key_help
            ),
            title="Terminal size",
            border_style="yellow",
        )
        layout = Layout()
        layout.split_column(
            Layout(intro, size=header_height),
            Layout(notice, ratio=1),
            Layout(footer, size=footer_height),
        )
        layout.pgn_hit_regions = button_regions
        return layout
    layout = Layout()
    layout.split_column(
        Layout(intro, size=header_height),
        Layout(metrics, size=card_height * (4 // columns)),
        Layout(device_panel, size=device_height),
        Layout(results, size=result_height),
        Layout(counts, size=counter_height),
        Layout(footer, size=footer_height),
    )
    layout.pgn_hit_regions = button_regions
    return layout
