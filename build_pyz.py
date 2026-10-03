#!/usr/bin/env python3
"""Build a single-file zipapp (.pyz) of the toolkit.

Stages the toolkit's three scripts together with the dispatcher
(``pyz/__main__.py``) into a clean build directory, then packs the whole thing
into one ``.pyz`` using the stdlib ``zipapp`` module — no third-party build
dependencies, no bootloader, no temp extraction.

See ``docs/PACKAGING_PYTHON_CLI.md`` (section 7) for why zipapp is the right
fit here: the target machine already has Python, and a plain ``.pyz`` is just a
zip archive with a shebang.

Usage:
    python build_pyz.py                 # -> dist/google_oauth_extractor.pyz
    python build_pyz.py -o out/tool.pyz
    python build_pyz.py --compressed    # smaller archive, a few ms slower start

Third-party packages (requests, pywin32, pycryptodome) are intentionally NOT
bundled; install them on the target with ``pip install -r requirements.txt``.
"""

import argparse
import shutil
import sys
import zipapp
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# Top-level scripts copied verbatim into the archive root.
SCRIPTS = [
    "extract_tokens_windows.py",
    "test_token.py",
    "token_to_session.py",
]

# Dispatcher; must land at the archive root as __main__.py.
ENTRY = Path("pyz") / "__main__.py"

STAGE_REL = Path("build") / "pyz_app"
DEFAULT_OUTPUT_REL = Path("dist") / "google_oauth_extractor.pyz"

# POSIX shebang makes the .pyz directly runnable after chmod +x; on Windows it
# is ignored and the file is run via `py file.pyz`.
INTERPRETER = "/usr/bin/env python3"


def _resolve(path):
    """Resolve a path relative to the project root (absolute paths pass through)."""
    path = Path(path)
    return path if path.is_absolute() else (ROOT / path)


def build(output=DEFAULT_OUTPUT_REL, compressed=False):
    """Stage the sources and pack them into a single .pyz. Returns the archive path."""
    stage = ROOT / STAGE_REL
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)

    entry_src = ROOT / ENTRY
    if not entry_src.is_file():
        raise SystemExit(f"error: missing entry point: {entry_src}")
    shutil.copy2(entry_src, stage / "__main__.py")

    for name in SCRIPTS:
        src = ROOT / name
        if not src.is_file():
            raise SystemExit(f"error: missing script: {src}")
        shutil.copy2(src, stage / name)

    output = _resolve(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()

    zipapp.create_archive(
        stage,
        target=output,
        interpreter=INTERPRETER,
        compressed=compressed,
    )
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Pack the toolkit into a single-file .pyz (stdlib zipapp)."
    )
    parser.add_argument(
        "-o", "--output", default=str(DEFAULT_OUTPUT_REL),
        help=f"output .pyz path (default: {DEFAULT_OUTPUT_REL.as_posix()})",
    )
    parser.add_argument(
        "--compressed", action="store_true",
        help="deflate the archive (smaller file, slightly slower startup)",
    )
    args = parser.parse_args(argv)

    output = build(args.output, args.compressed)

    size_kb = output.stat().st_size / 1024
    print(f"[+] Built {output}")
    print(f"    size:        {size_kb:.1f} KiB")
    print(f"    files:       {', '.join(['__main__.py'] + SCRIPTS)}")
    print(f"    compressed:  {args.compressed}")
    print(f"    interpreter: {INTERPRETER}")
    print("")
    print("Run it with:")
    print(f"    py {output.name} --help")
    print(f"    py {output.name} test --help")
    print("")
    print("Reminder: requests / pywin32 / pycryptodome are not bundled - the")
    print("target machine needs: pip install -r requirements.txt")
    return 0


if __name__ == "__main__":
    sys.exit(main())