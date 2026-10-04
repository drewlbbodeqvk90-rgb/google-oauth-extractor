# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build recipe for the Google OAuth Token Extractor Toolkit.

Produces a single-file Windows executable -- dist/goe.exe --
with CPython, the toolkit's three scripts and every third-party dependency
(requests, pycryptodome, pywin32) embedded. This is the Python analogue of a
Node `nexe` / `pkg` binary; see docs/PACKAGING_PYTHON_CLI.md sections 1 and 4.

Build (from the project root, or anywhere -- paths are anchored to SPECPATH):

    pyinstaller --noconfirm goe.spec
    # or simply:
    python build_exe.py

Notes
-----
* ``pyz/__main__.py`` is the single entry point, shared with the .pyz build.
* The three command modules are imported *dynamically* by the dispatcher
  (``importlib.import_module``), which static analysis cannot see. That is
  exactly what ``hiddenimports`` is for -- PACKAGING_PYTHON_CLI.md section 1.
* ``upx=False``: UPX compression is heavily represented in malware signatures
  and triggers antivirus false positives -- PACKAGING_PYTHON_CLI.md section 9.
* ``--onefile`` self-extracts to %TEMP% on every launch. For faster startup and
  fewer AV false positives, build --onedir instead (drop ``a.binaries`` /
  ``a.datas`` from EXE() and add a COLLECT step).
"""

import os

ROOT = SPECPATH  # directory containing this spec (injected by PyInstaller)



a = Analysis(
    [os.path.join(ROOT, 'pyz', '__main__.py')],
    pathex=[ROOT],
    binaries=[],
    datas=[],
    hiddenimports=[
        # Imported dynamically by the dispatcher -- invisible to the analyzer.
        'extract_tokens_windows',
        'test_token',
        'token_to_session',
        # DPAPI entry point used by the extraction path.
        'win32crypt',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'test', 'numpy', 'matplotlib', 'PIL', 'IPython', 'pytest'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='goe',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
