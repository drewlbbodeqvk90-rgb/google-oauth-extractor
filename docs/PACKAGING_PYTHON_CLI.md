# Packaging Python CLI Tools as Standalone Artifacts

> Reference notes on bundling a multi-script Python command-line tool so it can
> be handed to another machine. Covers the mainstream freezers, the zipapp
> family, and the embedded-interpreter approach — plus the failure modes that
> only show up *after* you build.

---

## 1. Why Python has no exact `nexe` equivalent

`nexe`, `pkg`, and `deno compile` are simple because Node ships **one**
embeddable runtime and your program is plain JavaScript — there is nothing to
compile across the boundary.

Python is messier, and that shapes every tool in this space:

- **C extensions.** Packages like `cryptography`, `lxml`, `numpy`, or
  `pywin32` are compiled `.pyd`/`.so` binaries, not Python source. A packager
  must locate and ship them, and it cannot always tell *statically* that they
  are needed.
- **Data files.** Many packages ship non-code payloads — CA bundles, JSON
  schemas, compiled translation catalogues. An import scanner never sees these.
- **Dynamic imports.** `importlib`, plugin systems, and `__import__` calls
  defeat static analysis. This is the entire reason `--hidden-import` exists.
- **The interpreter itself.** You are shipping CPython, not linking it away.

Practical consequence: a Python "onefile exe" is **not** a compiled binary the
way a Go or Rust binary is. It is a launcher with an embedded interpreter and a
compressed archive bolted on beside it.

## 2. The axis that decides everything

Before comparing tools, answer one question:

> **Does the target machine already have a Python interpreter installed?**

That single fact splits the field cleanly, and it is the difference between a
tiny artifact you produce in ten seconds and a 15 MB build with a hand-tuned
spec file and an antivirus conversation.

## 3. Comparison

| Approach | Target needs Python? | Output | Build cost | Notes |
|---|---|---|---|---|
| **PyInstaller** | No | `.exe` + bundled CPython | Seconds | De-facto standard; automatic hooks; `--onefile` self-extracts to `%TEMP%` |
| **Nuitka** | No | True native binary | Minutes–hours | Transpiles to C, then compiles; fastest runtime, least readable binary |
| **cx_Freeze** | No | `.exe` + library folder | Seconds | Mature, but fewer automatic hooks than PyInstaller |
| **py2exe** | No | `.exe` | Seconds | Windows-only; long dormant stretches; niche today |
| **zipapp / shiv / pex** | **Yes** | single `.pyz` | Instant | `zipapp` is stdlib — zero build dependencies |
| **Embedded interpreter** | No (you ship it) | folder/zip + launcher | Manual | No freezer involved; full control over layout |

---

## 4. PyInstaller

The usual default. It analyses your entry script, follows imports, and emits a
bootloader executable plus a bundle holding CPython, your bytecode, and the
collected dependencies.

```bash
pip install pyinstaller
pyinstaller --onefile --console --name mytool mytool.py
```

What it leaves behind:

```
build/            # intermediate analysis + collected files (disposable)
dist/mytool.exe   # the artifact you ship
mytool.spec       # generated build recipe — commit this
```

Once you have tuned the flags, rebuild from the spec (`pyinstaller
mytool.spec`) so your configuration does not live only in your shell history.

### onefile vs onedir

- **`--onedir`** — a folder containing `mytool.exe` plus `_internal/`. Starts
  fast, no temp extraction, and is markedly less likely to be quarantined.
- **`--onefile`** — one file to move around. At *every* launch the bootloader
  **extracts the entire bundle to `%TEMP%\_MEIxxxxxx`**, runs from there, and
  deletes it on exit. Costs: slower cold start, no caching between runs, and
  behaviour that resembles a dropper to endpoint security.

For anything you actually hand to other people, `--onedir` plus a zip is
usually the lower-friction choice.

### Locating bundled resources

At runtime `sys._MEIPASS` points at the bundle root:

```python
import sys
from pathlib import Path

BASE = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
config = BASE / "data" / "defaults.json"
```

### The flags that fix most "works in dev, breaks when frozen" bugs

```bash
pyinstaller --onefile \
  --hidden-import=some_native_module \   # invisible to static analysis
  --collect-data=certifi \               # data files, not code
  --collect-submodules=myplugin_pkg \    # plugin-style packages
  yourscript.py
```

- **`--hidden-import`** — for modules reached only through dynamic import, and
  for C extensions that static analysis walks straight past. Packages wrapping
  native DLLs (pywin32 and friends) are recurring offenders, as are
  `pkg_resources`-driven entry points.
- **`--collect-data` / `--collect-all`** — for packages whose *files* matter,
  not just their importable code.
- **`--add-data "src;dest"`** — mind the separator: **`;` on Windows**, `:` on
  POSIX. This trips people up constantly in cross-platform build scripts.
- **`--paths DIR`** — extra import search roots for unusual layouts.

### Other knobs worth knowing

| Flag | Effect |
|---|---|
| `--console` / `--windowed` (`--noconsole`) | Keep or suppress the console window |
| `--name` | Output binary name |
| `--icon app.ico` | Executable icon |
| `--exclude-module X` | Shrink the bundle by dropping unused dependencies |
| `--clean` | Discard cached analysis — reach for this when a build goes strange |
| `--upx-dir` | UPX-compress binaries (**note: raises AV false-positive rates**) |

---

## 5. Nuitka

Nuitka does something categorically different: it **transpiles your Python to
C** and compiles that with a real C compiler, linking against CPython.

```bash
pip install nuitka
python -m nuitka --standalone --onefile --enable-plugin=tk-inter mytool.py
```

- **`--standalone`** — ship the interpreter and every dependency alongside.
- **`--onefile`** — single binary that self-extracts, same tradeoff as
  PyInstaller.
- **`--enable-plugin=`** — how you handle toolkits that need special
  treatment (`tk-inter`, `numpy`, `pyside6`, ...).

**When it is worth it:** you want genuinely faster execution, or the least
readable artifact of the bunch. Compiled code is substantially harder to
decompile than `.pyc`.

**What it costs:** build times go from seconds to minutes or hours; you need a
working MSVC or gcc toolchain; and its plugin system occasionally needs
coaxing for packages PyInstaller handles silently. Validate the artifact twice
as carefully — the failure modes are less familiar.

---

## 6. cx_Freeze

A middle ground: simpler than Nuitka, more explicit than PyInstaller. It is
driven either by a `setup.py`-style `build_exe_options` dict or by the
`cxfreeze` command.

```bash
pip install cx_Freeze
cxfreeze --target-dir dist mytool.py
```

Configuration lives in a `setup.py`-ish file, which some teams prefer to a
`.spec` because it is ordinary Python they can read and diff:

```python
from cx_Freeze import setup, Executable

setup(
    name="mytool",
    options={"build_exe": {"packages": ["win32crypt"], "excludes": ["tkinter"]}},
    executables=[Executable("mytool.py", base=None)],  # base="gui" for no console
    version="1.0",
)
```

It emits an `.exe` plus a library folder — effectively an always-`--onedir`
model. Reach for it if PyInstaller's hooks misbehave on your dependencies and
you would rather declare things by hand.

---

## 7. zipapp / shiv / pex — when the target already has Python

If the machine has an interpreter, you need no freezer at all. A `.pyz` is just
a zip archive with a shebang that CPython executes directly.

```
mytool/
  __main__.py         # required entry point
  mytool/
    __init__.py
    commands/
      __init__.py
      extract.py
      verify.py
```

```bash
# Everything inside mytool/ becomes the archive root
python -m zipapp mytool -o mytool.pyz -p "/usr/bin/env python3"

python mytool.pyz --help     # runs anywhere Python is installed
py mytool.pyz --help         # Windows, via the py launcher
```

Practical points:

- **`__main__.py` must sit at the archive root.** That is where execution
  starts; everything else is imported relative to it.
- **Zero build dependencies.** `zipapp` is stdlib. No wheel, no bootloader, no
  compiler, no build step to keep working — rebuild is one command.
- **Third-party packages are *not* included.** A plain `zipapp` archives only
  your source; anything from PyPI must already be installed on the target.
  `shiv` and `pex` exist to close exactly that gap by vendoring `site-packages`
  into the archive.
- **The `-p` shebang** makes the file directly runnable on POSIX after
  `chmod +x`; on Windows you associate `.pyz` with `py.exe` or invoke it
  explicitly through the launcher.
- **It is a packaging format, not a protection format.** The archive is plain
  zip, source and `.pyc` are trivially extractable, and `.pyc` is
  decompilable. Never treat a `.pyz` as an obfuscation boundary.
- **Startup is honest.** No self-extraction, no temp directory, no first-run
  delay — Python reads the zip lazily.

If you have several separate scripts, the usual move is to consolidate them
behind **one entry point** with subcommands (`mytool extract`, `mytool verify`)
before packaging. Freezers and zipapp both want a single entry, and you end up
with one dispatch table instead of N binaries.

---

## 8. Embedded interpreter — manual, but total control

python.org publishes a **Windows embeddable package**: a zip containing
`python.exe`, `python3xx.dll`, and a stdlib archive. No installer, no registry
writes, no `pip`.

```
mytool/
  python/        # unzipped embeddable distribution
  mytool/        # your package
  mytool.pyz
  run.cmd
```

```bat
@echo off
"%~dp0python\python.exe" "%~dp0mytool.pyz" %*
```

Details that matter:

- **`python3xx._pth`** controls `sys.path`, and critically whether
  `site-packages` is honoured at all. Editing it is how you expose vendored
  dependencies.
- **No pip by default.** Either add it deliberately, or drop pure-Python wheels
  into the folder and extend `._pth`.
- **No bootloader, no compression, no temp extraction.** Predictable startup
  and far fewer antivirus surprises than `--onefile`.
- **The dependency resolution is entirely yours** — this is the work the
  freezers automate, and the reason to prefer them unless you specifically
  need the control.

### Real-world notes (from the `goe` portable bundle)

The embeddable distribution is **more complete than it looks** and easier to use
than its reputation suggests:

- **The stdlib it needs is present.** The zip ships `_sqlite3.pyd` *and*
  `sqlite3.dll`, `_ssl.pyd` with `libssl-3.dll`/`libcrypto-3.dll`, `_socket.pyd`,
  `select.pyd`, `_hashlib.pyd` and `unicodedata.pyd`, so a `sqlite3` + HTTPS
  workload runs out of the box — no manually dropped DLLs required.
- **`import site` in `pythonXXX._pth` is mandatory, not optional.** With a
  `._pth` file present `site` does not run by default, and therefore no `.pth`
  file is ever processed. `pywin32` depends on exactly that: its `pywin32.pth`
  adds `win32\lib` to `sys.path` and runs `import pywin32_bootstrap`, which is
  what registers `pywin32_system32` so `pywintypesNNN.dll` is findable by
  `win32crypt.pyd`. Leave `site` disabled and the failure is a DLL-load error,
  not a missing-module error — a much less obvious symptom.
- **You do not need pip inside the distribution.** Install from the outside:

  ```bat
  .venv-build\Scripts\python -m pip install --target python\Lib\site-packages ^
      --only-binary=:all: --platform win_amd64 --implementation cp ^
      --python-version 3.13 --abi cp313 -r requirements.txt
  ```

  `pip` permits `--platform`/`--python-version`/`--implementation`/`--abi` only
  together with `--target` (or `--dry-run`), and requires `--only-binary=:all:`.
- **The bundled `python.exe` is Authenticode-signed** by the Python Software
  Foundation — an embedded signature, not merely the `python.cat` catalog
  sibling. Verify it on the *extracted* copy, because that is what a user runs.
- **Prefer an `abi3` wheel when one exists.** `pycryptodome` publishes
  `cp37-abi3-win_amd64`, so it installs on any CPython >= 3.7 — including
  versions that have no version-specific wheel yet. `pywin32` ships
  version-specific wheels (`cp313`, `cp314`, …), so it pins you harder.
- **Size is honest.** 49.5 MiB folder / 23.3 MiB zip for this toolkit; the
  interpreter plus OpenSSL alone is ~12 MiB. Pruning unused `.pyd`s and unused
  `pywin32` subpackages is possible, but every deletion is a runtime risk, so
  it should be opt-in.
- **Quote `%~dp0` in the launcher**, because the bundle gets run from paths
  containing spaces: `"%~dp0python\python.exe" "%~dp0python\goe.pyz" %*` needs
  no `PATH` at all.

---

## 9. Cross-cutting concerns

**One entry point.** Every option above works best with a single entry script
or `__main__.py`. Multi-script tools should grow an argparse dispatcher first
and get packaged second.

**Runtime file lookups.** Code that does `open("config.json")` relative to the
source tree will break once frozen. Anchor every path to `sys._MEIPASS`
(PyInstaller) or the module's own directory, never to the CWD. This is the
single most common post-build breakage.

**Pin your build environment.** Build from a clean, pinned virtualenv. A
freezer bundles *whatever happens to be importable*, so a polluted global
environment silently inflates your artifact and can drag in a package that
conflicts at runtime.

**Expect real size.** Budget ~10–15 MB for a trivial script, and considerably
more once `requests`, `numpy`, or a GUI toolkit arrives. If the size alarms
you, `--exclude-module` the things you know you do not use.

**No cross-compiling.** You cannot produce a Windows `.exe` from Linux with
PyInstaller or Nuitka. Build on (or CI on) every platform you intend to ship.
GitHub Actions' `windows-latest` / `macos-latest` / `ubuntu-latest` matrix is
the standard answer.

**Code signing (Windows).** SmartScreen's "unrecognised app" warning is driven
by **Mark-of-the-Web**, not by being unsigned per se. A binary you just built
locally has no MOTW and will normally run without a prompt — which is why the
warning appears for the *recipient* but not for the developer. A binary that
arrived by download, email attachment, or network share does carry MOTW, and an
unsigned, zero-reputation one will prompt. Signing is what actually fixes that —
not compression tweaks. You need an Authenticode certificate and `signtool`:

```bat
signtool sign /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 mytool.exe
```

**Antivirus false positives.** PyInstaller's bootloader and UPX compression are
both heavily represented in malware signatures, so legitimate tools get
quarantined surprisingly often. Fixes that genuinely help: prefer `--onedir`,
drop UPX, sign the binary, and submit false-positive reports to the vendors.
There is no configuration that makes this problem disappear.

**Keep build output out of version control** — `build/`, `dist/` — while
committing the `.spec` or `setup.py` that reproduces the build.

---

## 10. Windows trust: MOTW, SmartScreen and Smart App Control

Before picking between a freezer and `zipapp`, know that on Windows *"will this
run?"* is decided by **three separate mechanisms**, and they do not care about
the same things.

### Mark-of-the-Web → SmartScreen

When a file arrives from the internet — browser download, email attachment, a
UNC/network path, or a zip extracted from one — Windows attaches a
`Zone.Identifier` alternate data stream. That is the Mark-of-the-Web (MOTW).

**SmartScreen is driven by MOTW, not by being unsigned.** A binary you just
built locally has no MOTW, so SmartScreen never evaluates it and it runs with
no prompt. The *same* binary, once it reaches someone else by download, does
carry MOTW — and an unsigned binary with no reputation gets the full-screen
"Windows protected your PC" dialog.

```powershell
# Does this file carry MOTW?  (only ':$DATA' => no MOTW)
Get-Item .\mytool.exe -Stream *

# Strip MOTW — same as the Properties -> Unblock checkbox
Unblock-File .\mytool.exe
```

This is the classic *works for the developer, warns for the recipient* split. It
is expected behaviour, not a sign your build is broken.

### Smart App Control — applies to local builds too

SAC is the exception to everything above: it evaluates **every** application
image, MOTW or not, including one you compiled on the machine yourself. It
weighs the image against Microsoft's reputation service and blocks what it
cannot vouch for.

```
HKLM\SYSTEM\CurrentControlSet\Control\CI\Policy
    VerifiedAndReputablePolicyState    0 = off,  1 = enforced,  2 = evaluation
```

In **evaluation** mode it observes and allows; in **enforced** mode an unsigned,
unknown `.exe` is simply blocked. Signing the binary — or turning SAC off — is
the only way through.

### Why a `.pyz` sidesteps both

A `.pyz` is not a PE image. It is a zip archive passed as an *argument* to
`python.exe`, so the executable Windows evaluates and reputation-checks is the
**signed, well-known interpreter**, not your artifact:

- **SmartScreen** — the launched image is `python.exe` (validly signed by the
  Python Software Foundation, or by Microsoft for a Store install), which has
  reputation. The archive is data.
- **Smart App Control** — same story: the image subject to code-integrity
  evaluation is the signed interpreter, so it is allowed.
- **Antivirus** — no PyInstaller bootloader and no self-extraction into
  `%TEMP%`, which are precisely the behaviours heuristics associate with
  "extract-and-execute".

Two caveats. First, this only holds if the target's interpreter is itself a
signed, reputable build — ship a hacked-together portable `python.exe` and you
have recreated the problem. Second, `.pyz` is a plain zip: the trust advantage
is about *launching*, not about hiding code (section 7).

---

## 11. Verifying the artifact

The golden rule: **test the artifact, not the source tree.** A build that runs
from `python tool.py` tells you almost nothing about `dist/tool.exe`.

1. **Run on a machine with no Python installed.** The only test that actually
   proves the bundle is self-contained. A clean VM or container beats trusting
   your dev box.
2. **Exercise every subcommand**, not just `--help`. Import errors in rarely
   used modules are exactly what static analysis misses.
3. **Hit the paths that read shipped data files** and the paths that go out to
   the network — those are where `.pem` bundles and CA stores go missing.
4. **Check exit codes propagate.** `sys.exit(1)` from a script buried inside a
   bundle can get swallowed by some activation shims, and CI will not notice.
5. **Run from a different working directory**, and from a path containing
   spaces. Both break naive relative paths.
6. **For `--onefile`, watch the start time** and confirm `%TEMP%` is writable —
   locked-down or full temp directories are a classic field failure.
7. **Re-verify after any dependency bump.** A build is only as good as the
   environment it was produced from.

---

## Summary: pick one

| If you need... | Use |
|---|---|
| The default, most-trodden path | **PyInstaller** `--onedir` |
| A single file and can accept temp extraction | **PyInstaller** `--onefile` |
| Maximum runtime speed, least readable output | **Nuitka** |
| Hand-declared dependency control | **cx_Freeze** |
| A target machine that already has Python | **`zipapp`** (or `shiv`/`pex` for deps) |
| No freezer, no installer, full layout control | **Embedded interpreter** |

Start with `--onedir` PyInstaller. Move to something else only when a specific
constraint — startup time, artifact size, antivirus noise, or a hard "no
interpreter on the target" rule — pushes you there.



