"""Check the actual Core2 C++ frontend without compiling a firmware image.

An explicitly supplied existing compilation database selects the cached cross
compiler. It runs with -fsyntax-only; existing build artifacts stay unchanged.
No serial connection, upload target, linker or image generation is used.
"""

import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

from app_registry import ROOT

PROJECT = ROOT / "runtime/apps/wireless-remote/core2"
BUILD = ROOT / "work/core2-remote-build"


def compiled_artifacts():
    result = {}
    for path in BUILD.rglob("*"):
        if path.is_file() and path.suffix in (".o", ".a", ".bin", ".elf", ".d"):
            stat = path.stat()
            result[path.relative_to(ROOT).as_posix()] = [stat.st_size, stat.st_mtime_ns]
            if path.suffix in (".bin", ".elf"):
                result[path.relative_to(ROOT).as_posix()].append(hashlib.sha256(path.read_bytes()).hexdigest())
    return result


def windows_arguments(command):
    """Use the Windows quoting rules used by the real compiler invocation."""
    api = ctypes.windll.shell32.CommandLineToArgvW
    api.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_int)]
    api.restype = ctypes.POINTER(ctypes.c_wchar_p)
    count = ctypes.c_int()
    values = api(command, ctypes.byref(count))
    if not values:
        raise ValueError("Invalid compiler command")
    try:
        return [values[index] for index in range(count.value)]
    finally:
        free = ctypes.windll.kernel32.LocalFree
        free.argtypes = [ctypes.c_void_p]
        free.restype = ctypes.c_void_p
        free(ctypes.cast(values, ctypes.c_void_p))


def syntax_arguments(arguments):
    result = [arguments[0]]
    paired = {"-o", "-MF", "-MT", "-MQ"}
    skip = False
    for value in arguments[1:]:
        if skip:
            skip = False
        elif value in paired:
            skip = True
        elif value in ("-c", "-MD", "-MMD", "-MP", "-MG"):
            continue
        elif any(value.startswith(flag) for flag in paired):
            continue
        elif value.startswith("@") or value in ("-save-temps", "-save-temps=obj"):
            raise ValueError("Unreviewed compiler output/response-file option: " + value)
        else:
            result.append(value)
    if skip:
        raise ValueError("Missing compiler option argument")
    result.append("-fsyntax-only")
    return result


def load_command(database):
    entries = json.loads(database.read_text(encoding="utf-8"))
    if not isinstance(entries, list):
        raise ValueError("Expected a compilation database array")
    matches = [entry for entry in entries if
               (Path(entry["directory"]) / entry["file"]).resolve() ==
               (PROJECT / "src/main.cpp").resolve()]
    if len(matches) != 1:
        raise ValueError("Expected one actual Core2 frontend command")
    entry = matches[0]
    if Path(entry["directory"]).resolve() != PROJECT.resolve():
        raise ValueError("Compilation directory does not match the Core2 project")
    command = syntax_arguments(windows_arguments(entry["command"]))
    compiler = Path(command[0])
    if "g++" not in compiler.name or not compiler.is_file():
        raise ValueError("Expected the configured cross C++ compiler")
    return entry, command


def check(database):
    if os.name != "nt":
        raise RuntimeError("This cached Core2 compiler profile uses Windows")
    if not database.is_file():
        raise FileNotFoundError(database)
    entry, command = load_command(database)
    out = ROOT / "work/core2-syntax" / str(time.time_ns())
    out.mkdir(parents=True)
    (out / "compile_commands.json").write_bytes(database.read_bytes())
    version = (PROJECT / "VERSION").read_text().strip()
    generated = out / "remote_version.h"
    generated.write_text("#define XW_REMOTE_VERSION " + json.dumps(version) + "\n",
                         encoding="utf-8")
    # Select the current source version without rewriting the cached build tree.
    command.insert(1, "-I" + str(out))
    compiler = Path(command[0])
    before = compiled_artifacts()
    try:
        with (out / "syntax.log").open("w", encoding="utf-8") as log:
            result = subprocess.run(command, cwd=entry["directory"],
                                    stdout=log, stderr=subprocess.STDOUT)
    finally:
        after = compiled_artifacts()
        changed = sorted(name for name in set(before) | set(after)
                         if before.get(name) != after.get(name))
        firmware_created = any(name in after and Path(name).suffix in (".bin", ".elf")
                               for name in changed)
        guard = {"passed": not changed, "changed_artifacts": changed,
                 "firmware_created": firmware_created,
                 "compilation_database_unchanged":
                 database.read_bytes() == (out / "compile_commands.json").read_bytes()}
        (out / "artifact-guard.json").write_text(json.dumps(guard, indent=2) + "\n")
        if changed or not guard["compilation_database_unchanged"]:
            raise RuntimeError("Syntax-only artifact guard failed; see " + str(out))
    inputs = [PROJECT / "src/main.cpp", PROJECT / "platformio.ini",
              PROJECT / "build_protocol.py", PROJECT / "VERSION", Path(__file__)]
    inputs = sorted(set(inputs) | set(PROJECT.parent.glob("*.h")) |
                    set((PROJECT / "src").glob("*.h")))
    report = {
        "passed": result.returncode == 0,
        "source_version": version,
        "syntax_exit_code": result.returncode,
        "existing_artifacts_unchanged": not changed,
        "existing_artifacts_checked": len(before),
        "device_accessed": False, "firmware_created": firmware_created,
        "hardware_qualified": False, "platformio_invoked": False,
        "compiler": str(compiler),
        "compiler_sha256": hashlib.sha256(compiler.read_bytes()).hexdigest(),
        "compilation_database_sha256": hashlib.sha256(database.read_bytes()).hexdigest(),
        "generated_version_sha256": hashlib.sha256(generated.read_bytes()).hexdigest(),
        "command": command,
        "source_hashes": {path.relative_to(ROOT).as_posix():
                          hashlib.sha256(path.read_bytes()).hexdigest() for path in inputs},
    }
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"passed": report["passed"], "review": out.relative_to(ROOT).as_posix(),
                      "existing_artifacts_unchanged": not changed,
                      "firmware_created": firmware_created}, indent=2))
    return 0 if report["passed"] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True,
                        help="Existing compile_commands.json; PlatformIO is never invoked")
    args = parser.parse_args()
    return check(args.database.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
