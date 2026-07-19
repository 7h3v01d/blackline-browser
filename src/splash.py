"""
splash.py  —  Blackline Browser boot experience

Provides:
  • BlacklineSplash        animated frameless splash (logo, sweep, boot log, progress)
  • VaultPasswordDialog    dark-industrial replacement for the QInputDialog vault prompt

House style: obsidian/teal/amber/phosphor, JetBrains Mono, zero border radius.

Usage (main.py):
    splash = BlacklineSplash()
    splash.run(5000)          # animated, blocking, ends on final frame (stays visible)
    window = WebBrowser()     # vault dialog appears over the splash
    window.show()
    splash.finish(window)     # fade out

Usage (browser.py):
    password, ok = VaultPasswordDialog.ask(vault_exists=os.path.exists("credentials.vault"))
"""

import os

from PyQt6.QtCore import (
    Qt, QTimer, QEventLoop, QRect, QRectF, QPointF, QPropertyAnimation,
    QEasingCurve, QObject, QEvent, pyqtSlot,
)
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QPixmap, QFont, QLinearGradient, QIcon,
)
from PyQt6.QtWidgets import (
    QWidget, QDialog, QLabel, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout,
    QFrame, QGraphicsDropShadowEffect, QApplication,
)

# ── Palette ──────────────────────────────────────────────────────────────────
OBSIDIAN = "#0b0f14"
PANEL    = "#0e141b"
INPUT_BG = "#11171f"
HOVER    = "#16202b"
BORDER   = "#1c2733"
STEEL    = "#253341"
TEAL     = "#2fd6c3"
AMBER    = "#ffb454"
PHOSPHOR = "#4be08a"
RED      = "#ff5c66"
TEXT     = "#e6edf3"
DIM      = "#7d8b99"
MUTED    = "#4d5b68"

MONO = "'JetBrains Mono', 'Cascadia Mono', Consolas, monospace"

APP_VERSION = "1.0"


# ── Asset helpers ────────────────────────────────────────────────────────────

def _assets_dir() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    for candidate in (
        os.path.join(os.path.dirname(here), "assets"),   # <project>/assets
        os.path.join(here, "assets"),                    # src/assets
    ):
        if os.path.isdir(candidate):
            return candidate
    return os.path.join(os.path.dirname(here), "assets")


def asset(*names) -> str:
    """Return the first existing asset path from the given filenames."""
    base = _assets_dir()
    for name in names:
        path = os.path.join(base, name)
        if os.path.exists(path):
            return path
    return ""


def load_pixmap(*names) -> QPixmap:
    path = asset(*names)
    return QPixmap(path) if path else QPixmap()


# ─────────────────────────────────────────────────────────────────────────────
# Splash screen
# ─────────────────────────────────────────────────────────────────────────────

class BlacklineSplash(QWidget):
    """
    Frameless animated splash. Everything is painted, so there is no dependency
    on the application stylesheet (which is applied later in startup).
    """

    MARGIN   = 28                      # room for the drop shadow
    CARD_W   = 660
    CARD_H   = 372

    STAGES = [
        (0.00, "INITIALISING RUNTIME"),
        (0.16, "RESOLVING WIDEVINE CDM"),
        (0.34, "COMPILING FILTER LISTS"),
        (0.55, "REGISTERING PLUGINS"),
        (0.72, "STARTING WEB ENGINE"),
        (0.88, "MOUNTING VAULT"),
        (1.00, "READY"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.SplashScreen
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(self.CARD_W + self.MARGIN * 2,
                          self.CARD_H + self.MARGIN * 2)

        self._logo = load_pixmap("splash.png", "blackline_banner_blk.png",
                                 "blackline_banner.png")
        self._progress = 0.0            # 0..1
        self._tick = 0                  # animation frames
        self._status = self.STAGES[0][1]
        self._manual_status = False

        icon_path = asset("icon.ico")
        if icon_path:
            self.setWindowIcon(QIcon(icon_path))

        # NOTE: no QGraphicsDropShadowEffect here. On Windows, a graphics effect
        # on a translucent frameless top-level window pushes the dirty rect
        # outside the window bounds, and every repaint fails with
        # "UpdateLayeredWindowIndirect failed ...". The shadow is painted
        # manually inside our own bounds instead — see _draw_shadow().

        self._timer = QTimer(self)
        self._timer.setInterval(16)     # ~60 fps
        self._timer.timeout.connect(self._on_frame)

        self._elapsed = 0
        self._duration = 5000

    # ── public API ───────────────────────────────────────────────────────────

    def run(self, duration_ms: int = 5000):
        """Show, fade in, animate for duration_ms, then hold on the final frame."""
        self._duration = max(600, int(duration_ms))
        self._elapsed = 0
        self._center_on_screen()
        self.setWindowOpacity(0.0)
        self.show()
        self.raise_()

        self._fade = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade.setDuration(260)
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)
        self._fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade.start()

        loop = QEventLoop(self)
        self._loop = loop
        self._timer.start()
        QTimer.singleShot(self._duration, loop.quit)
        loop.exec()
        self._timer.stop()

        self._progress = 1.0
        if not self._manual_status:
            self._status = self.STAGES[-1][1]
        self.update()
        QApplication.processEvents()

    def set_status(self, text: str, progress: float = None):
        """Optional: drive the splash from real startup work."""
        self._manual_status = True
        self._status = str(text).upper()
        if progress is not None:
            self._progress = max(0.0, min(1.0, float(progress)))
        self.update()
        QApplication.processEvents()

    def finish(self, window=None, fade_ms: int = 280):
        """Fade out and close. Pass the main window to raise it afterwards."""
        anim = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade_out = anim
        anim.setDuration(max(0, int(fade_ms)))
        anim.setStartValue(self.windowOpacity())
        anim.setEndValue(0.0)
        anim.setEasingCurve(QEasingCurve.Type.InCubic)

        loop = QEventLoop(self)
        anim.finished.connect(loop.quit)
        anim.start()
        loop.exec()

        self.close()
        if window is not None:
            window.raise_()
            window.activateWindow()

    # ── internals ────────────────────────────────────────────────────────────

    def _center_on_screen(self):
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        self.move(geo.center().x() - self.width() // 2,
                  geo.center().y() - self.height() // 2)

    @pyqtSlot()
    def _on_frame(self):
        self._elapsed += self._timer.interval()
        self._tick += 1
        raw = min(1.0, self._elapsed / float(self._duration))
        # ease-out so the bar sprints then settles — feels like real work
        self._progress = 1.0 - pow(1.0 - raw, 1.7)
        if not self._manual_status:
            for threshold, label in self.STAGES:
                if self._progress >= threshold:
                    self._status = label
        self.update()

    # ── painting ─────────────────────────────────────────────────────────────

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        m = self.MARGIN
        card = QRect(m, m, self.CARD_W, self.CARD_H)

        self._draw_shadow(p, card)

        # card body
        p.fillRect(card, QColor(OBSIDIAN))

        # faint vertical vignette
        grad = QLinearGradient(QPointF(card.left(), card.top()),
                               QPointF(card.left(), card.bottom()))
        grad.setColorAt(0.0, QColor(47, 214, 195, 16))
        grad.setColorAt(0.45, QColor(0, 0, 0, 0))
        grad.setColorAt(1.0, QColor(0, 0, 0, 60))
        p.fillRect(card, QBrush(grad))

        # 1px border
        p.setPen(QPen(QColor(BORDER), 1))
        p.drawRect(card.adjusted(0, 0, -1, -1))

        # top accent rail (teal → amber, sweeps with progress)
        rail = QRect(card.left(), card.top(), card.width(), 2)
        rail_grad = QLinearGradient(QPointF(rail.left(), 0), QPointF(rail.right(), 0))
        rail_grad.setColorAt(0.0, QColor(TEAL))
        rail_grad.setColorAt(max(0.02, self._progress), QColor(PHOSPHOR))
        rail_grad.setColorAt(min(1.0, self._progress + 0.001), QColor(28, 39, 51))
        rail_grad.setColorAt(1.0, QColor(28, 39, 51))
        p.fillRect(rail, QBrush(rail_grad))

        self._draw_brackets(p, card)
        self._draw_logo(p, card)
        self._draw_sweep(p, card)
        self._draw_footer(p, card)

        p.end()

    def _draw_shadow(self, p: QPainter, card: QRect):
        """Hand-rolled falloff shadow, drawn strictly inside the widget."""
        p.setBrush(Qt.BrushStyle.NoBrush)
        steps = self.MARGIN - 2
        for i in range(steps, 0, -1):
            t = i / float(steps)
            alpha = int(66 * pow(1.0 - t, 2.4))
            if alpha <= 0:
                continue
            p.setPen(QPen(QColor(0, 0, 0, alpha), 1))
            # offset down a touch so the light reads as coming from above
            p.drawRect(card.adjusted(-i, -i + 3, i, i + 3))

    def _draw_brackets(self, p: QPainter, card: QRect):
        arm, inset = 16, 10
        p.setPen(QPen(QColor(AMBER), 1))
        l, t = card.left() + inset, card.top() + inset
        r, b = card.right() - inset, card.bottom() - inset
        for (x, y, dx, dy) in ((l, t, 1, 1), (r, t, -1, 1), (l, b, 1, -1), (r, b, -1, -1)):
            p.drawLine(x, y, x + arm * dx, y)
            p.drawLine(x, y, x, y + arm * dy)

    def _draw_logo(self, p: QPainter, card: QRect):
        if self._logo.isNull():
            p.setPen(QColor(TEXT))
            f = QFont("JetBrains Mono", 30, QFont.Weight.Bold)
            f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 6)
            p.setFont(f)
            p.drawText(QRect(card.left(), card.top() + 96, card.width(), 60),
                       Qt.AlignmentFlag.AlignCenter, "BLACKLINE")
            return

        target_w = int(card.width() * 0.80)
        scaled = self._logo.scaledToWidth(
            target_w, Qt.TransformationMode.SmoothTransformation)
        x = card.left() + (card.width() - scaled.width()) // 2
        y = card.top() + 44
        # additive blend: the artwork's black backdrop melts into the card
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
        p.drawPixmap(x, y, scaled)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        self._logo_rect = QRect(x, y, scaled.width(), scaled.height())

    def _draw_sweep(self, p: QPainter, card: QRect):
        """Teal scanline sweeping down over the logo, once per ~2.2s."""
        rect = getattr(self, "_logo_rect", None)
        if rect is None:
            return
        cycle = (self._tick % 138) / 138.0
        y = rect.top() + int(cycle * rect.height())
        glow = QLinearGradient(QPointF(rect.left(), 0), QPointF(rect.right(), 0))
        glow.setColorAt(0.0, QColor(47, 214, 195, 0))
        glow.setColorAt(0.5, QColor(47, 214, 195, 70))
        glow.setColorAt(1.0, QColor(47, 214, 195, 0))
        p.fillRect(QRect(rect.left(), y, rect.width(), 1), QBrush(glow))
        p.fillRect(QRect(rect.left(), y + 1, rect.width(), 9),
                   QBrush(QColor(47, 214, 195, 5)))

    def _draw_footer(self, p: QPainter, card: QRect):
        pad = 26
        bar_y = card.bottom() - 62
        text_y = bar_y - 26

        # status line
        f = QFont("JetBrains Mono", 8)
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 2)
        p.setFont(f)

        blink = "" if (self._tick // 24) % 2 and self._progress < 1.0 else "_"
        p.setPen(QColor(DIM if self._progress < 1.0 else PHOSPHOR))
        p.drawText(QRect(card.left() + pad, text_y, card.width() - pad * 2, 18),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   f"› {self._status}{blink}")

        p.setPen(QColor(AMBER))
        p.drawText(QRect(card.left() + pad, text_y, card.width() - pad * 2, 18),
                   Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                   f"{int(self._progress * 100):3d}%")

        # progress track + fill
        track = QRect(card.left() + pad, bar_y, card.width() - pad * 2, 3)
        p.fillRect(track, QColor(BORDER))
        fill_w = int(track.width() * self._progress)
        if fill_w > 0:
            fill = QRect(track.left(), track.top(), fill_w, track.height())
            fg = QLinearGradient(QPointF(fill.left(), 0), QPointF(fill.right(), 0))
            fg.setColorAt(0.0, QColor(TEAL))
            fg.setColorAt(1.0, QColor(PHOSPHOR))
            p.fillRect(fill, QBrush(fg))
            # bright head
            p.fillRect(QRect(fill.right() - 1, fill.top() - 1, 2, 5), QColor(TEXT))

        # baseline caption
        f2 = QFont("JetBrains Mono", 7)
        f2.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 3)
        p.setFont(f2)
        p.setPen(QColor(MUTED))
        cap = QRect(card.left() + pad, card.bottom() - 40, card.width() - pad * 2, 20)
        p.drawText(cap, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   f"BLACKLINE BROWSER  v{APP_VERSION}")
        p.drawText(cap, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                   "LEON PRIEST")

    # click anywhere to skip the wait
    def mousePressEvent(self, event):
        loop = getattr(self, "_loop", None)
        if loop is not None and loop.isRunning():
            loop.quit()


# ─────────────────────────────────────────────────────────────────────────────
# Vault password dialog
# ─────────────────────────────────────────────────────────────────────────────

VAULT_QSS = f"""
#card {{
    background-color: {PANEL};
    border: 1px solid {BORDER};
}}
QLabel {{
    color: {DIM};
    font-family: {MONO};
    font-size: 11px;
    background: transparent;
}}
#title {{
    color: {TEXT};
    font-size: 13px;
    font-weight: bold;
    letter-spacing: 3px;
}}
#subtitle {{
    color: {MUTED};
    font-size: 10px;
    letter-spacing: 2px;
}}
#fieldLabel {{
    color: {TEAL};
    font-size: 10px;
    letter-spacing: 2px;
}}
#hint {{
    color: {MUTED};
    font-size: 10px;
}}
#warn {{
    color: {AMBER};
    font-size: 10px;
    letter-spacing: 1px;
}}
QLineEdit {{
    background-color: {INPUT_BG};
    border: 1px solid {STEEL};
    border-radius: 0px;
    color: {TEXT};
    font-family: {MONO};
    font-size: 13px;
    padding: 9px 10px;
    selection-background-color: {TEAL};
    selection-color: #05201c;
}}
QLineEdit:focus {{
    border: 1px solid {TEAL};
    background-color: {HOVER};
}}
QPushButton {{
    background-color: transparent;
    border: 1px solid {STEEL};
    border-radius: 0px;
    color: {DIM};
    font-family: {MONO};
    font-size: 11px;
    letter-spacing: 2px;
    padding: 8px 18px;
}}
QPushButton:hover {{
    border-color: {TEAL};
    color: {TEXT};
    background-color: {HOVER};
}}
#primary {{
    background-color: {TEAL};
    border: 1px solid {TEAL};
    color: #05201c;
    font-weight: bold;
}}
#primary:hover {{
    background-color: {PHOSPHOR};
    border-color: {PHOSPHOR};
    color: #05201c;
}}
#reveal {{
    padding: 6px 10px;
    letter-spacing: 1px;
    font-size: 10px;
}}
#close {{
    border: none;
    color: {MUTED};
    font-size: 14px;
    padding: 2px 8px;
}}
#close:hover {{
    color: {RED};
    background: transparent;
}}
"""


class _CapsWatcher(QObject):
    """Heuristic caps-lock detection: uppercase typed with no Shift held."""

    def __init__(self, on_change):
        super().__init__()
        self._on_change = on_change

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.KeyPress:
            text = event.text()
            if text and text.isalpha():
                shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
                self._on_change(text.isupper() != shift)
        return False


class VaultPasswordDialog(QDialog):
    """Dark-industrial master-password prompt. Esc or SKIP returns ok=False."""

    def __init__(self, parent=None, vault_exists: bool = True):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setModal(True)
        self.setStyleSheet(VAULT_QSS)
        self._drag_pos = None
        self._vault_exists = vault_exists

        self._build_ui()
        self.setFixedSize(self.sizeHint())
        self._center_on_screen()

    # ── construction ─────────────────────────────────────────────────────────

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 24, 24, 24)   # shadow gutter

        card = QFrame(self)
        card.setObjectName("card")
        card.setFixedWidth(420)
        outer.addWidget(card)

        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(28)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 210))
        card.setGraphicsEffect(shadow)

        lay = QVBoxLayout(card)
        lay.setContentsMargins(22, 18, 22, 20)
        lay.setSpacing(0)

        # ── header row ──
        header = QHBoxLayout()
        header.setSpacing(10)

        mark = QLabel()
        pix = load_pixmap("Blackwell symbol logo_128.png", "Blackwell symbol logo.png")
        if not pix.isNull():
            mark.setPixmap(pix.scaled(26, 26,
                                      Qt.AspectRatioMode.KeepAspectRatio,
                                      Qt.TransformationMode.SmoothTransformation))
        header.addWidget(mark)

        titles = QVBoxLayout()
        titles.setSpacing(2)
        title = QLabel("VAULT ACCESS")
        title.setObjectName("title")
        subtitle = QLabel("UNLOCK CREDENTIAL STORE" if self._vault_exists
                          else "CREATE NEW CREDENTIAL STORE")
        subtitle.setObjectName("subtitle")
        titles.addWidget(title)
        titles.addWidget(subtitle)
        header.addLayout(titles)
        header.addStretch(1)

        close_btn = QPushButton("✕")
        close_btn.setObjectName("close")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.reject)
        header.addWidget(close_btn, 0, Qt.AlignmentFlag.AlignTop)
        lay.addLayout(header)

        lay.addSpacing(16)
        rule = QFrame()
        rule.setFixedHeight(1)
        rule.setStyleSheet(f"background-color: {BORDER};")
        lay.addWidget(rule)
        lay.addSpacing(18)

        # ── field ──
        field_label = QLabel("MASTER PASSWORD")
        field_label.setObjectName("fieldLabel")
        lay.addWidget(field_label)
        lay.addSpacing(7)

        row = QHBoxLayout()
        row.setSpacing(6)
        self.edit = QLineEdit()
        self.edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.edit.setPlaceholderText("••••••••••••")
        self.edit.returnPressed.connect(self._on_accept)
        row.addWidget(self.edit, 1)

        self.reveal_btn = QPushButton("SHOW")
        self.reveal_btn.setObjectName("reveal")
        self.reveal_btn.setCheckable(True)
        self.reveal_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.reveal_btn.toggled.connect(self._toggle_reveal)
        row.addWidget(self.reveal_btn)
        lay.addLayout(row)

        lay.addSpacing(8)
        self.notice = QLabel("Cancel or press Esc to run without the password manager.")
        self.notice.setObjectName("hint")
        self.notice.setWordWrap(True)
        lay.addWidget(self.notice)

        # always present so the fixed dialog height reserves room for it
        self.caps = QLabel(" ")
        self.caps.setObjectName("warn")
        lay.addWidget(self.caps)

        self._caps_watcher = _CapsWatcher(self._set_caps)
        self.edit.installEventFilter(self._caps_watcher)

        lay.addSpacing(20)

        # ── buttons ──
        btns = QHBoxLayout()
        btns.setSpacing(8)
        btns.addStretch(1)

        skip = QPushButton("SKIP")
        skip.setCursor(Qt.CursorShape.PointingHandCursor)
        skip.clicked.connect(self.reject)
        btns.addWidget(skip)

        unlock = QPushButton("UNLOCK" if self._vault_exists else "CREATE")
        unlock.setObjectName("primary")
        unlock.setDefault(True)
        unlock.setCursor(Qt.CursorShape.PointingHandCursor)
        unlock.clicked.connect(self._on_accept)
        btns.addWidget(unlock)
        lay.addLayout(btns)

    # ── behaviour ────────────────────────────────────────────────────────────

    def _center_on_screen(self):
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        self.move(geo.center().x() - self.sizeHint().width() // 2,
                  geo.center().y() - self.sizeHint().height() // 2)

    @pyqtSlot(bool)
    def _toggle_reveal(self, on: bool):
        self.edit.setEchoMode(QLineEdit.EchoMode.Normal if on
                              else QLineEdit.EchoMode.Password)
        self.reveal_btn.setText("HIDE" if on else "SHOW")

    def _set_caps(self, on: bool):
        self.caps.setText("⚠  CAPS LOCK APPEARS TO BE ON" if on else " ")

    @pyqtSlot()
    def _on_accept(self):
        if not self.edit.text():
            self.edit.setStyleSheet(f"QLineEdit {{ border: 1px solid {RED}; }}")
            QTimer.singleShot(700, lambda: self.edit.setStyleSheet(""))
            return
        self.accept()

    def password(self) -> str:
        return self.edit.text()

    # frameless drag
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    # ── convenience ──────────────────────────────────────────────────────────

    @staticmethod
    def ask(parent=None, vault_exists: bool = True):
        """Returns (password, ok) — drop-in replacement for QInputDialog.getText."""
        dlg = VaultPasswordDialog(parent, vault_exists=vault_exists)
        ok = dlg.exec() == QDialog.DialogCode.Accepted
        return (dlg.password() if ok else ""), ok


# ── standalone preview:  python src/splash.py ────────────────────────────────
if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)
    s = BlacklineSplash()
    s.run(5000)
    pwd, ok = VaultPasswordDialog.ask(vault_exists=True)
    print("password entered:", bool(pwd), "ok:", ok)
    s.finish()
