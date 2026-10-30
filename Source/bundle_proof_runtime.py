"""Bundle the shared FLINT proof runtime from an explicitly supplied wheel.

Only the shared libraries and their licenses are used. No Python extension is
loaded, so the wheel's CPython tag does not constrain the application runtime.
"""

from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import zipfile


def bundle(wheel, frontend, native):
    wheel, frontend, native = Path(wheel), Path(frontend), Path(native)
    windows = wheel.name.endswith("win_amd64.whl")
    platform = "windows" if windows else "linux"
    destination = frontend / "lib" / "proof" / platform
    destination.mkdir(parents=True, exist_ok=True)
    licenses = native.parent / "THIRD-PARTY-LICENSES" / "proof-runtime"
    licenses.mkdir(parents=True, exist_ok=True)
    records = []
    with zipfile.ZipFile(wheel) as archive:
        members = archive.infolist()
        if sum(item.file_size for item in members) > 100 * 1024 * 1024:
            raise ValueError("Unexpected proof wheel size")
        for item in members:
            name = Path(item.filename)
            if ".." in name.parts or name.is_absolute():
                raise ValueError("Invalid proof wheel member")
            library = name.parts[0] == "python_flint.libs" and item.file_size > 0
            license_file = ".dist-info" in item.filename and (
                "license" in item.filename.lower() or "copying" in item.filename.lower()
            )
            if not (library or license_file):
                continue
            target = destination / name.name if library else licenses / platform / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(item))
            if library:
                records.append(
                    {
                        "file": target.name,
                        "bytes": target.stat().st_size,
                        "sha256": hashlib.sha256(target.read_bytes()).hexdigest().upper(),
                    }
                )
    main = [item for item in records if item["file"].startswith("libflint")]
    if len(main) != 1 or not records:
        raise ValueError("Wheel must contain exactly one shared FLINT library")
    manifest = {
        "schema": "SCOUT_EXACT_PROOF_RUNTIME_V1",
        "source_wheel": wheel.name,
        "wheel_sha256": hashlib.sha256(wheel.read_bytes()).hexdigest().upper(),
        "platform": "windows" if windows else "linux",
        "libraries": records,
        "proof_function": "fmpz_is_prime",
        "probable_prime_is_not_accepted": True,
    }
    (destination / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    config = native / ("proof_runtime_" + platform + ".h")
    # One platform per build tree. The final source distribution supplies the
    # wheel as an explicit build input rather than depending on a machine path.
    config.write_text(
        "#pragma once\n#define SCOUT_PROOF_SUBDIRECTORY "
        + json.dumps(platform)
        + "\n#define SCOUT_PROOF_LIBRARY "
        + json.dumps(main[0]["file"])
        + "\n#define SCOUT_PROOF_LIBRARY_BYTES "
        + str(main[0]["bytes"])
        + "ULL\n",
        encoding="utf-8",
    )
    (native / "proof_runtime_config.h").write_text(
        '#pragma once\n#ifdef _WIN32\n#include "proof_runtime_windows.h"\n#else\n#include "proof_runtime_linux.h"\n#endif\n',
        encoding="utf-8",
    )
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheel", required=True, type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    result = bundle(args.wheel, root / "frontend", root / "native")
    print(json.dumps({"platform": result["platform"], "libraries": len(result["libraries"])}))
