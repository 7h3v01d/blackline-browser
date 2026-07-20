# Blackline Browser — Capability Audit

**Subject:** Blackline Browser (PyQt6 + QtWebEngine), `src/` ≈ 3,500 LOC + 6 plugins
**Author:** Leon Priest / GitHub: 7h3v01d
**Date:** 20 July 2026
**Purpose:** Honest assessment of where Blackline falls short of mainstream, privacy-focused, and power-user browsers.

---

## 0. Method and scope

Findings are drawn from reading the source in the `2026-07-20_0207` package: `browser.py`, `interceptors.py`, `vault.py`, `dialogs.py`, `downloader.py`, `main_gui.py`, `splash.py`, and the six plugins. Version claims were verified against PyPI and Qt documentation on the audit date rather than from memory.

This audit deliberately does **not** grade on a curve for it being a solo project. The question asked was where it genuinely falls short, so it is measured against what shipped browsers actually do. Section 6 covers where Blackline wins, and it does win in places.

**Headline verdict:** Blackline is a strong *power-user shell* on top of a *stale and unpatchable engine*. The UI, feature composition, and integrations are genuinely competitive — in a few areas better than mainstream. The gaps are almost entirely in engine currency, credential safety, and isolation, and one of them can destroy user data today.

---

## 1. Critical — fix before anyone else runs this

### 1.1 A mistyped master password silently destroys the vault

`browser.py`:

```python
if ok and password:
    self.vault = Vault(password)
    if not self.vault.unlock_vault():
        self.vault.create_and_lock_vault({"logins": [], "api_keys": []})
```

`Vault.unlock_vault()` returns `False` for **two different reasons**: the file does not exist, *or* Fernet decryption failed. The caller cannot tell them apart, and treats both as "make a new vault." `create_and_lock_vault()` then opens `credentials.vault` with `"wb"` and overwrites it.

Consequence: **one typo at the login prompt wipes every saved credential and API key, silently, with no backup and no undo.** There is no recovery path — the plaintext is gone.

Severity: **P0.** This is the single most serious finding in the audit. No shipped password manager can lose a vault to a typo.

Fix shape: have `unlock_vault()` return a tri-state (`OK` / `WRONG_PASSWORD` / `NO_VAULT`), only create when the file is genuinely absent, re-prompt on a bad password, and write via temp-file + `os.replace()` with a `.bak` retained. That is your existing atomic-write house pattern — it just was not applied here.

### 1.2 Chromium baseline is roughly two years stale, with no update path

`requirements.txt` pins `PyQt6-WebEngine==6.7.0`. Qt 6.7's WebEngine is based on Chromium 118.0.5993.220. Current PyQt6-WebEngine on PyPI is **6.11.0**.

Fairness matters here: Qt backports security patches from recent Chrome releases to supported versions, and the listed Chromium version is only the base version. So this is not literally "Chromium 118 with 118's bugs." But Qt 6.7 is not an LTS release and is past its patch window, so the backport stream that made the pin defensible has ended.

| | Blackline | Chrome/Edge | Firefox | Brave | LibreWolf |
|---|---|---|---|---|---|
| Engine patch latency | Frozen at pin | ~2–4 weeks major, days for 0-days | ~4 weeks | Tracks Chromium | Tracks Firefox |
| Auto-update | None | Silent background | Background | Background | Manual/pkg |
| Emergency 0-day response | Manual rebuild by you | Hours | Hours | Hours | Days |

This is *the* structural gap and it is not closeable by writing better Python. A solo developer cannot match a browser vendor's vulnerability response. It should drive positioning (§7), not just a backlog ticket.

Immediate action: move the pin to 6.11.x, test, and add a startup check that logs `qWebEngineChromiumVersion()` so the baseline is visible rather than implicit.

### 1.3 Plugin loader is unsandboxed arbitrary code execution from a relative path

```python
plugin_dir = Path("plugins")          # relative to CWD, not to the app
sys.path.append(str(plugin_dir))
module = import_module(module_name)
```

Any `.py` file dropped in a `plugins/` folder *relative to the working directory* is imported and executed with full process privileges — no manifest, no signature, no capability declaration, no allowlist. Because the path is CWD-relative, launching Blackline from a different directory can load a different, attacker-supplied `plugins/` tree.

The notable thing is that you have already solved this problem twice, better, in your own work: UCI Protocol does Ed25519 signing with TOFU key pinning, and ACG/Keystone Cleanroom are deny-first with an approval pipeline. Blackline's plugin system is the least governed component in an estate whose defining characteristic is governance. Porting even a stripped-down version of the UCI approach — hash-pin the plugin set, prompt on change — would close this cheaply and make the browser consistent with the rest of the portfolio.

### 1.4 Master password is retained in plaintext and compared non-constant-time

```python
self.master_password_str = master_password    # kept for re-auth
...
return password_to_check == self.master_password_str
```

Two issues: the master password lives in process memory as a `str` for the whole session (Python strings are immutable, so it cannot be zeroed and may persist in a crash dump or swap file), and re-authentication compares with `==` rather than `hmac.compare_digest`. Also, PBKDF2-HMAC-SHA256 at **100,000 iterations** is roughly a sixth of current OWASP guidance for that primitive.

Fix shape: keep only the derived key, verify re-auth by attempting decryption rather than string comparison, raise iterations (and store the count in the file header so old vaults stay readable), or move to Argon2id via `argon2-cffi`.

---

## 2. Isolation and privacy gaps

| Capability | Blackline | Brave | LibreWolf | Mullvad | Firefox |
|---|---|---|---|---|---|
| Private / incognito window | **None** | Yes + Tor window | Yes | Yes (whole browser is ephemeral) | Yes |
| Multiple profiles / containers | **None** | Profiles | Profiles | — | Containers |
| Fingerprint resistance | **None** | Randomisation | RFP | RFP + uniform config | RFP (opt-in) |
| HTTPS-only enforcement | **None** | Yes | Yes | Yes | Yes |
| Cosmetic ad filtering | **None** | Yes | uBO | uBO | uBO |
| Tracker blocking (EasyPrivacy etc.) | **None** | Yes | Yes | Yes | Yes |
| Third-party cookie policy control | Default only | Blocked | Blocked | Blocked | Total Cookie Protection |

Specifics worth calling out:

- **`QWebEngineProfile.defaultProfile()` is used for everything.** All tabs share one cookie jar, one cache, one storage partition. Qt supports off-the-record profiles for exactly this purpose; a private window is arguably the cheapest high-value feature on the whole backlog.
- **Certificate errors are a one-click override.** `handle_certificate_error()` presents a plain Yes/No `QMessageBox`. Mainstream browsers deliberately make this hostile — interstitial, "Advanced" disclosure, typed confirmation for HSTS hosts — because one-click bypass is how MITM attacks succeed. There is also no HSTS awareness in the handler.
- **Browsing data is plaintext, in the working directory.** `history.json`, `tabs.json`, `console_history.json`, `settings.json` all land relative to CWD. Passwords get Fernet; the browsing history that reveals just as much does not.
- **The ad blocker is network-level only.** Post-fix it is a solid domain blocklist, but it cannot hide elements, so blocked ad *slots* still leave layout holes, and `$domain=`-scoped rules are skipped by design because the interceptor has no initiator context. It loads EasyList only — no EasyPrivacy, no annoyances list.

---

## 3. Platform and ecosystem gaps

| Capability | Blackline | Chrome | Firefox | Vivaldi | qutebrowser |
|---|---|---|---|---|---|
| WebExtensions (uBO, 1Password, Dark Reader) | **None** | Yes | Yes | Yes | No |
| Sync across devices | **None** | Yes | Yes | Yes | No |
| Signed installer / auto-update | **None** | Yes | Yes | Yes | Package managers |
| Crash recovery | **None** | Yes | Yes | Yes | Partial |
| Mobile client | **None** | Yes | Yes | Yes | No |
| Vertical tabs / tab groups | **None** | Groups | Both | Both | Tree-style |

- **No WebExtensions support** is the biggest single functional gap for anyone else adopting it. QtWebEngine has no extension host, so this is effectively unfixable — which is fine, but it means Blackline can never be someone's only browser.
- **No test suite.** There is not a single test file in the package. Set against your own recent work — ACG at 231, Keystone Cleanroom at 290, InkHeart at 1,607, UCI at 380 — Blackline is a conspicuous outlier, and it is the project where a regression is most user-visible. The ad-blocker substring bug found earlier today is precisely the kind of defect a twenty-line table-driven test would have caught at write time.
- **No atomic writes.** `save_history()`, `save_settings()`, `save_tabs()` all `open(..., "w")` and `json.dump()` directly. A crash or power loss mid-write truncates the file; `save_history()` swallows the exception with a bare `except Exception: pass`. Again, this is your documented house pattern simply not applied here.
- **Windows-only in practice.** `find_widevine_path()` hardcodes `C:\Program Files\Google\Chrome`, and the packaging assumes Windows. Not a defect for personal use — worth stating plainly if the repo is public, since the README does not currently scope it.

---

## 4. Correctness issues found during the audit

| # | Issue | Severity | Status |
|---|---|---|---|
| 1 | Wrong master password overwrites vault | **P0** | Open |
| 2 | EasyList substring matching blocked github.com, youtube.com, reddit.com | P1 | **Fixed today** |
| 3 | `LocalContentCanAccessRemoteUrls` off → favicons and webfont silently dropped | P2 | **Fixed today** |
| 4 | `--disable-logging` never applied (`setdefault` on an already-set key) | P3 | **Fixed today** |
| 5 | Drop-shadow effect on translucent top-level → per-frame `UpdateLayeredWindowIndirect` failures | P3 | **Fixed today** |
| 6 | Plugin loader executes unsigned code from CWD-relative path | P1 | Open |
| 7 | Master password retained as plaintext `str`; `==` comparison | P2 | Open |
| 8 | PBKDF2 at 100k iterations | P2 | Open |
| 9 | Non-atomic writes to history/settings/tabs | P2 | Open |
| 10 | Certificate override is a single click, no HSTS awareness | P2 | Open |

---

## 5. One non-technical exposure

The Netflix downloader plugin drives `yt_dlp` against DRM-protected commercial content. Circumventing technological protection measures is separately actionable from copyright infringement in most jurisdictions, including under Australia's Copyright Act. Whatever the personal-use position, publishing it in a public repo under your real name and GitHub handle is a different risk profile from keeping it local. I am not a lawyer and this is not legal advice — but an honest audit should not omit that the highest-risk artefact in the repo is a plugin, not a CVE. Worth a deliberate decision before the repo goes public, not an accidental one.

---

## 6. Where Blackline genuinely beats the field

Stated plainly, because an audit that only lists deficits is not honest either:

- **Integrated multi-threaded download manager** with chunked ranges, SHA-256 verification, and resume. Chrome's downloader does none of that. Closest comparison is a separate app like IDM.
- **Qt-side picture-in-picture** that survives navigation and hands the video back. Browser-native PiP is more fragile than what you built.
- **Repeater and proxy plugins** — request interception, pause, replay. That is Burp Suite territory, inside a normal browser, with no proxy configuration.
- **Reading mode, notes sidebar, screenshot region capture** as first-party features rather than three separate extensions.
- **The new tab page and boot sequence.** The dark-industrial identity is more coherent than most commercial browsers manage. Vivaldi is the only mainstream browser in the same conversation.
- **Auditability.** ~3,500 lines you can read end to end, versus 30M+ lines in Chromium. That is a real and underrated property.

---

## 7. Recommended positioning

The Chromium currency problem cannot be engineered away by one person, which makes positioning a design decision rather than a marketing one.

**Do not position Blackline as a daily driver or a privacy browser.** It cannot beat Brave or Mullvad on isolation and fingerprinting, and recommending it for banking or threat-model-serious browsing would be misleading given §1.2 and §2.

**Do position it as a power-user instrument** — a research, interception, and media-tooling browser that happens to be pleasant to live in. Against that framing the download manager, repeater, proxy, PiP, and notes are the headline features, and the honest caveat is one line in the README: engine currency is tied to the pinned Qt version, use a mainstream browser for high-risk sessions.

---

## 8. Prioritised remediation

| Priority | Item | Effort | Rationale |
|---|---|---|---|
| **P0** | Tri-state vault unlock + `.bak` + atomic write | ~2 h | Prevents silent data destruction |
| **P0** | Bump PyQt6/WebEngine 6.7 → 6.11, log Chromium version at startup | ~half day | Closes ~2 years of engine drift |
| **P1** | Test suite: filter parser, vault round-trip, session save/load | ~1 day | Brings Blackline in line with the rest of the estate |
| **P1** | Plugin hash-pinning + approval prompt (port from UCI) | ~1 day | Removes unsandboxed RCE; reuses existing design |
| **P1** | Private window via off-the-record `QWebEngineProfile` | ~half day | Highest-value missing privacy feature |
| **P2** | Argon2id or PBKDF2 ≥600k, drop plaintext master password | ~3 h | Brings KDF to current guidance |
| **P2** | Atomic writes across history/settings/tabs | ~2 h | House pattern, not yet applied |
| **P2** | Harden certificate interstitial, add HTTPS-only toggle | ~half day | Removes one-click MITM acceptance |
| **P3** | EasyPrivacy list, cosmetic filtering via injected CSS | ~1 day | Closes visible gap vs Brave |
| **P3** | Crash recovery / session journal | ~half day | Parity with mainstream |

**Explicitly not recommended:** WebExtensions support (QtWebEngine has no extension host — architecturally out of reach), sync infrastructure (server, auth, and E2E crypto to maintain forever), and any attempt to fork or vendor Chromium directly.

---

*Findings verified against source in `blackline-browser_2026-07-20_0207`. Version claims checked against PyPI and Qt documentation on 20 July 2026.*
