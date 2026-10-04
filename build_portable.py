#!/usr/bin/env python3
"""Build the self-contained "portable" bundle: embedded Python + deps + goe.pyz.

Outputs:
    dist/goe-portable/       python\\python.exe + Lib\\site-packages + goe.pyz + goe.cmd
    dist/goe-portable.zip    the same folder, zipped for transfer

Why this exists
---------------
The program Windows actually launches is ``python.exe``, which is Authenticode
signed by the Python Software Foundation. SmartScreen and Smart App Control
then evaluate a signed, well-known interpreter instead of an unsigned
single-file binary, and nothing self-extracts into %TEMP%. See
``docs/PACKAGING_PYTHON_CLI.md`` sections 8 and 10.

Pinned to Python 3.13.15 embeddable on purpose: it matches the dev venv, so the
cp313 wheels are exactly the ones already proven to work here.

Usage:
    python build_portable.py             # build + zip + self-test
    python build_portable.py --clean     # remove dist/goe-portable first
    python build_portable.py --no-zip    # skip the transfer archive
"""

import argparse
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# --- pinned embeddable release -------------------------------------------------
PY_VERSION = "3.13.15"
PY_ABI = "313"
EMBED_ZIP = f"python-{PY_VERSION}-embed-amd64.zip"
EMBED_URL = f"https://www.python.org/ftp/python/{PY_VERSION}/{EMBED_ZIP}"
EMBED_SIZE = 11009825  # bytes, from python.org - sanity check on the download

# --- paths --------------------------------------------------------------------
BUNDLE = ROOT / "dist" / "goe-portable"
PYDIR = BUNDLE / "python"
SITE = PYDIR / "Lib" / "site-packages"
PYZ = ROOT / "dist" / "goe.pyz"
ZIP_OUT = ROOT / "dist" / "goe-portable.zip"
REQ = ROOT / "requirements.txt"
SRC = ROOT / "portable"          # goe.cmd + README.txt live here, copied in
CACHE = Path.home() / "Downloads"


def ensure_embed_zip():
    """Return the embeddable zip, downloading it once into ~/Downloads."""
    target = CACHE / EMBED_ZIP
    if target.is_file() and target.stat().st_size == EMBED_SIZE:
        print(f"[+] cached   {target} ({EMBED_SIZE:,} bytes)")
        return target
    if target.is_file():
        print(f"[!] size mismatch on {target.name} - re-downloading")
    print(f"[*] downloading {EMBED_URL}")
    CACHE.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(EMBED_URL, timeout=120) as resp, \
            open(target, "wb") as fh:
        shutil.copyfileobj(resp, fh)
    got = target.stat().st_size
    if got != EMBED_SIZE:
        raise SystemExit(f"error: size mismatch: got {got}, expected {EMBED_SIZE}")
    print(f"[+] downloaded {target.name} ({got:,} bytes)")
    return target


def extract_embed(zip_path):
    """Unpack the embeddable distribution into dist/goe-portable/python/."""
    if PYDIR.exists():
        shutil.rmtree(PYDIR)
    PYDIR.mkdir(parents=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(PYDIR)
    print(f"[+] extracted {len(list(PYDIR.iterdir()))} files -> python/")


def install_deps():
    """Install the runtime deps into the embed's Lib\\site-packages.

    Uses the running interpreter's pip with an explicit target spec, so the
    fetch is for cp313/win_amd64 regardless of how the host is configured.
    """
    SITE.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable, "-m", "pip", "install",
        "--target", str(SITE),
        "--only-binary=:all:",
        "--platform", "win_amd64",
        "--implementation", "cp",
        "--python-version", "3.13",
        "--abi", f"cp{PY_ABI}",
        "-r", str(REQ),
    ]
    print("[*] " + " ".join(cmd))
    rc = subprocess.call(cmd)
    if rc != 0:
        raise SystemExit(f"error: pip exited {rc}")


def patch_pth():
    """Enable site + site-packages in pythonXXX._pth.

    site.main() is mandatory here: it is what processes pywin32.pth, which adds
    win32\\lib to sys.path and runs pywin32_bootstrap -- the bootstrap registers
    pywin32_system32 so pywintypesXXX.dll is findable by win32crypt.pyd.
    Without it, `import win32crypt` fails with a DLL load error.
    """
    pth = PYDIR / f"python{PY_ABI}._pth"
    if not pth.is_file():
        raise SystemExit(f"error: {pth.name} missing from the embed distribution")
    lines = [
        f"python{PY_ABI}.zip",
        ".",
        r"Lib\site-packages",
        "",
        "# site.main() must run: it puts Lib\\site-packages on sys.path and, via",
        "# pywin32.pth, adds win32\\lib and runs pywin32_bootstrap, which registers",
        f"# pywin32_system32 so pywintypes{PY_ABI}.dll is findable by win32crypt.pyd.",
        "import site",
        "",
    ]
    pth.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print(f"[+] patched  {pth.name} (site enabled, site-packages listed)")


def copy_payload():
    """Place goe.pyz inside the python\\ folder and the launcher at the root."""
    if not PYZ.is_file():
        print("[*] dist/goe.pyz missing - building it first")
        import build_pyz
        build_pyz.build()
    shutil.copy2(PYZ, PYDIR / "goe.pyz")
    for name in ("goe.cmd", "README.txt"):
        shutil.copy2(SRC / name, BUNDLE / name)
    print("[+] copied   python\\goe.pyz, goe.cmd, README.txt")


def make_transfer_zip():
    """Zip the bundle, with entries relative to its root."""
    if ZIP_OUT.exists():
        ZIP_OUT.unlink()
    count = 0
    with zipfile.ZipFile(ZIP_OUT, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for path in sorted(BUNDLE.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(BUNDLE))
                count += 1
    print(f"[+] zipped   dist/goe-portable.zip  "
          f"({count} files, {ZIP_OUT.stat().st_size / 1024 / 1024:.1f} MiB)")


def self_test():
    """Exercise the built bundle the way a user would."""
    py = PYDIR / "python.exe"
    pyz = PYDIR / "goe.pyz"
    launcher = BUNDLE / "goe.cmd"
    results = []

    rc = subprocess.call([str(py), "-c",
                          "import win32crypt, Crypto.Cipher.AES, requests, "
                          "sqlite3, ssl, hashlib"])
    results.append(("imports (win32crypt/Crypto/requests/sqlite3/ssl)", rc == 0))

    rc = subprocess.call([str(py), str(pyz), "--version"])
    results.append(("python.exe + goe.pyz --version", rc == 0))

    rc = subprocess.call([str(py), str(pyz), "extract", "--help"],
                         stdout=subprocess.DEVNULL)
    results.append(("goe.pyz extract --help", rc == 0))

    if launcher.is_file():
        rc = subprocess.call(["cmd", "/c", str(launcher), "extract", "--help"],
                             stdout=subprocess.DEVNULL)
        results.append(("goe.cmd extract --help (launcher)", rc == 0))

    ok = True
    for label, passed in results:
        print(f"    {'ok  ' if passed else 'FAIL'} {label}")
        ok = ok and passed
    return ok


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Build the portable (embedded-Python) bundle."
    )
    parser.add_argument("--clean", action="store_true",
                        help="remove dist/goe-portable before building")
    parser.add_argument("--no-zip", action="store_true",
                        help="skip the transfer .zip")
    args = parser.parse_args(argv)

    if sys.version_info[:2] != (3, 13):
        print(f"error: run this with CPython 3.13 (current: "
              f"{sys.version.split()[0]}) - the cp{PY_ABI} wheels are fetched "
              f"for the target, so the host must match.", file=sys.stderr)
        return 1

    if args.clean and BUNDLE.exists():
        shutil.rmtree(BUNDLE)
        print("[+] cleaned  dist/goe-portable")

    embed = ensure_embed_zip()
    extract_embed(embed)
    install_deps()
    patch_pth()
    copy_payload()
    if not args.no_zip:
        make_transfer_zip()

    print("\n[*] self-test")
    if not self_test():
        print("error: self-test failed", file=sys.stderr)
        return 1

    size = sum(p.stat().st_size for p in BUNDLE.rglob("*") if p.is_file())
    print(f"\n[+] Built dist/goe-portable  ({size / 1024 / 1024:.1f} MiB)")
    print("    run:  dist\\goe-portable\\goe.cmd --help")
    return 0


if __name__ == "__main__":
    sys.exit(main())

