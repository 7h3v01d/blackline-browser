# 🌐 Personal Web Browser v2.0

A privacy-focused personal browser built on **PyQt6 + QtWebEngine**, with a signature dark-industrial UI, a speed-dial new-tab page, DRM video support, ad blocking, an encrypted password vault, and a plugin system. Built as a daily driver for personal web use.

![Python](https://img.shields.io/badge/Python-3.11%2B-2fd6c3?style=flat-square&logo=python&logoColor=white)
![PyQt6](https://img.shields.io/badge/PyQt6-QtWebEngine-ffb454?style=flat-square&logo=qt&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Windows%2010%2F11-4be08a?style=flat-square&logo=windows&logoColor=white)
![License](https://img.shields.io/badge/License-Evaluation--Only-ff5c66?style=flat-square)

---

<img width="1282" height="852" alt="webbrowser" src="https://github.com/user-attachments/assets/d5335cda-b782-4655-a138-e524f19e6ae9" />

---

## 🆕 Recent updates

- **Full visual retheme** into the signature dark-industrial design language — obsidian/teal/amber/phosphor palette, JetBrains Mono typography, flat zero-radius chrome, corner-bracket speed-dial tiles, and a systems-monitor status bar. Applied end-to-end across the toolbar, tabs, menus, dialogs, panels, reading mode, and plugins.
- **HTML5 video fullscreen now works** — a site's own fullscreen button (e.g. YouTube) properly goes full screen and hides all browser chrome.
- **Picture-in-Picture rebuilt** as a Qt-side floating mini-player with two-way position handover (see below).
- **YouTube Shorts wheel navigation** — the mouse wheel now moves between Shorts.

---

## ✨ Features

### Interface
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
- **Ad blocker** — loads EasyList on first run (66,000+ filters). Tries three mirrors automatically. Auto-refreshes weekly. Netflix/DRM domains are always whitelisted.
- **Encrypted password vault** — AES-256 (Fernet) vault for saved logins and API keys. Requires a master password on launch. Auto-captures credentials from login forms.
- **SSL indicator** — 🔐 for valid HTTPS, ⚠️ for certificate errors with accept/reject prompt.
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
├── main.py                      # Entry point — Widevine detection, app init
├── browser.py                   # Main window, all UI and feature logic
├── dialogs.py                   # Bookmarks, History, Notes, DevTools, Password Manager
├── interceptors.py              # Ad blocker, proxy interceptor, plugin base class
├── downloader.py                # Multi-threaded download engine
├── main_gui.py                  # Download panel UI
├── vault.py                     # Encrypted credential storage (Fernet/PBKDF2)
├── new_tab.html                 # Speed dial new-tab page
├── core/
│   └── portcore.py              # Port management utilities
└── plugins/
    ├── proxy_plugin.py          # HTTP request interceptor / editor
    ├── repeater_plugin.py       # Request crafter & repeater
    ├── screenshot_plugin.py     # Full-page and region screenshot capture
    └── netflix_downloader_plugin.py  # yt-dlp based video downloader
```

**Runtime files created automatically:**
```
src/
├── settings.json                # Homepage, theme, ad blocker, autofill preferences
├── bookmarks_v2.json            # Bookmarks with folder structure
├── history.json                 # Browsing history (last 2000 entries)
├── tabs.json                    # Saved tab session
├── notes.json                   # Per-domain and global notes
├── credentials.vault            # Encrypted password vault
├── easylist.txt                 # Ad block filter list (auto-downloaded)
├── console_history.json         # DevTools JS console history
└── webengine_profile/           # Chromium persistent storage (cookies, cache)
```

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

On first launch you will be prompted for a **vault master password**. This encrypts your saved logins. If you skip it, the password manager is disabled for that session.

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

Plugins live in `src/plugins/`. Any `.py` file there is auto-loaded at startup. Each plugin subclasses `Plugin` from `interceptors.py` and appears as its own menu in the menu bar.

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

---

## 📝 Notes

- **EasyList** is downloaded on first run to `easylist.txt` and refreshed every 7 days. Three mirrors are tried in order if one is unavailable.
- **Widevine** is loaded from Google Chrome's installation directory. The browser scans all installed Chrome versions automatically and picks the latest one. Netflix and other DRM-protected sites require Chrome to be installed.
- The `webengine_profile/` directory stores cookies, cached pages, and local storage — delete it to reset the browser to a clean state.
- Closing the window auto-saves the current tab session; it is restored on next launch.

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
