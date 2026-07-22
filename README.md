# 🌐 Blackline Browser

A power-user personal browser built on **PyQt6 + QtWebEngine**, with a signature dark-industrial UI, an animated boot sequence, private browsing, network *and* cosmetic ad filtering, HTTPS-only mode, an encrypted credential vault, a governed plugin system, and an integrated multi-threaded download manager.

Built as a research and media-tooling browser rather than a hardened daily driver — see [Known limitations](#-known-limitations) for an honest account of where it does and does not compete.

![Python](https://img.shields.io/badge/Python-3.11%2B-2fd6c3?style=flat-square&logo=python&logoColor=white)
![PyQt6](https://img.shields.io/badge/PyQt6-QtWebEngine-ffb454?style=flat-square&logo=qt&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Windows%2010%2F11-4be08a?style=flat-square&logo=windows&logoColor=white)
![License](https://img.shields.io/badge/License-Evaluation--Only-ff5c66?style=flat-square)
![Tests](https://img.shields.io/badge/tests-415%20passing-4be08a?style=flat-square&logo=pytest&logoColor=white)

---

<img width="1282" height="852" alt="webbrowser" src="https://github.com/user-attachments/assets/d5335cda-b782-4655-a138-e524f19e6ae9" />

---

## 🆕 Recent updates

**Security & correctness**
- **Vault can no longer be destroyed by a typo.** A wrong master password was previously indistinguishable from "no vault yet", and the caller responded by overwriting `credentials.vault` with an empty one. Unlocking now returns an explicit state, retries on a bad password, and never writes unless the vault is genuinely absent.
- **Ad blocker rewritten.** Filters were matched as bare substrings, so a rule scoped to one site blocked `github.com`, `www.youtube.com` and `reddit.com` outright. Matching is now exact-or-subdomain.
- **Plugins are governed.** They execute with full process privileges, so loading is now deny-first: SHA-256 hash-pinned in `plugins.lock`, with approval prompted for anything new or modified.
- **Certificate errors are graded** rather than a single Yes/No box — revocation and pinning failures cannot be bypassed at all, trust failures require typing the hostname.
- **All persistence is atomic and app-anchored.** Data files resolved against the working directory, so launching from another folder silently started with an empty history.

**Features**
- **Animated boot sequence** — a 5-second splash with staged boot log and progress, followed by a styled vault dialog replacing the stock `QInputDialog`.
- **Private browsing** (`Ctrl+Alt+N`) — off-the-record profile, no history, no session restore, no saved passwords.
- **HTTPS-only mode** — automatic `http` → `https` upgrading, with local and RFC1918 hosts exempt.
- **Cosmetic ad filtering** — 13,600 element-hiding rules now applied, so blocked ads no longer leave holes in the layout.
- **EasyPrivacy** loaded alongside EasyList for tracker and analytics blocking.
- **Rebranded new-tab page** with the Blackline mark, HUD corner brackets, and favicons that fall back to a generated monogram rather than rendering empty.
- **415-test pytest suite** covering every pure-logic module.

## ✨ Features

### Interface
- **Boot sequence** — a 5-second animated splash (staged boot log, teal scanline, progress rail, click to skip) followed by a styled vault dialog with reveal toggle and caps-lock warning.
- **Signature dark UI** — full Qt chrome theming (toolbar, tabs, menus, dialogs, panels) in the obsidian/teal/amber/phosphor palette with JetBrains Mono type and flat, zero-radius controls. The active tab carries a teal underline, secure connections glow phosphor-green, and a HUD status bar reports ad-block filters, vault state, and tab count. Toggle back to the light Qt theme with `Ctrl+Shift+D` or the 🌙 button; preference saved across sessions.
- **Custom new-tab page** — a speed-dial dashboard with a monospace clock (teal ticking seconds), time-based greeting, DuckDuckGo search bar, and a grid of corner-bracket site tiles with a systems-readout footer. Add/remove tiles at any time; stored locally.
- **Draggable, closable tabs** — close buttons on every tab, drag to reorder, double-click empty tab bar to open a new tab.
- **Smart URL bar** — auto-detects URLs vs search queries. Bare domains (`github.com`) navigate directly; anything else searches DuckDuckGo.

### Browsing
- **Session restore** — open tabs are saved automatically on close and restored next launch. Manual save via `File → Save Session`.
- **Reading mode** (`Ctrl+Shift+R`) — strips any article down to clean readable text with a dark serif layout, a monospace HUD bar, and A−/A+ font controls.
- **Picture-in-Picture** (`Ctrl+Shift+P`) — pops the current video into a frameless, always-on-top mini-player you can drag by its bar and resize from the corner. Entering pauses the tab and opens the video at the same timestamp; the **↗ return** button hands the position back to the tab and resumes there, so you never lose your place, while **×** closes it but keeps the tab's position. Works for YouTube and direct video files.
- **Fullscreen** — HTML5 video fullscreen works (e.g. YouTube's fullscreen button), hiding all browser chrome; toggle manually with `F11`, exit with `Esc` or the site's own control.
- **YouTube Shorts wheel navigation** — scroll the mouse wheel to move between Shorts.
- **Zoom controls** — `Ctrl+=` / `Ctrl+-` / `Ctrl+0` per tab.
- **Find in page** (`Ctrl+F`).

> **A note on Picture-in-Picture:** QtWebEngine deliberately disables Chromium's native PiP surface ([QTBUG-82390](https://bugreports.qt.io/browse/QTBUG-82390)), so `requestPictureInPicture()` does nothing in any Qt-based browser. This mini-player is a Qt-side implementation instead: it re-opens the current video in a stay-on-top window and synchronises the timestamp both ways. Playback re-seeks to the position rather than being frame-continuous, and DRM/encrypted streams (e.g. Netflix) can't be detached this way.

### Privacy & Security
- **Private browsing** (`Ctrl+Alt+N`) — opens a tab on an off-the-record `QWebEngineProfile`. Nothing reaches disk: no history entry, no session restore, no captured passwords, no per-domain note. Cookies and cache are discarded when the last private tab closes. Private tabs are marked `◈` in the tab bar, and links opened from one stay private.
- **Ad blocker** — EasyList network rules (~48,000 blockable hosts) matched on exact-or-subdomain boundaries, plus **13,600 cosmetic rules** that hide the elements themselves so blocked ads leave no gap. Auto-refreshes weekly across three mirrors. Netflix/DRM domains are always whitelisted.
- **Tracker blocking** — EasyPrivacy is downloaded alongside EasyList and merged into the same host set, covering analytics and tracking that EasyList deliberately leaves alone.
- **HTTPS-only mode** (`View → HTTPS-Only Mode`) — rewrites `http://` navigations to `https://` before any other interceptor sees them. Loopback, `.local`/`.internal`/`.test` and RFC1918 addresses are exempt, so local tooling without TLS keeps working.
- **Graded certificate interstitial** — errors are classified rather than waved through with one click:

  | Severity | Examples | Requirement |
  |---|---|---|
  | Fatal | revoked, pinned-key mismatch, CT required | **No bypass offered** |
  | Dangerous | authority invalid, name mismatch, self-signed, SHA-1 | Type the hostname exactly |
  | Overridable | expired, not yet valid, clock skew | Confirm (Cancel is default) |

  Unrecognised errors classify as *dangerous*, not *overridable*. Exceptions are held in memory only and keyed by host **and** error, so a new failure on a trusted host asks again.
- **Encrypted credential vault** — AES-256 (Fernet) over PBKDF2-HMAC-SHA256. A wrong password re-prompts and never overwrites; the vault is written atomically with a `.bak` retained, and the master password is verified by re-deriving the key with a constant-time compare rather than being held in plaintext.
- **Governed plugin loading** — see [Plugin System](#-plugin-system).
- **Tor support** — enable `tor_enabled` in settings to route through a local Tor proxy.

### Organisation
- **Bookmarks manager** (`Ctrl+Shift+O`) — folder tree, live search, right-click context menu (open / edit / delete). Add the current page with `Ctrl+D`, choose or create a folder on the fly. Stored in `bookmarks_v2.json`.
- **History** (`Ctrl+H`) — searchable table, newest-first, open entries in a new tab, clear all.
- **Note-taking sidebar** (`Ctrl+Shift+N`) — per-domain notes (separate note for each site) plus a global scratch pad. Auto-saves to `notes.json` as you type.

### Downloads
- **Download manager** (`Ctrl+J`) — multi-threaded downloads with pause/resume/retry, progress bars, ETA, speed display, and a queue. Right-click any download for options.

### Developer Tools
- **DevTools panel** (`Ctrl+Shift+I`) — full Chromium inspector docked to the bottom.
- **JS console** — execute JavaScript against the current page with command history (↑/↓).

---

## 🧪 Testing

```bash
test.bat                          # all tests
test.bat -k vault                 # filter by name
test.bat tests/test_adblock.py    # a single file
```

**415 tests**, running in a few seconds. Qt tests run offscreen (set by `conftest.py`), so nothing appears on screen and the suite is CI-safe.

| Module | Covers | Coverage |
|---|---|---|
| `test_adblock.py` | Filter parsing, host matching, the substring regression | 99% |
| `test_vault.py` | Encryption round-trip, unlock states, durability, the data-loss regression | 91% |
| `test_privacy.py` | Every private-mode write path | 100% |
| `test_tls.py` | HTTPS-only decisions, certificate grading, exception scope | 99% |
| `test_cosmetic.py` | Rule parsing, CSS generation, injection safety | 91% |
| `test_plugin_guard.py` | Deny-first policy, lock file, path resolution | 94% |
| `test_storage.py` | Atomic writes, backup recovery, path anchoring | 88% |
| `test_splash.py` | Splash animation, vault dialog, layered-window regression | 83% |
| `test_new_tab.py` | Page integrity, favicon chain, Chromium flags | — |

Tests marked as regressions correspond to bugs that actually shipped; each names the defect it prevents returning.

Install the test dependencies once:

```bash
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

---

## 🎨 Design language

A consistent dark-industrial aesthetic, shared across the toolset:

| Token | Hex | Role |
|---|---|---|
| Obsidian | `#0b0f14` | Base background |
| Panel | `#0e141b` | Raised surfaces / cards |
| Border | `#1c2733` | Hairlines |
| Teal | `#2fd6c3` | Primary accent |
| Amber | `#ffb454` | Secondary accent |
| Phosphor | `#4be08a` | Live / secure state |
| Red | `#ff5c66` | Danger / close |

Typography is **JetBrains Mono** (falling back to Cascadia Mono → Consolas → monospace). Controls are flat and zero-radius with 1px steel hairlines; speed-dial tiles use corner brackets, and status readouts follow a HUD/systems-monitor style.

---

## 🗂 Project Structure

```
src/
├── main.py                      # Entry point — Widevine detection, Chromium flags
├── browser.py                   # Main window, all UI and feature wiring
├── splash.py                    # Boot splash + styled vault dialog
├── dialogs.py                   # Bookmarks, History, Notes, DevTools, Password Manager
├── interceptors.py              # Qt adapters: ad block, HTTPS-only, plugin base class
├── downloader.py                # Multi-threaded download engine
├── main_gui.py                  # Download panel UI
├── new_tab.html                 # Speed dial new-tab page
│
│   # Pure-logic modules — no Qt imports, directly unit-tested
├── adblock.py                   # Filter-list parsing and host matching
├── cosmetic.py                  # Element-hiding rules and CSS generation
├── privacy.py                   # What private tabs may and may not write
├── tls.py                       # HTTPS-only decisions, certificate grading
├── storage.py                   # Atomic, app-anchored JSON persistence
├── plugin_guard.py              # Deny-first plugin integrity gate
├── vault.py                     # Encrypted credential storage (Fernet/PBKDF2)
│
├── core/
│   └── portcore.py              # Port management utilities
└── plugins/
    ├── proxy_plugin.py          # HTTP request interceptor / editor
    ├── repeater_plugin.py       # Request crafter & repeater
    ├── screenshot_plugin.py     # Full-page and region screenshot capture
    ├── anonymity_plugin.py      # User-agent and fingerprint controls
    └── netflix_downloader_plugin.py  # yt-dlp based video downloader

tests/                           # 415 tests — see Testing
pytest.ini                       # Test configuration
requirements-dev.txt             # Test dependencies
```

The pure-logic modules exist so the decisions that matter — what gets blocked, what gets written to disk, what may execute — can be tested exhaustively without a running engine. `interceptors.py` is a thin Qt adapter over them.

**Runtime files, created automatically in the project root:**
```
├── settings.json                # Homepage, theme, ad blocker, HTTPS-only, autofill
├── bookmarks_v2.json            # Bookmarks with folder structure
├── history.json                 # Browsing history (last 2000 entries)
├── tabs.json                    # Saved tab session
├── notes.json                   # Per-domain and global notes
├── credentials.vault            # Encrypted credential vault
├── plugins.lock                 # Approved plugin hashes (machine-local)
├── easylist.txt                 # Ad block filter list (auto-downloaded)
├── easyprivacy.txt              # Tracker filter list (auto-downloaded)
├── console_history.json         # DevTools JS console history
├── *.bak                        # Previous copy of each file, kept automatically
└── webengine_profile/           # Chromium persistent storage (cookies, cache)
```

> These paths are anchored to the project root rather than the working directory. Files left in an old working directory by earlier versions are migrated automatically on first launch, and existing data is never overwritten.

---

## ⚙️ Requirements

### Python
Python 3.11+

### pip packages
```bash
pip install PyQt6 PyQt6-WebEngine cryptography requests urllib3
```

Pinned versions are in `requirements.txt`:
```bash
pip install -r requirements.txt
```

To run the test suite:
```bash
pip install -r requirements-dev.txt
```

### Plugin-specific (optional)
```bash
pip install Pillow          # screenshot_plugin.py
pip install yt-dlp          # netflix_downloader_plugin.py
```

### DRM video (Netflix, etc.)
Widevine CDM is required. The browser auto-detects it from any installed version of **Google Chrome** on Windows. No manual configuration needed — just have Chrome installed.

---

## 🚀 Running

```bash
cd src
python main.py
```

On launch you get the boot splash (click to skip), then the vault dialog.

- **Vault master password** — encrypts saved logins and API keys. Cancel or press `Esc` to run without the password manager. A wrong password re-prompts; it will not overwrite an existing vault.
- **Plugin approval** — on first launch each bundled plugin prompts once. Approve the ones you want; the decision is remembered by content hash.

---

## ⌨️ Keyboard Shortcuts

### Navigation
| Shortcut | Action |
|---|---|
| `Alt+←` | Back |
| `Alt+→` | Forward |
| `F5` or `Ctrl+R` | Reload |
| `Ctrl+L` | Focus URL bar |
| `Alt+Home` | New tab (home) |
| `Escape` | Stop loading |

### Tabs
| Shortcut | Action |
|---|---|
| `Ctrl+T` | New tab |
| `Ctrl+Alt+N` | New **private** tab |
| `Ctrl+W` | Close tab |
| `Ctrl+Tab` | Next tab |
| `Ctrl+Shift+Tab` | Previous tab |
| `Ctrl+1` – `Ctrl+8` | Jump to tab 1–8 |
| `Ctrl+9` | Jump to last tab |

### Page
| Shortcut | Action |
|---|---|
| `Ctrl+=` | Zoom in |
| `Ctrl+-` | Zoom out |
| `Ctrl+0` | Reset zoom |
| `Ctrl+F` | Find in page |
| `Ctrl+P` | Print |
| `F11` | Toggle fullscreen |

### Features
| Shortcut | Action |
|---|---|
| `Ctrl+D` | Bookmark this page |
| `Ctrl+Shift+O` | Bookmarks manager |
| `Ctrl+H` | History |
| `Ctrl+J` | Downloads panel |
| `Ctrl+Shift+N` | Notes sidebar |
| `Ctrl+Shift+R` | Reading mode |
| `Ctrl+Shift+P` | Picture-in-Picture |
| `Ctrl+Shift+D` | Toggle dark/light mode |
| `Ctrl+Shift+I` | Developer tools |

---

## 🔌 Plugin System

Plugins live in `src/plugins/`. Each subclasses `Plugin` from `interceptors.py` and appears as its own menu in the menu bar.

### Approval gate

Plugins are ordinary Python modules imported into the browser process with full privileges — they can read your files, your browsing data, and your vault. Loading is therefore **deny-first**:

1. Every `.py` file in `src/plugins/` is hashed with SHA-256 at startup.
2. Anything new, modified, or previously declined prompts for approval, showing the hash.
3. Approved hashes are pinned in `plugins.lock`. Only an exact match loads without asking.
4. Editing a plugin changes its hash, so it asks again — reverting the edit restores approval.

`plugins.lock` sits beside the application, not inside `plugins/`, so a dropped-in plugin cannot ship its own approval. A corrupt or missing lock file trusts *nothing* rather than everything. The file is machine-local and gitignored: approving on your machine must not silently approve on anyone else's.

> On first launch after upgrading you will be prompted once per bundled plugin. Earlier versions resolved the plugin directory against the working directory rather than the application, so depending on how you launched, plugins may never have loaded at all.

### Included plugins

**`proxy_plugin.py`** — Logs all HTTP requests in a dockable table. Pause/resume traffic, inspect and edit requests before forwarding them.

**`repeater_plugin.py`** — Request crafter. Load any captured request, modify the URL/method/headers/body, and replay it. Response shown inline.

**`screenshot_plugin.py`** — Capture the full page or draw a selection region. Preview before saving. Requires `Pillow`.

**`netflix_downloader_plugin.py`** — Download Netflix videos via `yt-dlp`. Supports quality selection (720p/1080p), audio language, subtitles, and series episode fetching. Requires `yt-dlp` and valid Netflix credentials in the embedded browser.

### Writing a plugin

```python
from interceptors import Plugin
from PyQt6.QtGui import QAction

class Plugin(Plugin):
    def __init__(self, browser, name="My Plugin", version="1.0"):
        super().__init__(browser, name, version)

    def init_plugin(self):
        super().init_plugin()
        # one-time setup here

    def add_to_menu(self, menu):
        action = QAction("Open My Plugin", self.browser)
        action.triggered.connect(self.do_something)
        menu.addAction(action)

    def get_interceptor(self):
        return None   # return a QWebEngineUrlRequestInterceptor subclass to intercept requests

    def do_something(self):
        self.browser.statusBar.showMessage("Hello from my plugin!", 3000)
```

Drop the file in `src/plugins/` and restart — it appears automatically in the menu bar.

---

## 🛠 Settings

Settings are stored in `src/settings.json` and managed via the menus. Available options:

| Key | Default | Description |
|---|---|---|
| `homepage` | `newtab` | URL opened on new tab / home. Use `"newtab"` for the speed dial page. |
| `ad_blocker_enabled` | `true` | Enable/disable EasyList ad blocking |
| `autofill_enabled` | `true` | Auto-capture and fill login credentials |
| `tor_enabled` | `false` | Route new-tab embedded browsers through Tor (localhost:9050) |
| `dark_mode` | `true` | Signature dark theme (off = default light Qt theme) |
| `https_only` | `false` | Upgrade `http://` navigations to `https://` (local hosts exempt) |

---

## 📝 Notes

- **EasyList** and **EasyPrivacy** are downloaded on first run and refreshed every 7 days. Three mirrors are tried in order for each. Rules carrying a path, a wildcard, or a `$domain=` scope are skipped deliberately — a request interceptor has no page context, and applying them globally is what previously blocked legitimate sites.
- **Widevine** is loaded from Google Chrome's installation directory. The browser scans all installed Chrome versions automatically and picks the latest one. Netflix and other DRM-protected sites require Chrome to be installed.
- The `webengine_profile/` directory stores cookies, cached pages, and local storage — delete it to reset the browser to a clean state.
- Closing the window auto-saves the current tab session; it is restored on next launch. Private tabs are excluded.
- Every JSON file is written to a temp file, fsynced, then moved into place, with the previous copy kept as `.bak`. A damaged file is recovered from its backup automatically and reported in the status bar.

---

## ⚠️ Known limitations

An honest account of where Blackline does not compete. These are structural, not backlog items.

**Engine currency.** QtWebEngine pins a Chromium base version, and security patches arrive only when the Qt release is updated and rebuilt. There is no auto-update mechanism. A browser vendor ships 0-day fixes within hours; here it takes a manual dependency bump. **Use a mainstream browser for banking and other high-risk sessions.**

**No WebExtensions.** QtWebEngine has no extension host, so uBlock Origin, password manager extensions, and Dark Reader cannot run. This is architectural and will not change.

**No fingerprint resistance.** Private mode gives cookie and storage isolation plus zero local traces. It does **not** randomise or normalise canvas, WebGL, fonts, or screen metrics — a site can still recognise you across private and normal tabs. Brave and Mullvad do this at the engine level, where the hooks are not exposed to Qt.

**No sync, no mobile client, no signed installer.**

**Windows-oriented.** Widevine detection assumes a Chrome installation at a Windows path. The rest is portable, but packaging and testing target Windows 10/11.

**Cosmetic filtering is declarative only.** Procedural rules (`#?#`, `:has()`, `:matches-css()`) are parsed and skipped rather than approximated, since faking them in plain CSS produces wrong results silently.

### Where it does compete

Integrated multi-threaded downloads with SHA-256 verification and resume; a Qt-side picture-in-picture that survives navigation; request interception and replay without proxy configuration; reading mode, notes, and region screenshots as first-party features; and ~4,000 lines of readable Python you can audit end to end, against 30M+ in Chromium.

---

## Contribution Policy

Feedback, bug reports, and suggestions are welcome.

You may submit:

- Issues
- Design feedback
- Pull requests for review

However:

- Contributions do not grant any license or ownership rights
- The author retains full discretion over acceptance and future use
- Contributors receive no rights to reuse, redistribute, or derive from this code

---

## License
This project is not open-source.

It is licensed under a private evaluation-only license.
See LICENSE.txt for full terms.
