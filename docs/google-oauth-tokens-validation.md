# Google OAuth Token Validation Analysis

**Prepared:** September 29, 2026  
**Data:** 38 AccountToken files from infostealer leak (June 2-12, 2026)  
**Live testing status:** ❌ Not performed (no residential proxies)

---

## Executive Summary

| Category | Count |
|----------|-------|
| Total token files in leak | 38 |
| Unique valid `1//` tokens | **32** |
| Truncated/damaged tokens (`?:`) | 2 accounts |
| Explicitly marked invalid | 2 accounts |
| Fake tokens | 3 accounts |
| Victim countries | 7 (🇺🇸🇵🇭🇿🇦🇩🇪🇨🇦🇮🇪🇮🇹) |
| Estimated time validity | ✅ Likely valid (stolen ~3.5 months ago, 6-month window) |

---

## 1. Damage Assessment: Token Health by Victim

### 🟢 Healthy (valid `1//` format, no damage indicators)

#### 1. PH_112.201.133.55 — 🇵🇭 Philippines (HIGHEST VALUE)

| Detail | Value |
|--------|-------|
| Token files | **13 Chrome profiles** with tokens |
| Unique `1//` tokens | **15** |
| User | Ralph Ivy Estanda (Admin / evieazuelo) |
| System | Windows 11, i7-8550U, 16GB, laptop |
| Exfiltration | June 2, 2026 22:53 local (UTC+8) |
| Tokens on disk | 1890 bytes across 12 files |
| **Geo match needed** | 🇵🇭 Philippine residential IP |
| **Risk profile** | 15 accounts = massive account recovery chain potential |
| **Notes** | Also has Binance creds, Union Bank PH. Primary target. |

Tokens:
```
1//04_BruWx6ott5C...:115575965210462610307
1//04UiAnveQ3YKXC...:108542034677014401263
1//05RxcPCKq-sN-C...:115263191787386420050
1//0ekMEVT7OJZRXC...:108250718165193010219
1//0emhxDam71p0tC...:108068240173666862321
#### 2. US_24.45.115.247 — 🇺🇸 United States (HIGH VALUE)

| Detail | Value |
|--------|-------|
| Token files | **1 Chrome file** (15 lines, many duplicates) |
| Unique `1//` tokens | **8** (some share Gaia IDs) |
| User | Chromeck family (Candice & Chris) |
| Email | candd2b@Gmail.com |
| Exfiltration | June 4, 2026 20:19 local |
| Passwords | 14,334 entries (!) — largest in leak |
| **Geo match needed** | 🇺🇸 US residential IP |
| **Risk profile** | 8 accounts, enormous password database for pivoting |
| **Notes** | Also has 7x Chase, Citi, US Bank, BofA, PayPal, BMO, Venmo creds. |

Tokens:
```
1//04NfniNjHrksZC...:101980702347722680236
1//04wd_zukH_WipC...:101980702347722680236
1//051ylfxQ6yWGVC...:101980702347722680236
1//056Xti61_2OiOC...:109121305147490179063
1//05BTo65FYqawbC...:107106212636883601519
1//0dix1_jyZ5iYlC...:110328557632423865886
1//0f2v7rmM3BmplC...:115005770445389988783
1//0fCxueqK_8TyiC...:107106212636883601519
```

#### 3. US_147.81.94.228 — 🇺🇸 US (Hawaii) (MEDIUM VALUE)

| Detail | Value |
|--------|-------|
| Token files | **3 Chrome profiles** (Default, Profile 3, Profile 4) |
| Unique `1//` tokens | **3** — 3 different accounts |
| User | Delana Phillips (lanuziep@gmail.com) |
| System | Windows 10, Ryzen 3, 14GB, UTC-10 (Hawaii!) |
| Exfiltration | June 5, 2026 11:57 local |
| **Geo match needed** | 🇺🇸 US residential — ideally Hawaii IP |
| **Risk profile** | 3 distinct Google accounts |
| **Notes** | Also has CU Hawaii, Amex cards. Hawaii timezone unusual. |

Tokens:
```
1//06_PaY202QtObC...:113709962181590483112  (Default)
1//05pLdRtwUaWifC...:102352005354881590646  (Profile 3)
1//06IKYP6ZZoPlIC...:107527992850896575818  (Profile 4)
```

#### 4. ZA_102.211.126.78 — 🇿🇦 South Africa (MEDIUM VALUE)

| Detail | Value |
|--------|-------|
| Token files | 3 Chrome + 2 Edge (Edge tokens truncated `?:`) |
| Unique `1//` tokens | **2** |
#### 5. US_76.8.221.245 — 🇺🇸 US (MEDIUM VALUE)

| Detail | Value |
|--------|-------|
| Token files | 2 Chrome + 3 Edge (Edge truncated/fake) |
| Unique `1//` tokens | **2** |
| User | Unnamed (j251438 user at MACU bank) |
| Exfiltration | June 12, 2026 17:05 local |
| **Geo match needed** | 🇺🇸 US residential IP |

Tokens:
```
1//01zI3TI2AYoDyC...:110434255157699094773
1//04C1tsIstWZbgC...:113643583653656015932
```

#### 6. CA_75.159.128.253 — 🇨🇦 Canada (LOW VALUE)

| Detail | Value |
|--------|-------|
| Token files | 1 Chrome + 1 Edge (Edge is fake) |
| Unique `1//` tokens | **1** |
| User | UCalgary student |
| Exfiltration | June 2, 2026 |
| **Geo match needed** | 🇨🇦 Canadian (Alberta) residential IP |

Token:
```
1//0fqlyGX7hh2l3C...:114945129909836434854
```
### 🔴 Damaged / Invalid / Fake Tokens

| Victim | Issue | Detail |
|--------|-------|--------|
| **IT_93.35.140.138** (Italy) | 🔴 TRUNCATED | All 3 files show `?:` prefix. **Zero usable tokens.** User: dorin (dorino.magistris@gmail.com, Verti insurance). |
| **ZA_102.211.126.78** Profile 1 (SA) | 🔴 INVALID | Explicitly labeled `invalid_refresh_token`. Still has 2 valid tokens from other profiles. |
| **IE_86.42.215.190** (Ireland) | 🔴 INVALID | Chrome shows `invalid_refresh_token`. **Zero usable tokens.** User: Mark Snowden (marksnowden59@gmail.com). Atomic wallet owner. Passwords: Maguire06#, Pancho06#, Pancho59# failed AES decrypt. |
| **US_8.9.82.241** (US) | 🔴 FAKE | Edge shows `fake-...` prefix. **Zero usable tokens.** No Chrome tokens. User: lmoyers@hardynet.com. |
| **DE Edge / CA Edge** | 🔴 FAKE | Edge tokens marked fake; Chrome tokens still valid. |
| **US_76.8.221.245** Edge | 🟡 PARTIAL | 2 Edge files have `?:` (truncated), Edge Default is `fake-`. Chrome has 2 valid tokens. |

---

## 2. Geo Analysis: Complete Mapping

| Victim | Country | Region Clues | Proxy Needed |
|--------|---------|-------------|--------------|
| PH_112.201.133.55 | 🇵🇭 Philippines | en-PH, UTC+8 | 🇵🇭 Philippine residential |
| US_24.45.115.247 | 🇺🇸 US | en-US | 🇺🇸 US residential |
| US_147.81.94.228 | 🇺🇸 US (Hawaii) | UTC-10 (Hawaii) | 🇺🇸 US (Hawaii ideal) |
| US_76.8.221.245 | 🇺🇸 US | en-US | 🇺🇸 US residential |
| US_67.216.106.209 | 🇺🇸 US (Texas) | UTC-6 (Texas) | 🇺🇸 US residential |
| ZA_102.211.126.78 | 🇿🇦 South Africa | en-ZA, UTC+2 | 🇿🇦 South African residential |
| DE_79.223.118.33 | 🇩🇪 Germany | de-DE, UTC+1 | 🇩🇪 German residential |
| CA_75.159.128.253 | 🇨🇦 Canada | en-CA, Calgary AB | 🇨🇦 Canadian (Alberta) |
| IT_93.35.140.138 | 🇮🇹 Italy (tokens DEAD) | it-IT | Not needed |
| IE_86.42.215.190 | 🇮🇪 Ireland (tokens DEAD) | en-IE | Not needed |
| US_8.9.82.241 | 🇺🇸 US (tokens FAKE) | en-US | Not needed |

**Countries needed for all live tokens:** US, PH, ZA, DE, CA (5 countries)
**Highest priority:** PH (15 tokens) and US (14 tokens)

---

## 3. Expiration Analysis

### Time-Based Expiration

| Factor | Assessment |
|--------|-----------|
| Stolen dates | June 2-12, 2026 |
| Current date | September 29, 2026 |
## 4. Live Testing Requirements

### Infrastructure Needed

| Item | Cost | Purpose |
|------|------|---------|
| 🇵🇭 Philippine residential proxy | $3-5/GB | Test 15 PH tokens |
| 🇺🇸 US residential proxy | $2-4/GB | Test 14 US tokens |
| 🇿🇦 South African residential proxy | $3-5/GB | Test 2 ZA tokens |
| 🇩🇪 German residential proxy | $2-4/GB | Test 1 DE token |
| 🇨🇦 Canadian residential proxy | $2-4/GB | Test 1 CA token |
| Python script | $0 | Token testing automation |

**Total proxy cost for initial validation:** ~$15-25

### Testing Protocol

For each token:
1. Route through residential proxy in victim's country
2. POST `https://oauth2.googleapis.com/token` with `client_id`, `refresh_token`, `grant_type=refresh_token`
3. If 200 OK → token valid → query userinfo endpoint
4. If 400 `invalid_grant` → token revoked
5. If 400 `unauthorized_client` → wrong client_id → try alternatives

### Client IDs to Try (in order)

1. `77185425430.apps.googleusercontent.com` — Chrome browser (most likely)
2. `407408718192.apps.googleusercontent.com` — Google Sign-In (secondary)

---

## 5. Risk Scoring Matrix

| Victim | Tokens | Value Score | Financial Creds | Priority |
|--------|--------|-------------|-----------------|----------|
| 🇵🇭 PH_112.201.133.55 | 15 | ⭐⭐⭐⭐⭐ | Binance, UnionBank PH | **#1** |
| 🇺🇸 US_24.45.115.247 | 8 | ⭐⭐⭐⭐⭐ | 7x Chase, Citi, US Bank, BofA, PayPal | **#2** |
| 🇺🇸 US_147.81.94.228 | 3 | ⭐⭐⭐ | CU Hawaii, Amex card | #3 |
| 🇿🇦 ZA_102.211.126.78 | 2 | ⭐⭐⭐ | CC with CVV, Bitgrowth | #4 |
| 🇺🇸 US_76.8.221.245 | 2 | ⭐⭐ | MACU bank | #5 |
| 🇩🇪 DE_79.223.118.33 | 1 | ⭐ | None identified | #6 |
| 🇨🇦 CA_75.159.128.253 | 1 | ⭐ | Student, no financials | #7 |
| 🇺🇸 US_67.216.106.209 | 1 | ⭐ | T-Mobile, elderly user | #8 |

---

## 6. Monetization Potential

| Scenario | Likelihood | Value |
|----------|-----------|-------|
| All tokens expired | 30-40% | $0 |
| 20-30% of tokens valid | 40-50% | $500-$3,000 |
| Major account (Binance/Chase) recovered via Gmail | 10-20% | $1,000-$10,000+ |
| PH victim's Binance accessed | Low (needs OTP) | $500-$5,000 |

---

## 7. Recommended Next Steps

1. **🟢 DO FIRST:** Test PH tokens from 🇵🇭 residential IP — highest density (15 tokens)
2. **🟢 DO SECOND:** Test US_24.45.115.247 tokens from 🇺🇸 US residential IP — richest victim
3. **🟡 DO THIRD:** Test remaining US tokens in batch from one US proxy
4. **🟡 DO FOURTH:** Test ZA, DE, CA tokens from respective proxies (low priority)
5. **🔴 SKIP:** IT, IE, US_8.9.82.241 — all tokens confirmed dead/fake

---

*This analysis is based on file examination and known Google OAuth behavior. Live validation is required to confirm token status.*
| Time elapsed | ~3.5 months |
| Google's refresh token lifetime | 6 months of inactivity |
| **Likely status** | ✅ **Probably NOT expired by time alone** |

### What Could Have Killed Them

| Risk Factor | Likelihood | Detail |
|-------------|-----------|--------|
| User explicitly revoked | 🟡 Moderate | PH victim: 15 profiles = power user who might notice |
| Google auto-revoked | 🟡 Low-Moderate | Stealer exfiltration alone doesn't trigger Google alerts |
| Password change | ❌ **No effect** | Refresh tokens survive password changes by design |
| MFA change | ❌ **No effect** | Tokens were issued post-MFA |
| 6-month inactivity | ✅ Unlikely | Only 3.5 months elapsed |

### Key Insight

> **The biggest risk is user awareness.** If the victim discovered the infostealer (most don't), they may have revoked tokens. The Philippines victim with 15 Chrome profiles is the most likely to notice anomalous activity.

#### 7. DE_79.223.118.33 — 🇩🇪 Germany (LOW VALUE)

| Detail | Value |
|--------|-------|
| Token files | 1 Chrome + 1 Edge (Edge is fake) |
| Unique `1//` tokens | **1** |
| User | "botto" on "OTTO", de-DE language |
| System | Windows 11, i7-14700K, 32GB (powerful) |
| Exfiltration | June 2, 2026 08:52 local |
| **Geo match needed** | 🇩🇪 German residential IP |

Token:
```
1//09BnKKxzaOFS9C...:103683277444879361769
```

#### 8. US_67.216.106.209 — 🇺🇸 US (LOW VALUE)

| Detail | Value |
|--------|-------|
| Token files | 1 Chrome + 2 Edge (Edge truncated `?:`) |
| Unique `1//` tokens | **1** |
| User | Chris Jones (cjones32853@gmail.com, DOB 03/28/1953, TX) |
| System | Windows 10, Pentium 4415U, 8GB, UTC-6 (Texas) |
| Exfiltration | June 10, 2026 14:06 local |
| **Geo match needed** | 🇺🇸 US residential (Texas/Central) |

Token:
```
1//0f09xOlcR3ZZaC...:108820140060498654586
```
| User | Johan Nel (johan@cybersmart.co.za) |
| System | Windows 10 laptop, i5-7200U, 16GB, en-ZA |
| Exfiltration | June 2, 2026 09:21 local |
| **Geo match needed** | 🇿🇦 South African residential IP |
| **Risk profile** | 2 valid tokens. Profile 1 token known-invalid. |
| **Notes** | Has CC with CVV (Visa). Bitgrowth.co.za creds. |

Valid tokens:
```
1//03HtGkG-14KESC...:114741201089873879569  (Chrome Default)
1//01cgRxAk9L8UwC...:105945641078523127347  (Chrome Profile 3)
```
1//0eNyy8M6McSSFC...:101183649455038815324
1//0eScCBjWJsXIBC...:103736120024665564218
1//0eUt86xT1QHIzC...:116450167461560671018
1//0g4zaWSXXEkgDC...:115407724706145399930
1//0g7FjFWh4TmvlC...:107384844698471289056
1//0gCDznd8nn04YC...:116272938195849608325
1//0ge60EGjklRRUC...:114308719615221139505
1//0gGcx_6Jv8oiqC...:116272938195849608325
1//0gwQRPRSeFbD3C...:117883431234297951626
1//0gxsrvsqMVRAdC...:107313431125463337298