#!/usr/bin/env python3
"""Build the standalone Windows executable via PyInstaller.

Wraps the committed PyInstaller recipe (``goe.spec``) so the
recipe -- not a shell history -- is the source of truth (see
``docs/PACKAGING_PYTHON_CLI.md`` section 4).

The result, ``dist/goe.exe``, is a single file containing
CPython plus every dependency, so it runs on a machine with no Python at all --
the Python analogue of a Node ``nexe`` binary.

Build from a pinned virtualenv so the freezer bundles exactly the declared
dependencies and nothing else (PACKAGING_PYTHON_CLI.md section 9):

    python -m venv .venv-build
    .venv-build\\Scripts\\python -m pip install -r requirements.txt pyinstaller
    .venv-build\\Scripts\\python build_exe.py --clean

Usage:
    python build_exe.py             # -> dist\\goe.exe
    python build_exe.py --clean     # wipe build/ + the previous .exe first
    python build_exe.py --run       # smoke-test the exe afterwards
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SPEC = ROOT / "goe.spec"
EXE = ROOT / "dist" / "goe.exe"
WORK_DIR = ROOT / "build" / "goe"


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Build the single-file .exe with PyInstaller."
    )
    parser.add_argument(
        "--clean", action="store_true",
        help="remove build/ and the previous .exe before building"
    )
    parser.add_argument(
        "--run", action="store_true",
        help="run the built .exe --help afterwards as a smoke test"
    )
    args = parser.parse_args(argv)

    if not SPEC.is_file():
        print(f"error: spec not found: {SPEC}", file=sys.stderr)
        return 1

    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("error: PyInstaller is not installed for this interpreter.",
              file=sys.stderr)
        print("  install it, preferably in a pinned venv:", file=sys.stderr)
        print("    python -m venv .venv-build", file=sys.stderr)
        print("    .venv-build/Scripts/python -m pip install "
              "-r requirements.txt pyinstaller", file=sys.stderr)
        return 1

    if args.clean:
        shutil.rmtree(WORK_DIR, ignore_errors=True)
        if EXE.exists():
            EXE.unlink()
        print(f"[+] cleaned {WORK_DIR}")
        print(f"[+] removed {EXE}")

    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", str(SPEC)]
    print("[*] " + " ".join(cmd))
    rc = subprocess.call(cmd, cwd=str(ROOT))
    if rc != 0:
        print(f"error: PyInstaller exited with {rc}", file=sys.stderr)
        return rc

    if not EXE.is_file():
        print(f"error: PyInstaller reported success but {EXE} is missing",
              file=sys.stderr)
        return 1

    print(f"\n[+] Built {EXE}")
    print(f"    size:     {EXE.stat().st_size / 1024 / 1024:.2f} MiB")
    print("    contains: CPython + requests + pycryptodome + pywin32")
    print(f"    recipe:   {SPEC.name}")
    print("")
    print("Run it with:")
    print(f"    {EXE.name} --help")
    print(f"    {EXE.name} extract --all-browsers")

    if args.run:
        print("\n[*] smoke test: --help")
        return subprocess.call([str(EXE), "--help"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
