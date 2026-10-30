"""Compiler-neutral include isolation for the POSIX CUDA preprocessor."""

from pathlib import Path
import shutil, re, tempfile


def prepare(source, build_root):
    build_root.mkdir(parents=True, exist_ok=True)
    output = Path(tempfile.mkdtemp(prefix="native-inputs-", dir=build_root))
    shutil.copytree(source, output, dirs_exist_ok=True)
    for path in sorted(output.rglob("*")):
        rel = path.relative_to(output)
        if (
            not path.is_file()
            or rel.parts[0] != "arithmetic"
            or path.suffix.lower() not in (".cuh", ".h")
        ):
            continue
        body = re.sub(r"(?m)^\s*#\s*pragma\s+once\s*\n", "", path.read_text())
        guard = "SCOUT_ISOLATED_" + re.sub("[^A-Z0-9]", "_", rel.as_posix().upper())
        classic = re.match(r"\s*#ifndef\s+(\w+)\s*\n\s*#define\s+\1\b", body)
        if classic:
            body = re.sub(r"\b" + re.escape(classic.group(1)) + r"\b", guard + "_ORIGINAL", body)
        text = (
            "#ifndef " + guard + "\n#define " + guard + "\n" + body + "\n#endif // " + guard + "\n"
        )
        path.write_text(text, encoding="utf-8", newline="\r\n")
    return output
