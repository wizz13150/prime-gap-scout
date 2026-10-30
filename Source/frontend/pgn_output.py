"""Output policy and exact bin projection. Does not execute a worker."""

from pathlib import Path
from bisect import bisect_right
import csv
import io
import os
import sys


def default_output_base():
    """Adjacent results folder; an unwritable location is an explicit error."""
    app = Path(sys.executable) if getattr(sys, "frozen", False) else Path(__file__)
    return app.resolve().parent / "results"


def exact_bins(start, end, bins, rows):
    boundaries = [start + (end - start) * i // bins for i in range(bins + 1)]
    counts = [0] * bins
    for _, _, lower in rows:
        if not start <= lower < end:
            raise ValueError("Gap lower prime outside the session range")
        counts[bisect_right(boundaries, lower) - 1] += 1
    return boundaries, counts


def complete_counts_text(counts):
    output = io.StringIO(newline="")
    csv.writer(output, lineterminator="\n").writerow(counts)
    return output.getvalue()


def top_rows(rows, limit=100):
    if limit < 1:
        raise ValueError("Report limit must be positive")
    return sorted(rows, key=lambda row: (-row[0], row[2]))[:limit]


def files_context(folder, metadata=None):
    folder = Path(folder).resolve()
    # Exact known filenames: do not enumerate/sort every historical chunk file.
    if metadata is None:
        from pgn_session import read_session_metadata

        metadata = read_session_metadata(folder)
    config = metadata["configuration"]
    count = config.get("count_gap", config.get("min_gap", 960))
    detail = config.get("detail_gap", config.get("min_gap", 960))
    names = [
        f"GapReport_details_ge{detail}.txt",
        f"counts_ge{count}.csv",
        f"counts_ge{count}.partial.csv",
        "bins.csv",
        "finalscreen.txt",
        "session.json",
        "run.json",
        "summary.log",
        "session-events.jsonl",
        "session-index.sqlite3",
    ]
    return {
        "folder": str(folder),
        "files": {name: str(folder / name) for name in names if (folder / name).is_file()},
    }


def write_index_counts(folder, args, end, position, status, index, write):
    """Bounded-memory bin projection, even when the persistent index is huge."""
    below = args.start + position
    from pgn_statistics import statistics_rows
    rows = statistics_rows(index.projection.value, float(args.target_merit))
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(("distribution", "count"))
    writer.writerows((label, count) for label, count, section in rows if not section)
    write(folder / "statistics.csv", output.getvalue())
    if args.bins == len(index.bounds) - 1:
        counts = index.bin_counts(args.count_gap, below)
        bounds = index.bounds
    else:
        bounds, counts = exact_bins(
            args.start, end, args.bins, index.iter_rows(args.count_gap, below)
        )
    if status == "COMPLETE":
        if below != end:
            raise ValueError("Complete CSV requires the exact full prefix")
        name = f"counts_ge{args.count_gap}.csv"
        write(folder / name, complete_counts_text(counts))
        output = io.StringIO(newline="")
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(("index", "start", "end", "count"))
        writer.writerows((i + 1, bounds[i], bounds[i + 1], counts[i]) for i in range(len(counts)))
        write(folder / "bins.csv", output.getvalue())
        return {"counts_csv": name, "bins_csv": "bins.csv", "partial_csv": None}
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(("index", "start", "end", "count_observed", "coverage", "covered_end"))
    for i, count in enumerate(counts):
        left, right = bounds[i], bounds[i + 1]
        cover = "COMPLETE" if right <= below else "PARTIAL" if left < below else "UNSEARCHED"
        writer.writerow(
            (
                i + 1,
                left,
                right,
                "" if cover == "UNSEARCHED" else count,
                cover,
                min(right, max(left, below)),
            )
        )
    name = f"counts_ge{args.count_gap}.partial.csv"
    write(folder / name, output.getvalue())
    return {"counts_csv": None, "bins_csv": None, "partial_csv": name}
