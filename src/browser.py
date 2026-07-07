"""
browser.py  —  upgraded personal browser
New features vs original:
  • Dark mode  (system-aware + manual toggle, Ctrl+Shift+D)
  • Keyboard shortcuts  (full set, see SHORTCUTS section)
  • Session restore  (saves & restores tab URLs across restarts)
  • Reading mode  (Ctrl+Shift+R  — strips page to readable article)
  • Custom new-tab page  (speed dial + clock + search)
  • Note-taking sidebar  (Ctrl+Shift+N)
  • Smarter bookmarks via BookmarksDialog with folders & search
  • Improved history (search, clear)
  • Better download panel integration
"""

import sys
import json
import os
import urllib.request
from urllib.parse import urlparse, urlunparse
from importlib import import_module
from pathlib import Path

from PyQt6.QtWidgets import (
    QMainWindow, QToolBar, QLineEdit, QPushButton,
    QTabWidget, QMenu, QStatusBar, QListWidget,
    QDockWidget, QFileDialog, QInputDialog, QLabel,
    QTableWidget, QTableWidgetItem, QMessageBox, QDialog, QVBoxLayout,
    QApplication, QWidget, QHBoxLayout, QSizeGrip
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import (
    QWebEngineProfile, QWebEnginePage, QWebEngineDownloadRequest,
    QWebEngineScript, QWebEngineSettings
)
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtCore import QUrl, Qt, QDateTime, QObject, pyqtSlot, pyqtSignal, QPoint
from PyQt6.QtGui import QAction, QIcon, QKeySequence, QPalette, QColor, QFont

from interceptors import Plugin, ChainedInterceptor, AdBlockInterceptor
from dialogs import HistoryDialog, DevToolsDialog, PasswordManagerDialog, BookmarksDialog, NoteSidebar
from vault import Vault
from main_gui import DownloadPanel


# ─────────────────────────────────────────────────────────────────────────────
# Reading mode JS  — strips a page down to its article text
# ─────────────────────────────────────────────────────────────────────────────

READER_JS = r"""
(function() {
    // Find the largest block of text content
    const candidates = Array.from(document.querySelectorAll('article, main, [role="main"], .post-content, .article-body, .entry-content, #content, #main'));
    let best = null;
    let bestLen = 0;
    candidates.forEach(el => {
        const len = el.innerText.length;
        if (len > bestLen) { bestLen = len; best = el; }
    });
    if (!best && document.body.innerText.length > 100) best = document.body;
    if (!best) return;

    const title = document.title || '';
    const html = best.innerHTML;

    document.open();
    document.write(`<!DOCTYPE html><html><head>
    <meta charset="utf-8">
    <title>${title}</title>
    <style>
        body {
            font-family: Georgia, 'Times New Roman', serif;
            background: #0b0f14;
            color: #cdd6df;
            max-width: 720px;
            margin: 64px auto;
            padding: 0 24px 80px;
            font-size: 19px;
            line-height: 1.85;
        }
        h1,h2,h3,h4 { font-family: 'JetBrains Mono','Cascadia Mono',Consolas,monospace;
                      color: #e6edf3; letter-spacing: -0.5px; }
        h1 { font-size: 1.9em; margin-bottom: 0.3em; border-bottom: 1px solid #1c2733; padding-bottom: 0.3em; }
        a { color: #2fd6c3; text-decoration: none; }
        a:hover { text-decoration: underline; text-decoration-color: #ffb454; }
        img { max-width: 100%; border: 1px solid #1c2733; }
        pre, code { background: #0e141b; border: 1px solid #1c2733; padding: 2px 6px;
                    font-family: 'JetBrains Mono','Cascadia Mono',Consolas,monospace; font-size: 0.85em;
                    color: #4be08a; }
        blockquote { border-left: 2px solid #2fd6c3; margin-left: 0; padding-left: 20px; color: #7d8b99; }
        ::selection { background: #2fd6c3; color: #05201c; }
        #reader-bar { position: fixed; top: 0; left: 0; right: 0; padding: 10px 24px;
                      background: rgba(8,11,15,0.94); backdrop-filter: blur(8px);
                      display: flex; align-items: center; gap: 14px; z-index: 9999;
                      border-bottom: 1px solid #1c2733;
                      font-family: 'JetBrains Mono','Cascadia Mono',Consolas,monospace; }
        #reader-bar span { font-size: 12px; color: #7d8b99; flex: 1; letter-spacing: 1px;
                           white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        #reader-bar .rtag { color: #ffb454; }
        #exit-reader { font-family: inherit; font-size: 12px; padding: 5px 14px;
                       background: #2fd6c3; color: #05201c; border: none; cursor: pointer; letter-spacing: 1px; }
        #exit-reader:hover { background: #4be08a; }
        #font-dec, #font-inc { font-family: inherit; font-size: 13px; padding: 4px 11px;
                               background: #0e141b; border: 1px solid #253341;
                               color: #7d8b99; cursor: pointer; }
        #font-dec:hover, #font-inc:hover { border-color: #2fd6c3; color: #e6edf3; }
    </style>
    </head><body>
    <div id="reader-bar">
        <span><span class="rtag">// READER</span> &nbsp; ${title}</span>
        <button id="font-dec" onclick="document.body.style.fontSize=Math.max(14,parseInt(getComputedStyle(document.body).fontSize)-2)+'px'">A−</button>
        <button id="font-inc" onclick="document.body.style.fontSize=Math.min(28,parseInt(getComputedStyle(document.body).fontSize)+2)+'px'">A+</button>
        <button id="exit-reader" onclick="history.back()">EXIT</button>
    </div>
    <div style="margin-top:60px">
    <h1>${title}</h1>
    ${html}
    </div>
    </body></html>`);
    document.close();
})();
"""

# ─────────────────────────────────────────────────────────────────────────────
# Dark mode stylesheet  (applied to the Qt chrome, not the web content)
# ─────────────────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────────────────
# Signature dark-industrial theme — obsidian / teal / amber / phosphor / red,
# JetBrains Mono typography, flat zero-radius chrome. Consistent with the rest
# of the 7h3v01d toolset (SQLite Workbench, Markdown Editor Pro, WinSAT Viewer).
#
#   obsidian  #0b0f14   panel  #0e141b   input  #11171f   hover  #16202b
#   border    #1c2733   steel  #253341
#   teal      #2fd6c3   amber  #ffb454   phosphor #4be08a  red    #ff5c66
#   text      #e6edf3   dim    #7d8b99   muted  #4d5b68
#   font      'JetBrains Mono' → 'Cascadia Mono' → Consolas → monospace
# ─────────────────────────────────────────────────────────────────────────────

DARK_QSS = """
* {
    font-family: 'JetBrains Mono', 'Cascadia Mono', Consolas, monospace;
}
QMainWindow, QDialog, QWidget {
    background-color: #0b0f14;
    color: #e6edf3;
}
QMenuBar {
    background-color: #080b0f;
    color: #7d8b99;
    border-bottom: 1px solid #1c2733;
    padding: 2px 4px;
}
QMenuBar::item { padding: 4px 12px; background: transparent; }
QMenuBar::item:selected { background: #16202b; color: #e6edf3; }
QMenu {
    background-color: #0e141b;
    color: #e6edf3;
    border: 1px solid #1c2733;
    padding: 4px;
}
QMenu::item { padding: 5px 22px 5px 14px; }
QMenu::item:selected { background-color: #2fd6c3; color: #05201c; }
QMenu::separator { height: 1px; background: #1c2733; margin: 4px 6px; }
QToolBar {
    background-color: #0b0f14;
    border-bottom: 1px solid #1c2733;
    spacing: 6px;
    padding: 8px;
}
QToolBar::separator { background: #1c2733; width: 1px; margin: 4px 2px; }
QPushButton {
    background-color: #0e141b;
    color: #7d8b99;
    border: 1px solid #1c2733;
    border-radius: 0px;
    padding: 6px 12px;
    font-size: 13px;
    min-width: 28px;
}
QPushButton:hover { background-color: #16202b; border-color: #253341; color: #e6edf3; }
QPushButton:pressed { background-color: #2fd6c3; color: #05201c; border-color: #2fd6c3; }
QPushButton:checked { background-color: #0e141b; color: #2fd6c3; border-color: #2fd6c3; }
QPushButton:disabled { color: #4d5b68; border-color: #131a22; }
QLineEdit {
    background-color: #11171f;
    color: #e6edf3;
    border: 1px solid #1c2733;
    border-radius: 0px;
    padding: 6px 12px;
    font-size: 13px;
    selection-background-color: #2fd6c3;
    selection-color: #05201c;
}
QLineEdit:focus { border-color: #2fd6c3; }
QComboBox, QSpinBox {
    background-color: #11171f;
    color: #e6edf3;
    border: 1px solid #1c2733;
    border-radius: 0px;
    padding: 5px 10px;
}
QComboBox:focus, QSpinBox:focus { border-color: #2fd6c3; }
QComboBox QAbstractItemView {
    background-color: #0e141b;
    border: 1px solid #1c2733;
    selection-background-color: #2fd6c3;
    selection-color: #05201c;
}
QTabWidget::pane { border: none; border-top: 1px solid #1c2733; background: #0b0f14; }
QTabBar::tab {
    background: #080b0f;
    color: #7d8b99;
    padding: 7px 18px;
    border: 1px solid #1c2733;
    border-bottom: 2px solid transparent;
    margin-right: 2px;
    font-size: 12px;
    max-width: 220px;
}
QTabBar::tab:selected {
    background: #0e141b;
    color: #e6edf3;
    border-bottom: 2px solid #2fd6c3;
}
QTabBar::tab:hover:!selected { background: #16202b; color: #e6edf3; }
QStatusBar {
    background-color: #080b0f;
    color: #4be08a;
    font-size: 11px;
    border-top: 1px solid #1c2733;
}
QStatusBar::item { border: none; }
QDockWidget { color: #7d8b99; font-weight: bold; titlebar-close-icon: none; }
QDockWidget::title {
    background: #080b0f;
    color: #7d8b99;
    padding: 6px 10px;
    border-bottom: 1px solid #1c2733;
    letter-spacing: 1px;
}
QTableWidget, QListWidget, QTreeWidget {
    background-color: #0b0f14;
    color: #e6edf3;
    border: 1px solid #1c2733;
    gridline-color: #131a22;
    alternate-background-color: #0e141b;
    selection-background-color: #16202b;
    selection-color: #2fd6c3;
    outline: none;
}
QListWidget::item, QTreeWidget::item { padding: 3px 2px; }
QListWidget::item:selected, QTreeWidget::item:selected,
QTableWidget::item:selected { background: #16202b; color: #2fd6c3; }
QHeaderView::section {
    background-color: #080b0f;
    color: #7d8b99;
    border: none;
    border-right: 1px solid #1c2733;
    border-bottom: 1px solid #1c2733;
    padding: 6px 10px;
    font-size: 12px;
    letter-spacing: 1px;
}
QScrollBar:vertical { background: #080b0f; width: 10px; margin: 0; }
QScrollBar::handle:vertical { background: #253341; min-height: 24px; }
QScrollBar::handle:vertical:hover { background: #2fd6c3; }
QScrollBar:horizontal { background: #080b0f; height: 10px; margin: 0; }
QScrollBar::handle:horizontal { background: #253341; min-width: 24px; }
QScrollBar::handle:horizontal:hover { background: #2fd6c3; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; width: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }
QTextEdit, QPlainTextEdit {
    background-color: #0b0f14;
    color: #e6edf3;
    border: 1px solid #1c2733;
    border-radius: 0px;
    selection-background-color: #2fd6c3;
    selection-color: #05201c;
}
QProgressBar {
    background-color: #11171f;
    border: 1px solid #1c2733;
    border-radius: 0px;
    text-align: center;
    color: #e6edf3;
    font-size: 11px;
}
QProgressBar::chunk { background-color: #2fd6c3; }
QSplitter::handle { background: #1c2733; }
QCheckBox { color: #e6edf3; spacing: 8px; }
QCheckBox::indicator {
    width: 15px; height: 15px;
    border: 1px solid #253341; background: #11171f;
}
QCheckBox::indicator:checked { background: #2fd6c3; border-color: #2fd6c3; }
QLabel { color: #e6edf3; background: transparent; }
QToolTip {
    background-color: #0e141b;
    color: #e6edf3;
    border: 1px solid #2fd6c3;
    padding: 4px 8px;
}
"""

LIGHT_QSS = ""   # Use Qt default light palette

# ─────────────────────────────────────────────────────────────────────────────
# Picture-in-Picture JS
# ─────────────────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────────────────
# Page enhancements injected on every load.
#   • YouTube Shorts wheel navigation — the embedded engine doesn't wire the
#     wheel to Shorts nav, so translate wheel → next/prev (button click, with a
#     synthetic arrow-key fallback).
# (Picture-in-Picture is handled Qt-side via a floating window — native
#  requestPictureInPicture() resolves but doesn't render in this engine build.)
# ─────────────────────────────────────────────────────────────────────────────

PAGE_ENHANCE_JS = r"""
(function () {
    if (window.__browserEnhanced) return;
    window.__browserEnhanced = true;

    function reelItems() {
        return Array.prototype.slice.call(
            document.querySelectorAll('ytd-reel-video-renderer')
        );
    }

    // Which reel is currently centered in the viewport
    function activeIndex(items) {
        var mid = window.innerHeight / 2;
        for (var i = 0; i < items.length; i++) {
            var r = items[i].getBoundingClientRect();
            if (r.top <= mid && r.bottom >= mid) return i;
        }
        return 0;
    }

    var cooling = false;
    window.addEventListener('wheel', function (e) {
        if (location.pathname.indexOf('/shorts') !== 0) return;
        e.preventDefault();
        e.stopPropagation();
        if (cooling) return;
        cooling = true;
        setTimeout(function () { cooling = false; }, 450);

        var down = e.deltaY > 0;
        var items = reelItems();

        // Primary: scroll the adjacent reel into view (a real, trusted scroll)
        if (items.length) {
            var idx = activeIndex(items);
            var target = items[idx + (down ? 1 : -1)];
            if (target) {
                target.scrollIntoView({ behavior: 'smooth', block: 'start' });
                return;
            }
        }

        // Fallback 1: click YouTube's nav button if present
        var btn = document.querySelector(
            down ? '#navigation-button-down button, [aria-label="Next video"]'
                 : '#navigation-button-up button, [aria-label="Previous video"]'
        );
        if (btn) { btn.click(); return; }

        // Fallback 2: synthetic arrow key (last resort)
        var key = down ? 'ArrowDown' : 'ArrowUp';
        var kc = down ? 40 : 38;
        ['keydown', 'keyup'].forEach(function (t) {
            document.dispatchEvent(new KeyboardEvent(t, {
                key: key, code: key, keyCode: kc, which: kc, bubbles: true, cancelable: true
            }));
        });
    }, { passive: false, capture: true });
})();
"""

# Detects the current video and returns JSON describing how to re-open it in a
# floating mini-player. YouTube uses a blob/MSE src, so we key off the video id
# and current timestamp; direct file sources can be replayed as-is.
PIP_DETECT_JS = r"""
(function () {
    try {
        var vids = Array.prototype.slice.call(document.querySelectorAll('video'))
            .filter(function (v) { return v.readyState > 0 || v.currentSrc || v.src; });
        if (!vids.length) return JSON.stringify({ ok: false });

        var v = vids.filter(function (x) { return !x.paused && !x.ended; })[0];
        if (!v) {
            v = vids.sort(function (a, b) {
                return (b.videoWidth * b.videoHeight) - (a.videoWidth * a.videoHeight);
            })[0];
        }

        var host = location.hostname;
        var out = {
            ok: true,
            time: Math.floor(v.currentTime || 0),
            src: v.currentSrc || v.src || '',
            page: location.href,
            host: host
        };

        try {
            if (host.indexOf('youtube.') >= 0) {
                var id = new URLSearchParams(location.search).get('v');
                if (!id && location.pathname.indexOf('/shorts/') === 0) {
                    id = location.pathname.split('/shorts/')[1].split('/')[0];
                }
                if (!id) {
                    var m = location.pathname.match(/\/embed\/([^/?]+)/);
                    if (m) id = m[1];
                }
                if (id) out.yt = id;
            } else if (host.indexOf('youtu.be') >= 0) {
                out.yt = location.pathname.slice(1);
            }
        } catch (e) {}

        try { v.pause(); } catch (e) {}
        return JSON.stringify(out);
    } catch (e) {
        return JSON.stringify({ ok: false, err: String(e) });
    }
})();
"""


# ─────────────────────────────────────────────────────────────────────────────
# JS Bridge
# ─────────────────────────────────────────────────────────────────────────────

class JsBridge(QObject):
    credentials_captured = pyqtSignal(str, str)

    @pyqtSlot(str, str)
    def capture_credentials(self, username, password):
        self.credentials_captured.emit(username, password)


QWEBCHANNEL_JS_CODE = """
"use strict";
class QWebChannel {
    constructor(transport, initCallback) {
        if (typeof transport === "undefined") { console.error("QWebChannel: transport required!"); return; }
        this.transport = transport;
        this.send = this.send.bind(this);
        this.execCallbacks = {};
        this.execId = 0;
        this.objects = {};
        this.transport.onmessage = this.onmessage.bind(this);
        this.send("QWebChannel.initialize");
        if (initCallback) { initCallback(this); }
    }
    send(data) {
        if (typeof this.transport.send !== "function") { console.error("QWebChannel: transport.send is not a function!"); return; }
        this.transport.send(data);
    }
    exec(data, callback) {
        if (!callback) { this.send(data); return; }
        if (this.execId === Number.MAX_SAFE_INTEGER) { this.execId = 0; }
        const id = ++this.execId;
        self.execCallbacks[id] = callback;
        this.send(JSON.stringify({ id: id, data: data }));
    }
    onmessage(message) {
        const data = JSON.parse(message.data);
        if (data.id && this.execCallbacks[data.id]) {
            const cb = self.execCallbacks[data.id];
            delete self.execCallbacks[data.id];
            cb(data.data);
        } else if (data.object && data.data) {
            if (this.objects[data.object]) { this.objects[data.object].emit(data.data); }
        }
    }
    registerObject(name, object) { self.objects[name] = object; }
}
if (typeof module !== 'undefined' && module.exports) { module.exports = QWebChannel; }
"""


# ─────────────────────────────────────────────────────────────────────────────
# Main Browser Window
# ─────────────────────────────────────────────────────────────────────────────

NEW_TAB_HTML = os.path.join(os.path.dirname(__file__), "new_tab.html")
HISTORY_FILE  = "history.json"
TABS_FILE     = "tabs.json"
SETTINGS_FILE = "settings.json"
CONSOLE_HIST  = "console_history.json"


# Injected into the PiP mini-player when it shows a YouTube watch page — hides
# the masthead, sidebar and comments so it reads as a compact player. CSS is
# declarative so it still applies to elements YouTube adds later (SPA build).
YT_ISOLATE_JS = r"""
(function () {
    if (location.hostname.indexOf('youtube.') < 0) return;
    var css =
        '#masthead-container,ytd-masthead,#secondary,#secondary-inner,#below,' +
        'ytd-comments,#chat,#guide,tp-yt-app-drawer,#merch-shelf,ytd-merch-shelf-renderer,' +
        '#related,#meta,#meta-contents{display:none!important}' +
        '#primary,#primary-inner,#columns,#page-manager{margin:0!important;padding:0!important}' +
        'ytd-watch-flexy #primary{max-width:100%!important}' +
        'html,body{overflow:hidden!important;background:#000!important}';
    var s = document.createElement('style');
    s.textContent = css;
    (document.head || document.documentElement).appendChild(s);
    try { window.scrollTo(0, 0); } catch (e) {}
})();
"""


class PipWindow(QWidget):
    """Frameless, always-on-top floating mini-player used as Picture-in-Picture.

    The embedded engine won't render native PiP, so instead of detaching the
    live <video> we re-open the current video (YouTube embed at timestamp, or a
    direct file source) in a small stay-on-top window. Draggable by its bar,
    resizable via the corner grip.
    """

    closed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool,
        )
        self.setWindowTitle("Picture-in-Picture")
        self.resize(420, 260)
        self.setMinimumSize(240, 150)
        self._drag_offset = None

        root = QVBoxLayout(self)
        root.setContentsMargins(1, 1, 1, 1)
        root.setSpacing(0)

        # ── Title bar (drag handle + controls) ──
        self.bar = QWidget()
        self.bar.setFixedHeight(26)
        self.bar.setStyleSheet(
            "background:#080b0f; border-bottom:1px solid #1c2733;"
        )
        bar_l = QHBoxLayout(self.bar)
        bar_l.setContentsMargins(10, 0, 6, 0)
        bar_l.setSpacing(6)

        tag = QLabel("// PiP")
        tag.setStyleSheet(
            "color:#2fd6c3; font-family:'JetBrains Mono','Cascadia Mono',Consolas,monospace;"
            "font-size:10px; letter-spacing:2px; background:transparent;"
        )
        bar_l.addWidget(tag)
        bar_l.addStretch(1)

        self.return_btn = QPushButton("\u2197")   # open-in-tab / return
        self.return_btn.setToolTip("Return to tab")
        self.close_btn = QPushButton("\u00d7")
        self.close_btn.setToolTip("Close")
        for b, color in ((self.return_btn, "#2fd6c3"), (self.close_btn, "#ff5c66")):
            b.setFixedSize(18, 18)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(
                "QPushButton { background:#0e141b; border:1px solid #1c2733; border-radius:0px;"
                f" color:{color}; font-family:'JetBrains Mono',Consolas,monospace; font-size:12px; padding:0; }}"
                f"QPushButton:hover {{ border-color:{color}; }}"
            )
            bar_l.addWidget(b)
        self.return_btn.setToolTip("Return to tab (resume here)")
        self.close_btn.setToolTip("Close (keep tab position)")

        root.addWidget(self.bar)

        # ── Video view ──
        self.view = QWebEngineView(self)
        self.view.loadFinished.connect(self._on_loaded)
        root.addWidget(self.view, 1)

        # ── Resize grip ──
        grip_row = QHBoxLayout()
        grip_row.setContentsMargins(0, 0, 0, 0)
        grip_row.addStretch(1)
        grip = QSizeGrip(self)
        grip_row.addWidget(grip)
        root.addLayout(grip_row)

        self.setStyleSheet("PipWindow { background:#0b0f14; border:1px solid #2fd6c3; }")

    def load_url(self, url: str):
        self.view.load(QUrl(url))

    def load_html(self, html: str, base_url: str = ""):
        # base_url gives the document a real origin for direct media playback.
        self.view.setHtml(html, QUrl(base_url) if base_url else QUrl())

    def _on_loaded(self, ok):
        if ok:
            self.view.page().runJavaScript(YT_ISOLATE_JS)

    # Drag the window by its title bar
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.bar.underMouse():
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_offset = None

    def closeEvent(self, event):
        # Stop playback so audio doesn't linger after closing
        self.view.setUrl(QUrl("about:blank"))
        self.closed.emit()
        super().closeEvent(event)


class WebBrowser(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Browser")
        self.setGeometry(100, 100, 1280, 820)

        # ── State ──────────────────────────────────────────────────────────
        self.bookmarks   = BookmarksDialog.load_bookmarks()
        self.history     = []
        self.homepage    = "newtab"
        self.plugins     = []
        self.tor_enabled = False
        self.vault       = None
        self._pip        = None   # floating Picture-in-Picture window
        self._pip_source = None   # tab the PiP video came from (for handover)
        self._pip_finishing = False
        self.autofill_enabled = True
        self.dark_mode   = True    # default dark
        self.reading_mode_active = False

        # ── Profile ────────────────────────────────────────────────────────
        self.profile = QWebEngineProfile.defaultProfile()
        self.USER_AGENTS = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        ]
        self.profile.setHttpUserAgent(self.USER_AGENTS[0])
        self.profile.setPersistentStoragePath("webengine_profile")
        s = self.profile.settings()
        s.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.PluginsEnabled, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.AutoLoadImages, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.FullScreenSupportEnabled, True)
        self.profile.downloadRequested.connect(self.handle_download)

        # ── Status bar ─────────────────────────────────────────────────────
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)

        # ── Ad blocker ─────────────────────────────────────────────────────
        self.ad_blocker = AdBlockInterceptor()
        self.dev_tools   = None
        self.download_panel = None

        # ── Toolbar ────────────────────────────────────────────────────────
        self._build_toolbar()

        # ── Tabs ───────────────────────────────────────────────────────────
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab_by_index)
        self.tabs.tabBarDoubleClicked.connect(self.tab_open_doubleclick)
        self.tabs.currentChanged.connect(self.current_tab_changed)
        self.setCentralWidget(self.tabs)

        # ── Menus ──────────────────────────────────────────────────────────
        self._build_menus()

        # ── Keyboard shortcuts ─────────────────────────────────────────────
        self._build_shortcuts()

        # ── Plugins ────────────────────────────────────────────────────────
        self.load_plugins()

        # ── WebChannel ─────────────────────────────────────────────────────
        self.channel  = QWebChannel()
        self.js_bridge = JsBridge()
        self.js_bridge.credentials_captured.connect(self.handle_credentials)
        self.channel.registerObject("bridge", self.js_bridge)

        # ── Download panel ─────────────────────────────────────────────────
        self.download_panel = DownloadPanel(self)
        self.download_dock  = QDockWidget("Downloads", self)
        self.download_dock.setWidget(self.download_panel)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.download_dock)
        self.download_dock.hide()

        # ── Notes sidebar ──────────────────────────────────────────────────
        self.note_sidebar = NoteSidebar(self)
        self.note_dock = QDockWidget("Notes", self)
        self.note_dock.setWidget(self.note_sidebar)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.note_dock)
        self.note_dock.hide()

        # ── Vault (password manager) ────────────────────────────────────────
        password, ok = QInputDialog.getText(
            self, "Vault Password", "Enter master password (or cancel to skip):",
            QLineEdit.EchoMode.Password
        )
        if ok and password:
            self.vault = Vault(password)
            if not self.vault.unlock_vault():
                self.vault.create_and_lock_vault({"logins": [], "api_keys": []})
        else:
            self.statusBar.showMessage("Vault not initialized. Password manager disabled.", 5000)

        # ── Apply dark mode ────────────────────────────────────────────────
        self.apply_theme()

        # ── Load settings & session ────────────────────────────────────────
        self.load_settings()
        self.load_history()

        # ── Open initial tab ───────────────────────────────────────────────
        self.add_new_tab(self._newtab_url(), "New Tab")
        self.load_tabs()   # restore previous session on top

        # ── Interceptors ───────────────────────────────────────────────────
        interceptors = [self.ad_blocker]
        for plugin in self.plugins:
            interceptor = plugin.get_interceptor()
            if interceptor:
                interceptors.append(interceptor)
        self.profile.setUrlRequestInterceptor(ChainedInterceptor(interceptors))

    # ─────────────────────────────────────────────────────────────────────
    # Theme
    # ─────────────────────────────────────────────────────────────────────

    def apply_theme(self):
        if self.dark_mode:
            QApplication.instance().setStyleSheet(DARK_QSS)
        else:
            QApplication.instance().setStyleSheet(LIGHT_QSS)

    def toggle_dark_mode(self):
        self.dark_mode = not self.dark_mode
        self.apply_theme()
        self.save_settings()
        label = "Dark" if self.dark_mode else "Light"
        self.statusBar.showMessage(f"Switched to {label} mode", 3000)

    # ─────────────────────────────────────────────────────────────────────
    # Toolbar
    # ─────────────────────────────────────────────────────────────────────

    def _build_toolbar(self):
        self.toolbar = QToolBar("Navigation")
        self.toolbar.setMovable(False)
        self.addToolBar(self.toolbar)

        self.back_btn = QPushButton("◄")
        self.back_btn.setToolTip("Back  (Alt+←)")
        self.back_btn.clicked.connect(self.navigate_back)
        self.toolbar.addWidget(self.back_btn)

        self.forward_btn = QPushButton("►")
        self.forward_btn.setToolTip("Forward  (Alt+→)")
        self.forward_btn.clicked.connect(self.navigate_forward)
        self.toolbar.addWidget(self.forward_btn)

        self.reload_btn = QPushButton("↻")
        self.reload_btn.setToolTip("Reload  (F5 / Ctrl+R)")
        self.reload_btn.clicked.connect(self.reload_page)
        self.toolbar.addWidget(self.reload_btn)

        self.home_btn = QPushButton("⌂")
        self.home_btn.setToolTip("Home  (Alt+Home)")
        self.home_btn.clicked.connect(self.go_home)
        self.toolbar.addWidget(self.home_btn)

        self.url_bar = QLineEdit()
        self.url_bar.setPlaceholderText("Search or enter URL…")
        self.url_bar.returnPressed.connect(self.navigate_to_url)
        self.url_bar.setMinimumWidth(300)
        self.toolbar.addWidget(self.url_bar)

        self.ssl_label = QLabel("🔒")
        self.ssl_label.setToolTip("Connection security")
        self.toolbar.addWidget(self.ssl_label)

        # Reading mode toggle button
        self.reader_btn = QPushButton("📖")
        self.reader_btn.setToolTip("Reading Mode  (Ctrl+Shift+R)")
        self.reader_btn.setCheckable(True)
        self.reader_btn.clicked.connect(self.toggle_reading_mode)
        self.toolbar.addWidget(self.reader_btn)

        # Dark mode quick-toggle
        self.theme_btn = QPushButton("🌙")
        self.theme_btn.setToolTip("Toggle Dark/Light Mode  (Ctrl+Shift+D)")
        self.theme_btn.setCheckable(True)
        self.theme_btn.setChecked(True)
        self.theme_btn.clicked.connect(self.toggle_dark_mode)
        self.toolbar.addWidget(self.theme_btn)

        # Picture-in-Picture
        self.pip_btn = QPushButton("⧉")
        self.pip_btn.setToolTip("Picture-in-Picture  (Ctrl+Shift+P)")
        self.pip_btn.clicked.connect(self.toggle_pip)
        self.toolbar.addWidget(self.pip_btn)

    # ─────────────────────────────────────────────────────────────────────
    # Menus
    # ─────────────────────────────────────────────────────────────────────

    def _build_menus(self):
        mb = self.menuBar()

        # File
        file_menu = mb.addMenu("File")
        self._add_action(file_menu, "New Tab", self._new_tab_action, "Ctrl+T")
        self._add_action(file_menu, "Close Tab", self.close_current_tab, "Ctrl+W")
        file_menu.addSeparator()
        self._add_action(file_menu, "Set Homepage", self.set_homepage)
        self._add_action(file_menu, "Save Session", self.save_tabs)

        # View
        view_menu = mb.addMenu("View")
        self._add_action(view_menu, "Developer Tools", self.toggle_dev_tools, "Ctrl+Shift+I")
        self._add_action(view_menu, "Show Downloads", self.show_download_manager, "Ctrl+J")
        self._add_action(view_menu, "Show Notes", self.toggle_notes, "Ctrl+Shift+N")
        view_menu.addSeparator()
        self._add_action(view_menu, "Picture-in-Picture", self.toggle_pip, "Ctrl+Shift+P")
        self._add_action(view_menu, "Reading Mode", self.toggle_reading_mode, "Ctrl+Shift+R")
        self._add_action(view_menu, "Toggle Dark Mode", self.toggle_dark_mode, "Ctrl+Shift+D")
        view_menu.addSeparator()
        self._add_action(view_menu, "Zoom In", self.zoom_in, "Ctrl+=")
        self._add_action(view_menu, "Zoom Out", self.zoom_out, "Ctrl+-")
        self._add_action(view_menu, "Reset Zoom", self.zoom_reset, "Ctrl+0")

        # History
        history_menu = mb.addMenu("History")
        self._add_action(history_menu, "Show History", self.show_history, "Ctrl+H")

        # Bookmarks
        bm_menu = mb.addMenu("Bookmarks")
        self._add_action(bm_menu, "Show Bookmarks", self.show_bookmarks, "Ctrl+Shift+O")
        self._add_action(bm_menu, "Bookmark This Page", self.add_bookmark, "Ctrl+D")

        # Tools
        tools_menu = mb.addMenu("Tools")
        self.toggle_ad_blocker_action = QAction("Enable Ad Blocker", self, checkable=True)
        self.toggle_ad_blocker_action.triggered.connect(self.toggle_ad_blocker)
        tools_menu.addAction(self.toggle_ad_blocker_action)

        self.toggle_autofill_action = QAction("Enable Autofill", self, checkable=True)
        self.toggle_autofill_action.triggered.connect(self.toggle_autofill)
        tools_menu.addAction(self.toggle_autofill_action)

        tools_menu.addSeparator()
        self._add_action(tools_menu, "Password Manager", self.show_password_manager)

    def _add_action(self, menu, label, slot, shortcut=None):
        action = QAction(label, self)
        if shortcut:
            action.setShortcut(shortcut)
        action.triggered.connect(slot)
        menu.addAction(action)
        return action

    # ─────────────────────────────────────────────────────────────────────
    # Keyboard shortcuts  (beyond what's in menus)
    # ─────────────────────────────────────────────────────────────────────

    def _build_shortcuts(self):
        shortcuts = [
            ("Alt+Left",    self.navigate_back),
            ("Alt+Right",   self.navigate_forward),
            ("F5",          self.reload_page),
            ("Ctrl+R",      self.reload_page),
            ("Ctrl+L",      self._focus_url_bar),
            ("Alt+Home",    self.go_home),
            ("Ctrl+Tab",    self.next_tab),
            ("Ctrl+Shift+Tab", self.prev_tab),
            ("Ctrl+1",      lambda: self._switch_tab(0)),
            ("Ctrl+2",      lambda: self._switch_tab(1)),
            ("Ctrl+3",      lambda: self._switch_tab(2)),
            ("Ctrl+4",      lambda: self._switch_tab(3)),
            ("Ctrl+5",      lambda: self._switch_tab(4)),
            ("Ctrl+6",      lambda: self._switch_tab(5)),
            ("Ctrl+7",      lambda: self._switch_tab(6)),
            ("Ctrl+8",      lambda: self._switch_tab(7)),
            ("Ctrl+9",      lambda: self._switch_tab(self.tabs.count() - 1)),
            ("Escape",      self._cancel_load),
            ("F11",         self.toggle_fullscreen),
            ("Ctrl+P",      self.print_page),
            ("Ctrl+F",      self.focus_find),
        ]
        for seq, slot in shortcuts:
            action = QAction(self)
            action.setShortcut(seq)
            action.triggered.connect(slot)
            self.addAction(action)

    # ─────────────────────────────────────────────────────────────────────
    # New Tab URL helper
    # ─────────────────────────────────────────────────────────────────────

    def _newtab_url(self):
        if os.path.exists(NEW_TAB_HTML):
            return QUrl.fromLocalFile(os.path.abspath(NEW_TAB_HTML))
        return QUrl(self.homepage if self.homepage != "newtab" else "https://duckduckgo.com")

    def _new_tab_action(self):
        self.add_new_tab(self._newtab_url(), "New Tab")

    # ─────────────────────────────────────────────────────────────────────
    # Tab management
    # ─────────────────────────────────────────────────────────────────────

    def add_new_tab(self, url, label="New Tab"):
        browser = QWebEngineView()
        page = QWebEnginePage(self.profile, browser)
        browser.setPage(page)
        page.setWebChannel(self.channel)
        page.runJavaScript(QWEBCHANNEL_JS_CODE)
        page.loadFinished.connect(lambda ok: self.on_load_finished(ok, browser))
        page.certificateError.connect(lambda error: self.handle_certificate_error(error, browser))
        # HTML5 fullscreen (YouTube etc.) — accept the page's request and go real fullscreen
        page.fullScreenRequested.connect(self._handle_fullscreen_request)
        # Handle "open in new tab / new window" from right-click menus
        page.createWindow = lambda _win_type: self._create_window()
        browser.urlChanged.connect(self.update_urlbar)
        browser.titleChanged.connect(lambda title: self.tabs.setTabText(self.tabs.indexOf(browser), title[:30] or "New Tab"))
        browser.loadProgress.connect(lambda p: self._update_load_progress(p, browser))
        browser.load(url)
        index = self.tabs.addTab(browser, label)
        self.tabs.setCurrentIndex(index)
        return browser

    def _create_window(self):
        """Called by QWebEnginePage.createWindow — opens a blank new tab and returns its page."""
        browser = self.add_new_tab(self._newtab_url(), "New Tab")
        return browser.page()

    def close_tab_by_index(self, index):
        if self.tabs.count() > 1:
            widget = self.tabs.widget(index)
            self.tabs.removeTab(index)
            widget.deleteLater()
        else:
            # Last tab — just navigate home instead of closing
            self.tabs.currentWidget().load(self._newtab_url())

    def on_load_finished(self, ok, browser):
        self.update_ssl_indicator(ok, browser)
        # Inject page-level enhancements (in-page PiP hotkey, Shorts wheel nav)
        browser.page().runJavaScript(PAGE_ENHANCE_JS)
        if browser == self.tabs.currentWidget():
            url_str = browser.url().toString()
            # Record history
            if url_str and not url_str.startswith("file://"):
                ts = QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm")
                self.history.append((ts, url_str))
                self.save_history()
            # Update notes sidebar domain
            if hasattr(self, 'note_sidebar'):
                self.note_sidebar.set_current_url(url_str)

    def _update_load_progress(self, percent, browser):
        if browser == self.tabs.currentWidget():
            if percent < 100:
                self.statusBar.showMessage(f"Loading… {percent}%")
            else:
                self.statusBar.clearMessage()

    def navigate_to_url(self):
        url = self.url_bar.text().strip()
        if not url:
            return
        # Smart URL detection
        if url.startswith("http://") or url.startswith("https://") or url.startswith("file://"):
            qurl = QUrl(url)
        elif "." in url and " " not in url:
            qurl = QUrl("https://" + url)
        else:
            qurl = QUrl("https://duckduckgo.com/?q=" + url.replace(" ", "+"))
        if self.tabs.count() == 0:
            self.add_new_tab(qurl, "Loading…")
        else:
            self.tabs.currentWidget().load(qurl)

    def navigate_back(self):
        if self.tabs.count() > 0:
            self.tabs.currentWidget().back()

    def navigate_forward(self):
        if self.tabs.count() > 0:
            self.tabs.currentWidget().forward()

    def reload_page(self):
        if self.tabs.count() > 0:
            self.tabs.currentWidget().reload()

    def go_home(self):
        self.add_new_tab(self._newtab_url(), "New Tab")

    def update_urlbar(self, url):
        self.url_bar.setText(url.toString())

    def tab_open_doubleclick(self, index):
        if index == -1:
            self._new_tab_action()

    def current_tab_changed(self, index):
        if index != -1 and self.tabs.currentWidget():
            self.update_urlbar(self.tabs.currentWidget().url())
            if hasattr(self, 'note_sidebar'):
                self.note_sidebar.set_current_url(self.tabs.currentWidget().url().toString())

    def close_current_tab(self):
        self.close_tab_by_index(self.tabs.currentIndex())

    def next_tab(self):
        self.tabs.setCurrentIndex((self.tabs.currentIndex() + 1) % self.tabs.count())

    def prev_tab(self):
        self.tabs.setCurrentIndex((self.tabs.currentIndex() - 1) % self.tabs.count())

    def _switch_tab(self, index):
        if 0 <= index < self.tabs.count():
            self.tabs.setCurrentIndex(index)

    def _cancel_load(self):
        if self.tabs.count() > 0:
            self.tabs.currentWidget().stop()

    # ─────────────────────────────────────────────────────────────────────
    # Zoom
    # ─────────────────────────────────────────────────────────────────────

    def zoom_in(self):
        if self.tabs.count() > 0:
            w = self.tabs.currentWidget()
            w.setZoomFactor(min(w.zoomFactor() + 0.1, 3.0))

    def zoom_out(self):
        if self.tabs.count() > 0:
            w = self.tabs.currentWidget()
            w.setZoomFactor(max(w.zoomFactor() - 0.1, 0.3))

    def zoom_reset(self):
        if self.tabs.count() > 0:
            self.tabs.currentWidget().setZoomFactor(1.0)

    # ─────────────────────────────────────────────────────────────────────
    # Reading mode
    # ─────────────────────────────────────────────────────────────────────

    def toggle_reading_mode(self):
        if self.tabs.count() == 0:
            return
        self.tabs.currentWidget().page().runJavaScript(READER_JS)
        self.reader_btn.setChecked(not self.reader_btn.isChecked())
        self.statusBar.showMessage("Reading mode activated", 3000)

    # ─────────────────────────────────────────────────────────────────────
    # Picture-in-Picture
    # ─────────────────────────────────────────────────────────────────────

    def toggle_pip(self):
        """Open (or close) the floating Picture-in-Picture mini-player.

        Native PiP doesn't render in this engine, so we re-open the current
        video in a stay-on-top window: YouTube via its embed URL at the current
        timestamp, direct file sources as-is. DRM/streamed (blob/MSE) sources
        can't be detached — we say so rather than fail silently.
        """
        if getattr(self, "_pip", None) is not None and self._pip.isVisible():
            self._finish_pip(resume=False)
            return
        if self.tabs.count() == 0:
            return
        self.tabs.currentWidget().page().runJavaScript(PIP_DETECT_JS, self._open_pip)

    def _open_pip(self, result):
        try:
            data = json.loads(result) if result else {}
        except Exception:
            data = {}

        if not data.get("ok"):
            self.statusBar.showMessage("No playable video found for Picture-in-Picture.", 4000)
            return

        html = None
        base = ""
        yt_url = None
        src = data.get("src", "")
        if data.get("yt"):
            start = int(data.get("time", 0) or 0)
            # Full watch page (not /embed/) — avoids the embed origin error 153.
            # Chrome is stripped after load by YT_ISOLATE_JS to keep it compact.
            yt_url = f"https://www.youtube.com/watch?v={data['yt']}&t={start}s"
        elif src.startswith("http") and not src.startswith("blob:"):
            html = (
                "<html><body style='margin:0;background:#000;height:100vh'>"
                f"<video src='{src}' autoplay controls "
                "style='width:100%;height:100%;object-fit:contain'></video>"
                "</body></html>"
            )
        else:
            self.statusBar.showMessage(
                "This video's stream is DRM/encrypted and can't be popped out.", 5000
            )
            return

        if getattr(self, "_pip", None) is None:
            self._pip = PipWindow(self)
            self._pip.return_btn.clicked.connect(lambda: self._finish_pip(resume=True))
            self._pip.close_btn.clicked.connect(lambda: self._finish_pip(resume=False))
            self._pip.closed.connect(lambda: self.statusBar.showMessage("Picture-in-Picture closed.", 2500))
        self._pip_source = self.tabs.currentWidget()   # video handed back here on exit
        if yt_url:
            self._pip.load_url(yt_url)
        else:
            self._pip.load_html(html, base)
        self._pip.show()
        self._pip.raise_()
        self._pip.activateWindow()
        self.statusBar.showMessage("Picture-in-Picture opened — floating on top.", 3000)

    def _view_alive(self, view):
        """True if the given web view is still one of the open tabs."""
        if view is None:
            return False
        for i in range(self.tabs.count()):
            if self.tabs.widget(i) is view:
                return True
        return False

    def _finish_pip(self, resume: bool):
        """Hand the popout's playback position back to the source tab, then close.

        This is the 'handover' half of PiP: we read where the mini-player is now,
        seek the tab's video to that exact spot, and (when returning) resume it
        there and refocus the tab — so closing feels continuous rather than like
        two separate players.
        """
        if getattr(self, "_pip", None) is None:
            return
        if getattr(self, "_pip_finishing", False):
            return
        self._pip_finishing = True

        source = getattr(self, "_pip_source", None)

        def _hand_back(t):
            try:
                t = int(t)
            except (TypeError, ValueError):
                t = -1
            if t >= 0 and self._view_alive(source):
                play = "v.play();" if resume else ""
                source.page().runJavaScript(
                    f"(function(){{var v=document.querySelector('video');"
                    f"if(v){{v.currentTime={t};{play}}}}})();"
                )
                if resume:
                    idx = self.tabs.indexOf(source)
                    if idx >= 0:
                        self.tabs.setCurrentIndex(idx)
            self._pip_source = None
            self._pip_finishing = False
            if getattr(self, "_pip", None) is not None:
                self._pip.close()

        # Read the popout's current time while its page is still live
        self._pip.view.page().runJavaScript(
            "(function(){var v=document.querySelector('video');"
            "return v?Math.floor(v.currentTime):-1;})();",
            _hand_back,
        )

    # ─────────────────────────────────────────────────────────────────────
    # Notes sidebar
    # ─────────────────────────────────────────────────────────────────────

    def toggle_notes(self):
        if self.note_dock.isHidden():
            self.note_dock.show()
        else:
            self.note_dock.hide()

    # ─────────────────────────────────────────────────────────────────────
    # URL bar / misc shortcuts
    # ─────────────────────────────────────────────────────────────────────

    def _focus_url_bar(self):
        self.url_bar.setFocus()
        self.url_bar.selectAll()

    def focus_find(self):
        """Activates in-page search (browser built-in)."""
        if self.tabs.count() > 0:
            # Show simple find text dialog
            text, ok = QInputDialog.getText(self, "Find in Page", "Search:")
            if ok and text:
                self.tabs.currentWidget().findText(text)

    def _handle_fullscreen_request(self, request):
        """Accept an HTML5 fullscreen request from web content (YouTube, etc.)."""
        request.accept()
        if request.toggleOn():
            self._enter_fullscreen()
        else:
            self._exit_fullscreen()

    def _enter_fullscreen(self):
        if getattr(self, "_is_fs", False):
            return
        self._is_fs = True
        self._fs_was_max = self.isMaximized()
        self.menuBar().hide()
        self.toolbar.hide()
        self.tabs.tabBar().hide()
        self.statusBar.hide()
        self.showFullScreen()

    def _exit_fullscreen(self):
        if not getattr(self, "_is_fs", False):
            return
        self._is_fs = False
        self.menuBar().show()
        self.toolbar.show()
        self.tabs.tabBar().show()
        self.statusBar.show()
        if getattr(self, "_fs_was_max", False):
            self.showMaximized()
        else:
            self.showNormal()

    def toggle_fullscreen(self):
        """F11 — manual fullscreen toggle (shares state with HTML5 fullscreen)."""
        if getattr(self, "_is_fs", False) or self.isFullScreen():
            self._exit_fullscreen()
        else:
            self._enter_fullscreen()

    def print_page(self):
        if self.tabs.count() > 0:
            self.tabs.currentWidget().page().print(None)

    # ─────────────────────────────────────────────────────────────────────
    # Downloads
    # ─────────────────────────────────────────────────────────────────────

    def handle_download(self, download):
        suggested_path = download.suggestedFileName()
        path, _ = QFileDialog.getSaveFileName(self, "Save File", suggested_path)
        if path:
            download.accept()
            self.download_panel.add_download(
                url=download.url().toString(),
                save_path=path,
                num_threads=1,
                start_immediately=True
            )
            self.download_dock.show()
        else:
            download.cancel()

    def show_download_manager(self):
        if self.download_dock.isHidden():
            self.download_dock.show()
        else:
            self.download_dock.hide()

    # ─────────────────────────────────────────────────────────────────────
    # History
    # ─────────────────────────────────────────────────────────────────────

    def show_history(self):
        dialog = HistoryDialog(self.history, self)
        dialog.exec()

    def save_history(self):
        try:
            # Keep last 2000 entries
            with open(HISTORY_FILE, "w") as f:
                json.dump(self.history[-2000:], f)
        except Exception:
            pass

    def load_history(self):
        try:
            if os.path.exists(HISTORY_FILE):
                with open(HISTORY_FILE) as f:
                    data = json.load(f)
                    # Support both old string format and new [ts, url] tuple format
                    self.history = []
                    for item in data:
                        if isinstance(item, (list, tuple)) and len(item) == 2:
                            self.history.append(tuple(item))
                        elif isinstance(item, str):
                            self.history.append(("Unknown", item))
        except Exception:
            self.history = []

    # ─────────────────────────────────────────────────────────────────────
    # Bookmarks
    # ─────────────────────────────────────────────────────────────────────

    def show_bookmarks(self):
        dialog = BookmarksDialog(self.bookmarks, self)
        dialog.exec()
        self.bookmarks = dialog.bookmarks   # sync back

    def add_bookmark(self):
        if self.tabs.count() == 0:
            return
        url = self.tabs.currentWidget().url().toString()
        title = self.tabs.currentWidget().title() or url
        if not url or url.startswith("file://"):
            return
        # Quick-add with default folder
        existing_urls = [b.get("url") if isinstance(b, dict) else b for b in self.bookmarks]
        if url not in existing_urls:
            folder, ok = QInputDialog.getItem(
                self, "Add Bookmark", "Folder:",
                list({b.get("folder", "Bookmarks") for b in self.bookmarks if isinstance(b, dict)} or ["Bookmarks"]),
                0, True
            )
            if not ok:
                folder = "Bookmarks"
            self.bookmarks.append({"title": title, "url": url, "folder": folder})
            # persist
            try:
                with open("bookmarks_v2.json", "w") as f:
                    json.dump(self.bookmarks, f, indent=2)
            except Exception:
                pass
            self.statusBar.showMessage(f"Bookmarked: {title[:50]}", 3000)
        else:
            self.statusBar.showMessage("Already bookmarked", 2000)

    # ─────────────────────────────────────────────────────────────────────
    # Password manager
    # ─────────────────────────────────────────────────────────────────────

    def show_password_manager(self):
        if self.vault:
            dialog = PasswordManagerDialog(self.vault, self)
            dialog.exec()
        else:
            self.statusBar.showMessage("Vault not initialized", 3000)

    # ─────────────────────────────────────────────────────────────────────
    # Developer tools
    # ─────────────────────────────────────────────────────────────────────

    def toggle_dev_tools(self):
        if not self.dev_tools:
            from dialogs import DevToolsDialog
            dev_tools_dialog = DevToolsDialog(self.tabs.currentWidget(), self)
            self.dev_tools = QDockWidget("Developer Tools", self)
            self.dev_tools.setWidget(dev_tools_dialog)
            self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.dev_tools)
        if self.dev_tools.isHidden():
            self.dev_tools.show()
        else:
            self.dev_tools.hide()

    # ─────────────────────────────────────────────────────────────────────
    # Credentials / vault
    # ─────────────────────────────────────────────────────────────────────

    def handle_credentials(self, username, password):
        if self.vault and self.autofill_enabled:
            url = self.tabs.currentWidget().url().toString()
            self.vault.data["logins"].append({"url": url, "username": username, "password": password})
            self.vault.create_and_lock_vault(self.vault.data)

    # ─────────────────────────────────────────────────────────────────────
    # Plugins
    # ─────────────────────────────────────────────────────────────────────

    def load_plugins(self):
        plugin_dir = Path("plugins")
        if plugin_dir.exists():
            sys.path.append(str(plugin_dir))
            for plugin_path in plugin_dir.glob("*.py"):
                module_name = plugin_path.stem
                try:
                    module = import_module(module_name)
                    plugin_class = getattr(module, "Plugin", None)
                    if plugin_class:
                        plugin = plugin_class(self)
                        plugin.init_plugin()
                        plugin.add_to_menu(self.menuBar().addMenu(plugin.name))
                        self.plugins.append(plugin)
                except Exception as e:
                    self.statusBar.showMessage(f"Failed to load plugin {module_name}: {str(e)}", 5000)

    # ─────────────────────────────────────────────────────────────────────
    # Session save / restore
    # ─────────────────────────────────────────────────────────────────────

    def save_tabs(self):
        try:
            urls = []
            for i in range(self.tabs.count()):
                widget = self.tabs.widget(i)
                url = widget.url().toString()
                if url and not url.startswith("file://"):
                    urls.append(url)
            with open(TABS_FILE, "w") as f:
                json.dump(urls, f)
            self.statusBar.showMessage(f"Session saved ({len(urls)} tabs)", 3000)
        except Exception as e:
            self.statusBar.showMessage(f"Failed to save session: {str(e)}", 5000)

    def load_tabs(self):
        try:
            if os.path.exists(TABS_FILE):
                with open(TABS_FILE) as f:
                    tabs = json.load(f)
                for url in tabs:
                    if url:
                        self.add_new_tab(QUrl(url), url[:40])
        except Exception as e:
            self.statusBar.showMessage(f"Failed to restore session: {str(e)}", 5000)

    def closeEvent(self, event):
        """Auto-save session on close."""
        self.save_tabs()
        super().closeEvent(event)

    # ─────────────────────────────────────────────────────────────────────
    # Settings
    # ─────────────────────────────────────────────────────────────────────

    def save_settings(self):
        try:
            with open(SETTINGS_FILE, "w") as f:
                json.dump({
                    "homepage": self.homepage,
                    "ad_blocker_enabled": self.ad_blocker.enabled,
                    "tor_enabled": self.tor_enabled,
                    "autofill_enabled": self.autofill_enabled,
                    "dark_mode": self.dark_mode,
                }, f, indent=2)
        except Exception as e:
            self.statusBar.showMessage(f"Failed to save settings: {str(e)}", 5000)

    def load_settings(self):
        try:
            if os.path.exists(SETTINGS_FILE):
                with open(SETTINGS_FILE) as f:
                    s = json.load(f)
                self.homepage          = s.get("homepage", "newtab")
                self.ad_blocker.enabled = s.get("ad_blocker_enabled", True)
                self.tor_enabled       = s.get("tor_enabled", False)
                self.autofill_enabled  = s.get("autofill_enabled", True)
                self.dark_mode         = s.get("dark_mode", True)
                self.toggle_ad_blocker_action.setChecked(self.ad_blocker.enabled)
                self.toggle_autofill_action.setChecked(self.autofill_enabled)
                self.theme_btn.setChecked(self.dark_mode)
                self.apply_theme()
        except Exception as e:
            self.statusBar.showMessage(f"Failed to load settings: {str(e)}", 5000)

    def toggle_ad_blocker(self):
        self.ad_blocker.enabled = self.toggle_ad_blocker_action.isChecked()
        self.save_settings()

    def toggle_autofill(self):
        self.autofill_enabled = self.toggle_autofill_action.isChecked()
        self.save_settings()

    def set_homepage(self):
        url, ok = QInputDialog.getText(self, "Set Homepage", "Enter URL (or 'newtab'):", text=self.homepage)
        if ok and url:
            if url != "newtab" and not url.startswith("http"):
                url = "https://" + url
            self.homepage = url
            self.save_settings()

    # ─────────────────────────────────────────────────────────────────────
    # SSL / certificate
    # ─────────────────────────────────────────────────────────────────────

    def handle_certificate_error(self, error, browser):
        reply = QMessageBox.warning(
            self, "Certificate Error",
            f"Invalid certificate for {error.url().toString()}: {error.description()}\n\nProceed anyway?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            error.acceptCertificate()
            self.ssl_label.setText("⚠️")
        else:
            error.rejectCertificate()
            self.ssl_label.setText("🔒")

    def update_ssl_indicator(self, ok, browser):
        if browser == self.tabs.currentWidget():
            url = browser.url()
            if ok and url.scheme() == "https":
                self.ssl_label.setText("🔐")
            else:
                self.ssl_label.setText("🔒")

    # ─────────────────────────────────────────────────────────────────────
    # Console history  (used by DevToolsDialog)
    # ─────────────────────────────────────────────────────────────────────

    def load_console_history(self):
        try:
            if os.path.exists(CONSOLE_HIST):
                with open(CONSOLE_HIST) as f:
                    return json.load(f)
        except Exception:
            pass
        return []

    def save_console_history(self, history):
        try:
            with open(CONSOLE_HIST, "w") as f:
                json.dump(history[-200:], f)
        except Exception:
            pass
