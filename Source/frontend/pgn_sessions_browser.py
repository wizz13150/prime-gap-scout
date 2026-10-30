"""Read-only actual sessions. Never constructs SessionStore/GapIndex or writes metadata."""

from dataclasses import dataclass
from pathlib import Path
import csv, json, os, sqlite3
from pgn_session import read_session_metadata


def read_json(path, maximum=1024 * 1024):
    path = Path(path)
    if path.stat().st_size > maximum:
        raise ValueError("Oversized session metadata: " + str(path))
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (RecursionError, OverflowError) as error:
        raise ValueError("Invalid document nesting") from error
    if not isinstance(value, dict):
        raise ValueError("Metadata document must be an object: " + str(path))
    return value


@dataclass
class SavedSession:
    session_id: str
    folder: Path
    status: str
    configuration: dict
    run: dict
    metadata: dict
    host: str = "local"
    readonly_mirror: bool = False

    @property
    def start(self):
        return int(self.configuration["start"])

    @property
    def end(self):
        return int(self.configuration["end"])

    @property
    def position(self):
        return int(self.metadata.get("positions", self.run.get("positions", 0)))

    @property
    def date(self):
        return str(self.metadata.get("created_utc", self.run.get("started_utc", "")))

    @property
    def gpu(self):
        return self.run.get("selected_gpu", self.metadata.get("device", {}))

    @property
    def resumable(self):
        return (
            self.configuration.get("native_protocol") == "PGN_NATIVE_GAP_RUNTIME_V1"
            and bool(self.configuration.get("threshold_policy"))
            and not self.readonly_mirror
            and self.status not in ("COMPLETE", "REPLACED_BEFORE_START")
            and not self.metadata.get("prepared_replacement")
            and self.metadata.get("schema") == "PGN68_DURABLE_SESSION_V1"
        )

    def entries(self):
        # Actual files, not a synthetic README or guessed path. A session has a
        # bounded file set; catalog history is separate from this directory.
        items = [
            {
                "path": str(self.folder),
                "label": "Open session folder",
                "detail": self.host + " • " + self.status,
                "is_dir": True,
            }
        ]
        with os.scandir(self.folder) as scan:
            files = [Path(item.path) for item in scan if item.is_file()]
        priority = {
            "GapReport": 0,
            "counts": 1,
            "bins": 2,
            "finalscreen": 3,
            "run": 4,
            "session.json": 5,
            "origin": 6,
            "summary": 7,
        }

        def rank(path):
            return (
                next((v for p, v in priority.items() if path.name.startswith(p)), 10),
                path.name.lower(),
            )

        for path in sorted(files, key=rank):
            if (
                ".pending" in path.name
                or ".tmp-" in path.name
                or path.name.endswith(("-wal", "-shm", ".lock"))
            ):
                continue
            try:
                size = path.stat().st_size
            except FileNotFoundError:
                continue
            items.append(
                {
                    "path": str(path.resolve()),
                    "label": path.name,
                    "detail": str(size) + " bytes",
                    "is_dir": False,
                }
            )
        return items

    def counted_gaps(self):
        files = self.run.get("files", {})
        name = files.get("counts_csv") or f"counts_ge{self.configuration.get('count_gap',960)}.csv"
        path = self.folder / Path(name).name
        if not path.is_file():
            return None
        if path.stat().st_size > 1024 * 1024:
            return None
        with path.open(newline="", encoding="utf-8") as stream:
            rows = csv.reader(stream)
            values = []
            for row in rows:
                try:
                    values.extend(int(value) for value in row)
                except ValueError:
                    return None
        return sum(values)

    def context(self):
        gpu = self.gpu
        return {
            "session_id": self.session_id,
            "folder": str(self.folder),
            "status": self.status,
            "start": self.start,
            "end": self.end,
            "position": self.position,
            "tests": self.metadata.get("tests", self.run.get("tests")),
            "gpu_name": gpu.get("model", "--"),
            "gpu_uuid": gpu.get("uuid", "--"),
            "gpu_index": gpu.get("index", 0),
            "created_utc": self.date,
            "host": self.host,
            "readonly_mirror": self.readonly_mirror,
            "counted_gaps": self.counted_gaps(),
            "min_gap": self.configuration.get("min_gap", 960),
            "bins": self.configuration.get("bins", 100),
            "top": self.configuration.get("report_top", 100),
            "target_merit": self.configuration.get("target_merit", 32),
            "next_range": self.metadata.get("next_range"),
            "configuration": self.configuration,
            "resumable": self.resumable,
            "files": {x["label"]: x["path"] for x in self.entries()[1:]},
        }


def session_from_folder(folder, entry=None):
    folder = Path(folder).expanduser().resolve()
    entry = entry or {}
    metadata = (
        read_session_metadata(folder)
        if (folder / "session.json").is_file() or (folder / "session-index.sqlite3").is_file()
        else {}
    )
    run = (
        read_json(folder / "run.json") if (folder / "run.json").is_file() else entry.get("run", {})
    )
    if not isinstance(metadata, dict) or not isinstance(run, dict):
        raise ValueError("Session metadata/run must be objects")
    gpu = run.get("selected_gpu", metadata.get("device", {}))
    if not isinstance(gpu, dict):
        raise ValueError("Saved GPU metadata must be an object")
    configuration = metadata.get("configuration", entry.get("configuration", {}))
    if (
        not isinstance(configuration, dict)
        or "start" not in configuration
        or "end" not in configuration
    ):
        raise ValueError("Session configuration must be an object with start/end")
    if any(isinstance(configuration[k], (bool, float)) for k in ("start", "end")):
        raise ValueError("Session endpoints must be exact integers")
    try:
        start, end = int(configuration["start"]), int(configuration["end"])
        position = int(metadata.get("positions", run.get("positions", 0)))
    except (ValueError, TypeError, OverflowError) as error:
        raise ValueError("Invalid session endpoint/progress integers") from error
    if not 0 <= position <= end - start or not start < end:
        raise ValueError("Invalid session range/progress")
    if configuration.get("native_protocol") == "PGN_NATIVE_GAP_RUNTIME_V1":
        from pgn_native_contract import require_new_configuration

        require_new_configuration(configuration)
    origin = read_json(folder / "origin.json") if (folder / "origin.json").is_file() else {}
    return SavedSession(
        str(metadata.get("session_id", entry.get("id", run.get("session_id", folder.name)))),
        folder,
        str(metadata.get("state", run.get("status", entry.get("status", "UNKNOWN")))),
        configuration,
        run,
        metadata,
        str(entry.get("host", origin.get("host", "local"))),
        bool(entry.get("readonly_mirror", origin.get("readonly_mirror", False))),
    )


def _note(errors, path, problem):
    if errors is not None and len(errors) < 8:
        errors.append(
            {"path": str(path), "reason": str(problem)[:240], "kind": type(problem).__name__}
        )


def load_catalog(path, errors=None):
    path = Path(path).resolve()
    data = read_json(path, 4 * 1024 * 1024)
    if data.get("schema") != "PGN_REAL_SESSION_CATALOG_V1" or not isinstance(
        data.get("sessions"), list
    ):
        raise ValueError("Invalid actual-session catalog schema/entries")
    result = []
    for entry in data["sessions"]:
        try:
            if not isinstance(entry, dict) or not isinstance(entry.get("folder"), str):
                raise ValueError("Catalog entry must name a local folder")
            folder = (path.parent / entry["folder"]).resolve()
            if folder.parent != path.parent:
                raise ValueError("Catalog session escaped its export root")
            result.append(session_from_folder(folder, entry))
        except (OSError, ValueError, TypeError, KeyError, RecursionError, sqlite3.Error) as problem:
            _note(errors, path, problem)
    return sorted(result, key=lambda item: item.date, reverse=True)


def discover_sessions(roots=(), catalog=None, errors=None):
    found = {}
    if catalog and Path(catalog).is_file():
        try:
            for item in load_catalog(catalog, errors):
                found[item.session_id] = item
        except (OSError, ValueError, TypeError, KeyError, RecursionError, sqlite3.Error) as problem:
            _note(errors, catalog, problem)
    for root in roots:
        root = Path(root).expanduser()
        if not root.is_dir():
            continue
        candidates = [root]
        try:
            with os.scandir(root) as scan:
                candidates.extend(Path(item.path) for item in scan if item.is_dir())
        except OSError as problem:
            _note(errors, root, problem)
            continue
        for folder in candidates:
            if not (
                (folder / "session.json").is_file() or (folder / "session-index.sqlite3").is_file()
            ):
                continue
            try:
                item = session_from_folder(folder)
            except (
                OSError,
                ValueError,
                TypeError,
                KeyError,
                RecursionError,
                sqlite3.Error,
            ) as problem:
                _note(errors, folder, problem)
                continue
            if item.session_id not in found:
                found[item.session_id] = item
    return sorted(found.values(), key=lambda item: item.date, reverse=True)


class ArrowList:
    def __init__(self, entries, page_size=12):
        self.entries = list(entries)
        self.selected = 0
        self.offset = 0
        self.page_size = max(1, page_size)

    def move(self, event):
        end = max(0, len(self.entries) - 1)
        if event == "UP":
            self.selected = max(0, self.selected - 1)
        elif event == "DOWN":
            self.selected = min(end, self.selected + 1)
        elif event == "PGUP":
            self.selected = max(0, self.selected - self.page_size)
        elif event == "PGDN":
            self.selected = min(end, self.selected + self.page_size)
        elif event == "HOME":
            self.selected = 0
        elif event == "END":
            self.selected = end
        if self.selected < self.offset:
            self.offset = self.selected
        if self.selected >= self.offset + self.page_size:
            self.offset = self.selected - self.page_size + 1

    def visible(self):
        return self.entries[self.offset : self.offset + self.page_size]

    def current(self):
        return self.entries[self.selected] if self.entries else None
