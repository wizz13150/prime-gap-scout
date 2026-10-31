"""Build the shipped CUDA workers and optional portable terminal application."""

from pathlib import Path
import argparse, hashlib, json, os, re, shutil, subprocess, sys

ROOT = Path(__file__).resolve().parent
NATIVE = ROOT / "native"
FRONTEND = ROOT / "frontend"


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest().upper()


def native_manifest(source=NATIVE):
    rows = []
    for path in sorted(
        source.rglob("*"), key=lambda path: path.relative_to(source).as_posix().casefold()
    ):
        if path.is_file() and path.suffix.lower() in (
            ".cu",
            ".cuh",
            ".h",
            ".def",
            ".bin",
            ".manifest",
        ):
            rows.append(
                {
                    "file": path.relative_to(source).as_posix(),
                    "bytes": path.stat().st_size,
                    "sha256": digest(path),
                }
            )
    if not rows:
        raise RuntimeError("Missing native source inputs")
    manifest = source / "SOURCE-MANIFEST.json"
    manifest.write_text(
        json.dumps({"schema": "PRIME_GAP_SCOUT_NATIVE_INPUTS_V1", "files": rows}, indent=2) + "\n",
        encoding="utf-8",
        newline="\r\n",
    )
    return digest(manifest)


def build(archs):
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+(?:-[a-zA-Z0-9.]+)?", version):
        raise RuntimeError("Invalid release VERSION")
    (FRONTEND / "scout_version.py").write_text('"""Generated from Source/VERSION."""\nVERSION = ' + repr(version) + "\n", encoding="utf-8")
    (NATIVE / "scout_version.h").write_text('#pragma once\n#define SCOUT_VERSION "' + version + '"\n', encoding="utf-8")
    proof_root = FRONTEND / "lib" / "proof" / ("windows" if os.name == "nt" else "linux")
    proof_manifest = proof_root / "manifest.json"
    if not proof_manifest.is_file():
        raise RuntimeError("Bundle the exact proof runtime first with --proof-wheel")
    proof = json.loads(proof_manifest.read_text(encoding="utf-8"))
    for item in proof["libraries"]:
        path = proof_root / item["file"]
        if (
            path.name != item["file"]
            or path.stat().st_size != item["bytes"]
            or digest(path) != item["sha256"]
        ):
            raise RuntimeError("Exact proof runtime differs from its manifest")
    proof_sha = digest(proof_manifest)
    nvcc = shutil.which("nvcc")
    if not nvcc and os.environ.get("CUDA_PATH"):
        candidate = (
            Path(os.environ["CUDA_PATH"]) / "bin" / ("nvcc.exe" if os.name == "nt" else "nvcc")
        )
        if candidate.is_file():
            nvcc = str(candidate)
    if not nvcc:
        raise RuntimeError(
            "nvcc was not found; install CUDA Toolkit and put its bin directory on PATH"
        )
    supported = subprocess.run(
        [nvcc, "--list-gpu-code"], capture_output=True, text=True, check=True
    ).stdout
    source = NATIVE
    if os.name != "nt":
        from prepare_native import prepare

        source = prepare(NATIVE, ROOT / "build")
    source_sha = native_manifest(source)
    bins = FRONTEND / "bin"
    bins.mkdir(exist_ok=True)
    flags = [
        "-O3",
        "-DNDEBUG",
        "--std=c++17",
        "--threads",
        "1",
        "--split-compile",
        "4",
        "-lineinfo",
        "-dlto",
        "-rdc=true",
        "--cudart",
        "shared",
        "-lcudadevrt",
        "-DPGN_RELEASE_ENABLE_PUBLIC_PERIG=0",
        "-DPGN_DESCRIPTOR_LANES=2",
        "-DPGN_DESCRIPTOR_BLOCKS=64",
        "-DPGN_EULER96_LAZY",
        "-DPGN_EULER96",
        "-DPGN_EULER96_FIXED_HIGH10",
        "-DPGN_PRESIEVE_GROUPS=1",
        "-DPGN_MARK_FULL_FAST",
        "-DPGN_MARK_BANK_ROTATE",
        "-DPGN_FUSED_SIEVE",
        "-DPGN_VERIFY_GAPS",
    ]
    completed = []
    for arch in archs:
        if "sm_" + str(arch) not in supported:
            print("SKIP unsupported nvcc target sm_" + str(arch))
            continue
        suffix = ".exe" if os.name == "nt" else ""
        output = bins / f"pgn68-worker-sm{arch}-k64{suffix}"
        command = [nvcc, *flags, f"-arch=sm_{arch}", f"-DPGN_RELEASE_BUILD_ARCH={arch}"]
        if os.name == "nt":
            command += [
                "-Xcompiler=/MT",
                "-Xcompiler=/utf-8",
                "-Xlinker=/MANIFEST:EMBED",
                "-Xlinker=/MANIFESTINPUT:worker.manifest",
            ]
        else:
            compiler = os.environ.get("CXX") or shutil.which("g++-13") or shutil.which("g++")
            if compiler:
                command += ["-ccbin", compiler]
            command += ["-Xlinker=-rpath", "-Xlinker=$ORIGIN/../lib", "-ldl"]
        command += ["search_worker.cu", "-o", str(output)]
        subprocess.run(command, cwd=source, check=True)
        image_sha = digest(output)
        for profile in (8, 16, 32, 64):
            target = bins / f"pgn68-worker-sm{arch}-k{profile}{suffix}"
            if target != output:
                shutil.copyfile(output, target)
            sidecar = {
                "schema": "PGN_NATIVE_MODULE_METADATA_V1",
                "resident_job_schema": "SCOUT_RESIDENT_JOB_V1",
                "image_sha256": image_sha,
                "source_manifest_sha256": source_sha,
                "gap_runtime_schema": "PGN_NATIVE_GAP_RUNTIME_V1",
                "profile_k": profile,
                "build_arch": arch,
                "exact_proof_manifest_sha256": proof_sha,
            }
            target.with_name(target.name + ".module.json").write_text(
                json.dumps(sidecar, indent=2) + "\n"
            )
        completed.append(arch)
    if not completed:
        raise RuntimeError("No requested architecture compiled")
    cuda = Path(nvcc).resolve().parent.parent
    if os.name == "nt":
        libraries = list((cuda / "bin").glob("cudart64_*.dll"))
        if not libraries:
            raise RuntimeError("CUDA runtime DLL not found in Toolkit bin")
        for path in libraries:
            shutil.copyfile(path, bins / path.name)
        # The Windows public-reference comparison uses the CUDA12.8 NVRTC ABI.
        # Bundle its redistributable pair when this Toolkit provides it, so the
        # prebuilt diagnostic does not depend on a developer's installed Toolkit.
        nvrtc_pair = [cuda / "bin" / name for name in
                      ("nvrtc64_120_0.dll", "nvrtc-builtins64_128.dll")]
        if all(path.is_file() for path in nvrtc_pair):
            libraries_dir = FRONTEND / "lib"
            libraries_dir.mkdir(exist_ok=True)
            for path in nvrtc_pair:
                shutil.copyfile(path, libraries_dir / path.name)
    else:
        lib = FRONTEND / "lib"
        lib.mkdir(exist_ok=True)
        libraries = list((cuda / "lib64").glob("libcudart.so.*"))
        if not libraries:
            raise RuntimeError("CUDA runtime shared library not found")
        for path in libraries:
            shutil.copyfile(path.resolve(), lib / path.name)
    return completed


def package():
    from PyInstaller.__main__ import run
    from pgn68 import argument_parser
    from pgn_launcher import generate

    dest = ROOT / "build" / ("windows" if os.name == "nt" else "ubuntu")
    separator = ";" if os.name == "nt" else ":"
    args = [
        "--noconfirm",
        "--onedir",
        "--console",
        "--name",
        "pgn68",
        "--distpath",
        str(dest),
        "--workpath",
        str(ROOT / "build/work"),
        "--specpath",
        str(ROOT / "build/spec"),
        "--paths",
        str(FRONTEND),
        "--collect-all",
        "rich",
        "--hidden-import",
        "sqlite3",
        "--hidden-import",
        "_sqlite3",
        "--add-data",
        str(FRONTEND / "data/diagnostic") + separator + "data/diagnostic",
    ]
    icon = FRONTEND / "data/horizon.ico"
    args += ["--add-data", str(icon) + separator + "data"]
    if os.name == "nt":
        args += ["--icon", str(icon)]
    for path in FRONTEND.glob("*.py"):
        if path.name != "pgn68.py":
            args += ["--hidden-import", path.stem]
    # Rich can discover optional notebook/scientific integrations installed on
    # the build machine. Scout uses its terminal API and standard-library data
    # structures; those unrelated packages are not application dependencies.
    for module in ("IPython", "numpy", "matplotlib", "scipy", "pandas", "sympy",
                   "torch", "tensorflow", "cupy", "numba"):
        args += ["--exclude-module", module]
    run(args + [str(FRONTEND / "pgn68.py")])
    out = dest / "pgn68"
    for name in ("bin", "lib"):
        if (FRONTEND / name).is_dir():
            shutil.copytree(FRONTEND / name, out / name, dirs_exist_ok=True)
    (out / "ui").mkdir(exist_ok=True)
    for name in ("console_ui.py", "pgn_dashboard.py"):
        shutil.copyfile(FRONTEND / name, out / "ui" / name)
    generate(argument_parser(), out)
    for path in (out / "Start-PGN68.cmd", out / "Start-PGN68.sh"):
        text = (
            path.read_text()
            .replace('set "IDLE=0"', 'set "IDLE=1"')
            .replace("export IDLE=0", "export IDLE=1")
            .replace("export IDLE='0'", "export IDLE='1'")
        )
        path.write_text(text, newline="\r\n" if path.suffix == ".cmd" else "\n")
    print("Complete portable directory:", out)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--archs", default="86,120", help="Comma-separated CUDA targets, default86,120"
    )
    parser.add_argument(
        "--package",
        action="store_true",
        help="Also freeze the Python frontend into a portable directory",
    )
    parser.add_argument(
        "--proof-wheel",
        type=Path,
        help="python-flint wheel supplying the target platform shared proof libraries",
    )
    options = parser.parse_args()
    targets = [int(part) for part in options.archs.split(",")]
    if not targets or any(arch not in (86, 120) for arch in targets):
        parser.error("Unsupported requested build target")
    sys.path.insert(0, str(FRONTEND))
    if options.proof_wheel:
        from bundle_proof_runtime import bundle

        bundle(options.proof_wheel, FRONTEND, NATIVE)
    build(targets)
    if options.package:
        package()
