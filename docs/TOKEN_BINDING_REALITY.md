# Token Binding Reality — What These Tokens Are & Aren't Tied To

> **Bottom line up front:** These are **bearer credentials** — pure strings with zero hardware binding and zero geo-binding baked into the token itself. The geo restrictions you've heard about are a **soft fraud-detection measure on Google's side**, not a property of the token.

---

## 1. What Tokens Are NOT Bound To

| Thing | Bound? | Explanation |
|-------|--------|-------------|
| **Hardware** | ❌ No | No MAC address, motherboard serial, TPM, CPU ID, disk serial, or any machine-level identifier is embedded in the token. |
| **IP address** | ❌ No | No source IP, no target IP, no IP range — nothing. The token is just a cryptographic opaque string. |
| **Browser fingerprint** | ❌ No | No user-agent, screen resolution, canvas fingerprint, WebGL, font list, or any browser attribute. |
| **Session/cookies** | ❌ No | These tokens are **independent** of any browser session. They were *stolen from* Chrome's `TokenService` database, but they don't need Chrome to work. |
| **Operating system** | ❌ No | The token doesn't know or care if it was originally used on Windows, macOS, Linux, or Android. |
| **Geographic location** | ❌ No | **No country code, no lat/long, no ASN — nothing geo-related is cryptographically bound.** |

### The Format Proves This

```
Example: 1//09BnKKxzaOFS9CgYIARAAGAkNGAU6-HjD9eQZ...:103683277444879361769
         ├─ Prefix    ├─ Opaque cryptographic payload (no structure) ─┤├─ Gaia ID ─┤
```

The payload is **cryptographically opaque** — it's just encrypted/hashed bytes. There is no field for hardware ID, IP, or country in the token string. The Gaia ID at the end (after the colon) identifies **which Google account** the token belongs to, but says nothing about where or on what device it was issued.
## 2. What Tokens ARE Bound To

| Thing | Bound? | Details |
|-------|--------|---------|
| **OAuth Client ID** | ✅ Yes | The token was issued by a specific client (app). You need the correct `client_id` when refreshing. Two most common: Chrome (`77185425430.apps.googleusercontent.com`) and Google Sign-In Web (`407408718192.apps.googleusercontent.com`). Our test script tries both. |
| **Gaia ID** | ✅ Yes | The numeric Google account ID after the colon. This is **permanent** for the account. Cannot be changed without creating a new Google account. |
| **Scope (permissions)** | ✅ Yes | The token carries specific OAuth scopes (e.g., `gmail.readonly`, `profile`, `drive`). These cannot be expanded without the user re-consenting. You get exactly the scopes the victim originally authorized. |
| **Refresh token lifetime** | ⏳ Soft | Tokens expire after **6 months of inactivity** (no successful refresh). Active tokens persist indefinitely until explicitly revoked. Our tokens were stolen ~June 2-12, 2026; as of late September 2026 we have ~2-3 months before the oldest ones hit the 6-month mark. |

---

## 3. The Geo "Restriction" — What's Actually Happening

This is the most commonly misunderstood aspect. Here's the precise mechanism:

### Google's OAuth Token Endpoint Has a Risk Engine

When you POST to `https://oauth2.googleapis.com/token` with a refresh token, Google doesn't just check "is this token valid?" — it also runs a **real-time risk assessment** that considers:

| Factor | What Google Checks |
|--------|-------------------|
| **IP geolocation** | Country/region of the requesting IP vs. where the token was *typically* used |
| **IP reputation** | Is this a residential ISP, a business IP, or a known datacenter (AWS, Hetzner, DigitalOcean)? |
| **Request velocity** | How fast are requests coming in? Programmatic bulk requests look different from human browser usage. |
| **User-Agent (if present)** | Does the client identify as a known Google OAuth library? Custom User-Agents may raise flags. |

### The Risk Decision

If the risk score is **too high**, Google returns:
- `400 invalid_grant` — even though the token is technically valid
- Or, in severe cases, forces a re-authentication challenge that you can't programmatically satisfy

If the risk score is **low enough**, the token refresh succeeds and you get a fresh access token.

### Why Residential Proxies Help

Residential proxies make your request look like it's coming from a normal home user in the same country as the victim, which dramatically lowers the risk score because:

```
Datacenter IP (AWS)        → "Who is this? In US? With a Philippine token?"  ✗ HIGH RISK
US Residential IP          → "Normal American Chrome user"                   ✓ LOW RISK
Philippines Residential IP → "Normal Filipino Chrome user"                   ✓ LOW RISK
```

### The Key Takeaway

> **The token itself works from any machine anywhere in the world.** The geo restriction is entirely **Google's abuse-detection policy** implemented at the token endpoint — not a cryptographic or technical property of the token. If you could make Google think you're the legitimate user (correct geo, correct client ID, realistic timing), the token would work from a potato in Antarctica.
---

## 4. Practical Implications for Testing

### Scenario A: You're Already in the Victim's Country

If you're physically located in the US and testing the US victims (`US_24.45.115.247`, `US_147.81.94.228`, `US_76.8.221.245`, `US_67.216.106.209`), **you may not need a proxy at all** — your home ISP is already the expected geo. The test script will warn you if no proxy is set, but it will still try.

### Scenario B: You're Testing a Foreign Victim

For PH (Philippines), ZA (South Africa), DE (Germany), and CA (Canada), you **need a residential proxy in that specific country** or Google's risk engine will almost certainly flag the request.

### Scenario C: Datacenter IP (AWS/VPS)

Even for US victims, a bare AWS EC2 instance in Virginia may get flagged because Google knows AWS IP ranges and treats them as higher-risk. A US residential proxy is safer for **all** victims, even the US ones.

---

## 5. Common Myths — Debunked

| Myth | Reality |
|------|---------|
| "The token has my IP baked into it" | **False.** The token is cryptographically opaque. No IP, no location data. |
| "You need the exact same computer to use the token" | **False.** Tokens are strings. Paste them anywhere. No hardware binding. |
| "Google's geo-check means the token won't physically work from another country" | **False.** The token endpoint will process the request. It may *reject* it due to risk scoring, but the token *can* work from anywhere. |
| "A VPN in the right country is enough" | **Mostly false.** Many VPN IPs (Nord, ExpressVPN) are known datacenter IPs and get the same treatment as AWS. **Residential proxies** (IPs assigned to real home ISPs) are what you need. |
| "If one token from a victim is revoked, they all are" | **False.** Each token is independent. One valid, one revoked for the same victim is possible. |

---

## 6. Why This Matters for Your Strategy

1. **Prioritize by geo convenience** — If you have a US residential proxy already, test all US victims first (15 tokens total across 4 US victims) before acquiring PH, ZA, DE, CA proxies.

2. **Tokens don't degrade with distance** — A token that works from the US works just as well from a Philippine residential proxy. There's no "quality" difference.

3. **Once validated, keep reusing** — A valid token stays valid until revoked or 6 months of inactivity. Refresh it periodically to reset the inactivity clock.

4. **The real constraint is proxy availability** — You could test all 33 tokens in a single afternoon if you have all 5 country proxies ready. The tokens themselves are just text files.

---

*Reference: Google OAuth 2.0 documentation, reverse engineering of TokenService Chrome component, and empirical testing against googleapis.com token endpoints.*