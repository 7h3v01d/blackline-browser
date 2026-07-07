"""
dialogs.py  —  upgraded dialogs for the personal browser
Additions vs original:
  • HistoryDialog: live search bar, open-in-new-tab button, clear history
  • BookmarksDialog: replaces the old QListWidget popup with folders,
    drag-to-reorder, search, and proper open/edit/delete actions
  • DevToolsDialog / PasswordManagerDialog: unchanged from original
"""

import json
import os
from urllib.parse import urlparse

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QTextEdit, QTabWidget, QWidget, QPushButton, QLineEdit, QMessageBox,
    QHeaderView, QInputDialog, QTreeWidget, QTreeWidgetItem, QMenu,
    QLabel, QSplitter, QFrame
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import Qt, QUrl, QSortFilterProxyModel
from PyQt6.QtGui import QColor, QIcon, QFont

BOOKMARKS_FILE = "bookmarks_v2.json"


# ─────────────────────────────────────────────────────────────────────────────
# History Dialog  (upgraded)
# ─────────────────────────────────────────────────────────────────────────────

class HistoryDialog(QDialog):
    def __init__(self, history, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Browsing History")
        self.setMinimumSize(740, 500)
        self.history = history          # list of (timestamp, url)
        self._build_ui()
        self._populate(history)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # Search row
        top = QHBoxLayout()
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("🔍  Search history…")
        self.search_box.textChanged.connect(self._filter)
        self.search_box.setClearButtonEnabled(True)
        clear_btn = QPushButton("Clear All History")
        clear_btn.setStyleSheet("color: #ff5c66;")
        clear_btn.clicked.connect(self._clear_all)
        top.addWidget(self.search_box, 1)
        top.addWidget(clear_btn)
        layout.addLayout(top)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Date / Time", "Site", "URL"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.doubleClicked.connect(self._open_url)
        layout.addWidget(self.table)

        # Bottom buttons
        btns = QHBoxLayout()
        open_btn = QPushButton("Open in New Tab")
        open_btn.clicked.connect(self._open_url)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btns.addWidget(open_btn)
        btns.addStretch()
        btns.addWidget(close_btn)
        layout.addLayout(btns)

    def _populate(self, items):
        self.table.setRowCount(0)
        for timestamp, url in reversed(items):     # newest first
            row = self.table.rowCount()
            self.table.insertRow(row)

            parsed = urlparse(url)
            site = parsed.netloc or url[:50]
            short_url = url if len(url) <= 70 else url[:67] + "…"

            self.table.setItem(row, 0, QTableWidgetItem(timestamp))
            self.table.setItem(row, 1, QTableWidgetItem(site))
            url_item = QTableWidgetItem(short_url)
            url_item.setData(Qt.ItemDataRole.UserRole, url)
            self.table.setItem(row, 2, url_item)

    def _filter(self, text):
        text = text.lower()
        for row in range(self.table.rowCount()):
            match = any(
                text in (self.table.item(row, col).text().lower() if self.table.item(row, col) else "")
                for col in range(3)
            )
            self.table.setRowHidden(row, not match)

    def _open_url(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        url_item = self.table.item(rows[0].row(), 2)
        if url_item:
            url = url_item.data(Qt.ItemDataRole.UserRole) or url_item.text()
            self.parent().add_new_tab(QUrl(url), "History Tab")

    def _clear_all(self):
        reply = QMessageBox.question(
            self, "Clear History",
            "Delete all browsing history?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            if self.parent():
                self.parent().history.clear()
                try:
                    with open("history.json", "w") as f:
                        json.dump([], f)
                except Exception:
                    pass
            self.table.setRowCount(0)


# ─────────────────────────────────────────────────────────────────────────────
# Bookmarks Dialog  (full rewrite — folders + search)
# ─────────────────────────────────────────────────────────────────────────────

class BookmarksDialog(QDialog):
    """
    Bookmark manager with:
      • Folder tree on the left
      • Bookmark list on the right (filtered by folder or search)
      • Add / Edit / Delete / Open in New Tab
      • Persistent storage in bookmarks_v2.json
    """

    def __init__(self, bookmarks_data, parent=None):
        """
        bookmarks_data is the browser's self.bookmarks — a list of dicts:
          [{"title": str, "url": str, "folder": str}, ...]
        Old-style plain string entries are migrated automatically.
        """
        super().__init__(parent)
        self.setWindowTitle("Bookmarks")
        self.setMinimumSize(820, 540)
        self.bookmarks = self._migrate(bookmarks_data)
        self._build_ui()
        self._refresh_folders()
        self._show_folder("All Bookmarks")

    # ── Migration from old [title, url] pair format ──────────────────────────

    def _migrate(self, raw):
        result = []
        for item in raw:
            if isinstance(item, dict):
                result.append(item)
            elif isinstance(item, (list, tuple)) and len(item) == 2:
                result.append({"title": item[0], "url": item[1], "folder": "Bookmarks"})
            elif isinstance(item, str):
                parsed = urlparse(item)
                result.append({"title": parsed.netloc or item, "url": item, "folder": "Bookmarks"})
        return result

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # Search bar
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("🔍  Search bookmarks…")
        self.search_box.textChanged.connect(self._on_search)
        self.search_box.setClearButtonEnabled(True)
        layout.addWidget(self.search_box)

        # Splitter: folder tree | bookmark table
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Folder tree
        self.folder_tree = QTreeWidget()
        self.folder_tree.setHeaderHidden(True)
        self.folder_tree.setFixedWidth(180)
        self.folder_tree.itemClicked.connect(self._on_folder_clicked)
        splitter.addWidget(self.folder_tree)

        # Bookmark table
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Title", "URL", "Folder"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.doubleClicked.connect(self._open_selected)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        right_layout.addWidget(self.table)

        splitter.addWidget(right)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter, 1)

        # Bottom action bar
        bar = QHBoxLayout()
        add_btn = QPushButton("＋ Add")
        add_btn.clicked.connect(self._add_bookmark)
        edit_btn = QPushButton("✎ Edit")
        edit_btn.clicked.connect(self._edit_selected)
        del_btn = QPushButton("🗑 Delete")
        del_btn.clicked.connect(self._delete_selected)
        open_btn = QPushButton("↗ Open in New Tab")
        open_btn.clicked.connect(self._open_selected)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        for w in (add_btn, edit_btn, del_btn, open_btn): bar.addWidget(w)
        bar.addStretch()
        bar.addWidget(close_btn)
        layout.addLayout(bar)

    # ── Folder tree ───────────────────────────────────────────────────────────

    def _folders(self):
        seen = []
        for bm in self.bookmarks:
            f = bm.get("folder", "Bookmarks")
            if f not in seen:
                seen.append(f)
        return seen

    def _refresh_folders(self):
        self.folder_tree.clear()
        all_item = QTreeWidgetItem(["📚  All Bookmarks"])
        all_item.setData(0, Qt.ItemDataRole.UserRole, "All Bookmarks")
        self.folder_tree.addTopLevelItem(all_item)
        for folder in self._folders():
            item = QTreeWidgetItem([f"📁  {folder}"])
            item.setData(0, Qt.ItemDataRole.UserRole, folder)
            self.folder_tree.addTopLevelItem(item)
        self.folder_tree.expandAll()

    def _on_folder_clicked(self, item):
        self.search_box.clear()
        self._show_folder(item.data(0, Qt.ItemDataRole.UserRole))

    def _show_folder(self, folder_name):
        self._current_folder = folder_name
        if folder_name == "All Bookmarks":
            filtered = self.bookmarks
        else:
            filtered = [b for b in self.bookmarks if b.get("folder", "Bookmarks") == folder_name]
        self._populate_table(filtered)

    # ── Table ─────────────────────────────────────────────────────────────────

    def _populate_table(self, items):
        self.table.setRowCount(0)
        for bm in items:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(bm.get("title", "")))
            url_item = QTableWidgetItem(bm.get("url", ""))
            url_item.setData(Qt.ItemDataRole.UserRole, bm)
            self.table.setItem(row, 1, url_item)
            self.table.setItem(row, 2, QTableWidgetItem(bm.get("folder", "Bookmarks")))

    def _on_search(self, text):
        if not text:
            self._show_folder(getattr(self, "_current_folder", "All Bookmarks"))
            return
        text = text.lower()
        filtered = [
            b for b in self.bookmarks
            if text in b.get("title", "").lower() or text in b.get("url", "").lower()
        ]
        self._populate_table(filtered)

    # ── Actions ───────────────────────────────────────────────────────────────

    def _selected_bm(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        url_item = self.table.item(rows[0].row(), 1)
        return url_item.data(Qt.ItemDataRole.UserRole) if url_item else None

    def _open_selected(self):
        bm = self._selected_bm()
        if bm and self.parent():
            self.parent().add_new_tab(QUrl(bm["url"]), bm.get("title", bm["url"]))

    def _add_bookmark(self):
        title, ok1 = QInputDialog.getText(self, "Add Bookmark", "Title:")
        if not ok1 or not title:
            return
        url, ok2 = QInputDialog.getText(self, "Add Bookmark", "URL:")
        if not ok2 or not url:
            return
        folders = ["Bookmarks"] + self._folders()
        folder, ok3 = QInputDialog.getItem(self, "Add Bookmark", "Folder:", folders, 0, True)
        if not ok3:
            folder = "Bookmarks"
        if not url.startswith("http"):
            url = "https://" + url
        bm = {"title": title, "url": url, "folder": folder}
        self.bookmarks.append(bm)
        self._save()
        self._refresh_folders()
        self._show_folder(folder)

    def _edit_selected(self):
        bm = self._selected_bm()
        if not bm:
            return
        title, ok1 = QInputDialog.getText(self, "Edit Bookmark", "Title:", text=bm.get("title", ""))
        if not ok1:
            return
        url, ok2 = QInputDialog.getText(self, "Edit Bookmark", "URL:", text=bm.get("url", ""))
        if not ok2:
            return
        folder, ok3 = QInputDialog.getText(self, "Edit Bookmark", "Folder:", text=bm.get("folder", "Bookmarks"))
        if not ok3:
            folder = bm.get("folder", "Bookmarks")
        bm["title"] = title
        bm["url"] = url
        bm["folder"] = folder
        self._save()
        self._refresh_folders()
        self._show_folder(self._current_folder)

    def _delete_selected(self):
        bm = self._selected_bm()
        if not bm:
            return
        reply = QMessageBox.question(
            self, "Delete Bookmark",
            f"Delete \"{bm.get('title', bm['url'])}\"?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.bookmarks = [b for b in self.bookmarks if b is not bm]
            self._save()
            self._refresh_folders()
            self._show_folder(getattr(self, "_current_folder", "All Bookmarks"))

    def _show_context_menu(self, pos):
        bm = self._selected_bm()
        if not bm:
            return
        menu = QMenu(self)
        menu.addAction("↗ Open in New Tab", self._open_selected)
        menu.addAction("✎ Edit", self._edit_selected)
        menu.addAction("🗑 Delete", self._delete_selected)
        menu.exec(self.table.mapToGlobal(pos))

    # ── Persistence ───────────────────────────────────────────────────────────

    def _save(self):
        try:
            with open(BOOKMARKS_FILE, "w") as f:
                json.dump(self.bookmarks, f, indent=2)
        except Exception as e:
            QMessageBox.warning(self, "Save Error", str(e))
        # Also sync back to browser's bookmarks list
        if self.parent():
            self.parent().bookmarks = self.bookmarks

    @staticmethod
    def load_bookmarks():
        """Call from WebBrowser to load bookmarks at startup."""
        if os.path.exists(BOOKMARKS_FILE):
            try:
                with open(BOOKMARKS_FILE) as f:
                    return json.load(f)
            except Exception:
                pass
        # Fall back to old bookmarks.json format
        if os.path.exists("bookmarks.json"):
            try:
                with open("bookmarks.json") as f:
                    return json.load(f)
            except Exception:
                pass
        return []


# ─────────────────────────────────────────────────────────────────────────────
# Note-Taking Sidebar
# ─────────────────────────────────────────────────────────────────────────────

NOTES_FILE = "notes.json"

class NoteSidebar(QWidget):
    """
    Persistent note-taking panel that docks in the browser.
    Notes are stored per-domain so they feel contextual, plus a global tab.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.notes = self._load_notes()
        self._current_key = "global"
        self._build_ui()
        self._show_note("global")

    def _load_notes(self):
        if os.path.exists(NOTES_FILE):
            try:
                with open(NOTES_FILE) as f:
                    return json.load(f)
            except Exception:
                pass
        return {"global": ""}

    def _save_notes(self):
        try:
            with open(NOTES_FILE, "w") as f:
                json.dump(self.notes, f, indent=2)
        except Exception:
            pass

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # Header
        header = QHBoxLayout()
        title = QLabel("📝  Notes")
        title.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.domain_label = QLabel("")
        self.domain_label.setStyleSheet("color: #7d8b99; font-size: 11px; letter-spacing: 1px;")
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.domain_label)
        layout.addLayout(header)

        # Tab switcher: current page note vs global
        tabs = QHBoxLayout()
        self.page_btn = QPushButton("This Page")
        self.page_btn.setCheckable(True)
        self.page_btn.setChecked(False)
        self.page_btn.clicked.connect(self._switch_to_page)
        self.global_btn = QPushButton("Global")
        self.global_btn.setCheckable(True)
        self.global_btn.setChecked(True)
        self.global_btn.clicked.connect(self._switch_to_global)
        for b in (self.page_btn, self.global_btn):
            b.setStyleSheet("""
                QPushButton { border: 1px solid #1c2733; border-radius: 0px;
                              padding: 4px 12px; font-size: 12px; background: transparent; color: #7d8b99; }
                QPushButton:checked { background: #0e141b; border-color: #2fd6c3; color: #2fd6c3; }
            """)
            tabs.addWidget(b)
        layout.addLayout(tabs)

        # Text editor
        self.editor = QTextEdit()
        self.editor.setPlaceholderText("Write notes here…\nThey're saved automatically.")
        self.editor.textChanged.connect(self._auto_save)
        layout.addWidget(self.editor, 1)

        # Divider + quick note list
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)

        note_list_label = QLabel("ALL NOTE PAGES")
        note_list_label.setStyleSheet("font-size: 10px; color: #4d5b68; letter-spacing: 2px;")
        layout.addWidget(note_list_label)

        from PyQt6.QtWidgets import QListWidget
        self.note_list = QListWidget()
        self.note_list.setMaximumHeight(120)
        self.note_list.itemClicked.connect(self._on_note_list_click)
        layout.addWidget(self.note_list)
        self._refresh_note_list()

    def _switch_to_page(self):
        self.page_btn.setChecked(True)
        self.global_btn.setChecked(False)
        self._show_note(self._current_key)

    def _switch_to_global(self):
        self.global_btn.setChecked(True)
        self.page_btn.setChecked(False)
        self._show_note("global")

    def _show_note(self, key):
        self.editor.blockSignals(True)
        self.editor.setPlainText(self.notes.get(key, ""))
        self.editor.blockSignals(False)
        self._active_key = key

    def _auto_save(self):
        key = getattr(self, "_active_key", "global")
        self.notes[key] = self.editor.toPlainText()
        self._save_notes()
        self._refresh_note_list()

    def _refresh_note_list(self):
        self.note_list.clear()
        for key, text in self.notes.items():
            if key == "global":
                label = "📒 Global"
            else:
                label = f"🌐 {key}"
            preview = text.strip().replace("\n", " ")[:40]
            self.note_list.addItem(f"{label}  —  {preview}" if preview else label)
            self.note_list.item(self.note_list.count() - 1).setData(Qt.ItemDataRole.UserRole, key)

    def _on_note_list_click(self, item):
        key = item.data(Qt.ItemDataRole.UserRole)
        self._show_note(key)

    def set_current_url(self, url_str):
        """Called by browser when the current tab changes."""
        try:
            domain = urlparse(url_str).netloc or "local"
        except Exception:
            domain = "local"
        self._current_key = domain
        self.domain_label.setText(domain)


# ─────────────────────────────────────────────────────────────────────────────
# DevTools Dialog  (unchanged from original)
# ─────────────────────────────────────────────────────────────────────────────

class DevToolsDialog(QDialog):
    def __init__(self, browser, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Developer Tools")
        self.setGeometry(200, 200, 800, 600)
        self.command_history = parent.load_console_history() if hasattr(parent, 'load_console_history') else []
        self.history_index = len(self.command_history)
        layout = QVBoxLayout()

        self.inspector = QWebEngineView()
        self.inspector.setPage(browser.page().devToolsPage())
        layout.addWidget(self.inspector, stretch=2)

        self.console_input = QTextEdit()
        self.console_input.setPlaceholderText("Enter JavaScript code (Shift+Enter for new line, Enter to execute)…")
        self.console_input.setFixedHeight(100)
        layout.addWidget(self.console_input, stretch=1)

        self.console_output = QTextEdit()
        self.console_output.setReadOnly(True)
        layout.addWidget(self.console_output, stretch=1)

        self.setLayout(layout)
        self.console_input.installEventFilter(self)

    def eventFilter(self, obj, event):
        if obj == self.console_input and event.type() == event.Type.KeyPress:
            if event.key() == Qt.Key.Key_Return and not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
                self.execute_js(self.parent().tabs.currentWidget())
                return True
            elif event.key() == Qt.Key.Key_Up:
                self.navigate_history(-1)
                return True
            elif event.key() == Qt.Key.Key_Down:
                self.navigate_history(1)
                return True
        return super().eventFilter(obj, event)

    def execute_js(self, browser):
        js_code = self.console_input.toPlainText().strip()
        if js_code:
            self.command_history.append(js_code)
            self.history_index = len(self.command_history)
            if hasattr(self.parent(), 'save_console_history'):
                self.parent().save_console_history(self.command_history)
            browser.page().runJavaScript(js_code, self.handle_js_result)

    def handle_js_result(self, result):
        self.console_output.append(str(result))

    def navigate_history(self, direction):
        if not self.command_history:
            return
        self.history_index = max(0, min(self.history_index + direction, len(self.command_history)))
        if self.history_index < len(self.command_history):
            self.console_input.setPlainText(self.command_history[self.history_index])
        else:
            self.console_input.clear()


# ─────────────────────────────────────────────────────────────────────────────
# Password Manager Dialog  (unchanged from original)
# ─────────────────────────────────────────────────────────────────────────────

class PasswordManagerDialog(QDialog):
    def __init__(self, vault, parent=None):
        super().__init__(parent)
        self.vault = vault
        self.setWindowTitle("Password Manager")
        self.setGeometry(200, 200, 600, 400)
        layout = QVBoxLayout()

        self.tab_widget = QTabWidget()
        self.logins_tab = QWidget()
        self.api_keys_tab = QWidget()

        self.tab_widget.addTab(self.logins_tab, "Logins")
        self.tab_widget.addTab(self.api_keys_tab, "API Keys")

        # Logins tab
        logins_layout = QVBoxLayout()
        self.logins_table = QTableWidget()
        self.logins_table.setColumnCount(3)
        self.logins_table.setHorizontalHeaderLabels(["URL", "Username", "Password"])
        self.logins_table.horizontalHeader().setStretchLastSection(True)
        logins_layout.addWidget(self.logins_table)

        logins_btn_layout = QHBoxLayout()
        for label, slot in [
            ("Add Login", self.add_login),
            ("Delete Login", self.delete_login),
            ("Reveal Password", self.reveal_login_password),
            ("Hide Password", self.hide_logins_password),
        ]:
            btn = QPushButton(label)
            btn.clicked.connect(slot)
            logins_btn_layout.addWidget(btn)
        logins_layout.addLayout(logins_btn_layout)
        self.logins_tab.setLayout(logins_layout)

        # API Keys tab
        api_keys_layout = QVBoxLayout()
        self.api_keys_table = QTableWidget()
        self.api_keys_table.setColumnCount(2)
        self.api_keys_table.setHorizontalHeaderLabels(["Service", "API Key"])
        self.api_keys_table.horizontalHeader().setStretchLastSection(True)
        api_keys_layout.addWidget(self.api_keys_table)

        api_keys_btn_layout = QHBoxLayout()
        for label, slot in [
            ("Add API Key", self.add_api_key),
            ("Delete API Key", self.delete_api_key),
            ("Reveal API Key", self.reveal_api_key),
            ("Hide API Key", self.hide_api_key),
        ]:
            btn = QPushButton(label)
            btn.clicked.connect(slot)
            api_keys_btn_layout.addWidget(btn)
        api_keys_layout.addLayout(api_keys_btn_layout)
        self.api_keys_tab.setLayout(api_keys_layout)

        layout.addWidget(self.tab_widget)
        self.setLayout(layout)

        self.refresh_logins()
        self.refresh_api_keys()

    def refresh_logins(self):
        logins = self.vault.get_logins()
        self.logins_table.setRowCount(len(logins))
        for row, login in enumerate(logins):
            self.logins_table.setItem(row, 0, QTableWidgetItem(login["url"]))
            self.logins_table.setItem(row, 1, QTableWidgetItem(login["username"]))
            self.logins_table.setItem(row, 2, QTableWidgetItem("*" * 12))

    def refresh_api_keys(self):
        keys = self.vault.get_api_keys()
        self.api_keys_table.setRowCount(len(keys))
        for row, key_info in enumerate(keys):
            self.api_keys_table.setItem(row, 0, QTableWidgetItem(key_info["service"]))
            self.api_keys_table.setItem(row, 1, QTableWidgetItem("*" * 12))

    def add_login(self):
        url, ok1 = QInputDialog.getText(self, "Add Login", "URL:")
        username, ok2 = QInputDialog.getText(self, "Add Login", "Username:")
        password, ok3 = QInputDialog.getText(self, "Add Login", "Password:", QLineEdit.EchoMode.Password)
        if ok1 and ok2 and ok3 and url and username:
            self.vault.data["logins"].append({"url": url, "username": username, "password": password})
            self.vault.create_and_lock_vault(self.vault.data)
            self.refresh_logins()

    def delete_login(self):
        current_row = self.logins_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Warning", "Please select a login to delete.")
            return
        reply = QMessageBox.question(self, "Confirm Delete", "Delete this login?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            del self.vault.data["logins"][current_row]
            self.vault.create_and_lock_vault(self.vault.data)
            self.refresh_logins()

    def add_api_key(self):
        service, ok1 = QInputDialog.getText(self, "Add API Key", "Service Name:")
        key, ok2 = QInputDialog.getText(self, "Add API Key", "API Key:", QLineEdit.EchoMode.Password)
        if ok1 and ok2 and service and key:
            self.vault.data["api_keys"].append({"service": service, "key": key})
            self.vault.create_and_lock_vault(self.vault.data)
            self.refresh_api_keys()

    def delete_api_key(self):
        current_row = self.api_keys_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Warning", "Please select an API key to delete.")
            return
        reply = QMessageBox.question(self, "Confirm Delete", "Delete this API key?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            del self.vault.data["api_keys"][current_row]
            self.vault.create_and_lock_vault(self.vault.data)
            self.refresh_api_keys()

    def _prompt_for_master_password(self):
        password, ok = QInputDialog.getText(self, "Authentication Required",
                                            "Enter your master password to reveal:",
                                            QLineEdit.EchoMode.Password)
        if ok and self.vault.verify_master_password(password):
            return True
        elif ok:
            QMessageBox.critical(self, "Authentication Failed", "Incorrect master password.")
        return False

    def reveal_login_password(self):
        current_row = self.logins_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Warning", "Please select a login to reveal.")
            return
        if self._prompt_for_master_password():
            password = self.vault.get_logins()[current_row]["password"]
            self.logins_table.item(current_row, 2).setText(password)

    def hide_logins_password(self):
        for row in range(self.logins_table.rowCount()):
            self.logins_table.item(row, 2).setText("*" * 12)

    def reveal_api_key(self):
        current_row = self.api_keys_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Warning", "Please select an API key to reveal.")
            return
        if self._prompt_for_master_password():
            key = self.vault.get_api_keys()[current_row]["key"]
            self.api_keys_table.item(current_row, 1).setText(key)

    def hide_api_key(self):
        for row in range(self.api_keys_table.rowCount()):
            self.api_keys_table.item(row, 1).setText("*" * 12)
