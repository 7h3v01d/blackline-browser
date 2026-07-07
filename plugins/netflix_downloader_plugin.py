try:
    from PyQt6.QtWidgets import QDialog, QVBoxLayout, QPushButton, QLabel, QLineEdit, QComboBox, QProgressBar, QTextEdit, QListWidget, QListWidgetItem
    from PyQt6.QtGui import QAction
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage
    from PyQt6.QtCore import QUrl, Qt
except ImportError as e:
    print(f"Failed to import PyQt6 modules: {str(e)}")
    raise
from interceptors import Plugin
import os
import yt_dlp
import requests
from pathlib import Path

class NetflixDownloaderDialog(QDialog):
    def __init__(self, plugin, parent=None):
        super().__init__(parent)
        self.plugin = plugin
        self.setWindowTitle("Netflix Downloader")
        self.setGeometry(200, 200, 600, 600)
        self.layout = QVBoxLayout()

        # Embedded browser for Netflix login and browsing
        self.profile = QWebEngineProfile("NetflixDownloaderProfile", self)
        if getattr(self.plugin.browser, 'tor_enabled', False):
            # Tor proxy — only applied if tor_enabled is set in browser settings
            try:
                from PyQt6.QtNetwork import QNetworkProxy
                proxy = QNetworkProxy(QNetworkProxy.ProxyType.Socks5Proxy, "127.0.0.1", 9050)
                QNetworkProxy.setApplicationProxy(proxy)
            except Exception:
                pass
        self.browser = QWebEngineView()
        self.page = QWebEnginePage(self.profile, self.browser)
        self.browser.setPage(self.page)
        self.browser.setUrl(QUrl("https://www.netflix.com/login"))
        self.layout.addWidget(self.browser)

        # URL input for videos or series
        self.url_label = QLabel("Netflix Video/Series URL(s) (one per line):")
        self.layout.addWidget(self.url_label)
        self.url_input = QTextEdit()
        self.url_input.setPlaceholderText("Enter Netflix video or series URL(s), e.g., https://www.netflix.com/watch/... or https://www.netflix.com/title/...")
        self.layout.addWidget(self.url_input)

        # Episode selection for series
        self.episode_label = QLabel("Select Episodes (for series):")
        self.layout.addWidget(self.episode_label)
        self.episode_list = QListWidget()
        self.episode_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self.layout.addWidget(self.episode_list)
        self.fetch_episodes_btn = QPushButton("Fetch Episodes")
        self.fetch_episodes_btn.clicked.connect(self.fetch_episodes)
        self.layout.addWidget(self.fetch_episodes_btn)

        # Quality selection
        self.quality_label = QLabel("Video Quality:")
        self.layout.addWidget(self.quality_label)
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(["720p", "1080p"])
        self.layout.addWidget(self.quality_combo)

        # Audio and subtitle language selection
        self.audio_label = QLabel("Audio Language:")
        self.layout.addWidget(self.audio_label)
        self.audio_combo = QComboBox()
        self.audio_combo.addItems(["English", "Spanish", "French", "German", "Japanese"])
        self.layout.addWidget(self.audio_combo)

        self.subtitle_label = QLabel("Subtitle Language:")
        self.layout.addWidget(self.subtitle_label)
        self.subtitle_combo = QComboBox()
        self.subtitle_combo.addItems(["None", "English", "Spanish", "French", "German", "Japanese"])
        self.layout.addWidget(self.subtitle_combo)

        # Download button
        self.download_btn = QPushButton("Download Video(s)")
        self.download_btn.clicked.connect(self.start_download)
        self.layout.addWidget(self.download_btn)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.layout.addWidget(self.progress_bar)

        # Status label
        self.status_label = QLabel("Status: Ready")
        self.layout.addWidget(self.status_label)

        self.setLayout(self.layout)

    def fetch_episodes(self):
        """Fetch episode URLs for a series URL."""
        urls = self.url_input.toPlainText().strip().split("\n")
        if not urls:
            self.status_label.setText("Status: No URLs provided")
            self.plugin.browser.statusBar.showMessage("No URLs provided", 5000)
            return

        self.episode_list.clear()
        series_url = urls[0]  # Use first URL for fetching episodes
        if "/title/" not in series_url:
            self.status_label.setText("Status: Please enter a series URL")
            self.plugin.browser.statusBar.showMessage("Invalid series URL", 5000)
            return

        try:
            ydl_opts = {"quiet": True, "simulate": True, "get_url": True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(series_url, download=False)
                if "entries" in info:
                    for entry in info["entries"]:
                        episode_url = entry.get("webpage_url")
                        episode_title = entry.get("title", "Unknown Episode")
                        if episode_url:
                            item = QListWidgetItem(f"{episode_title} ({episode_url})")
                            item.setData(Qt.ItemDataRole.UserRole, episode_url)
                            self.episode_list.addItem(item)
                    self.status_label.setText(f"Status: Found {self.episode_list.count()} episodes")
                    self.plugin.browser.statusBar.showMessage(f"Fetched {self.episode_list.count()} episodes", 5000)
                else:
                    self.status_label.setText("Status: No episodes found")
                    self.plugin.browser.statusBar.showMessage("No episodes found", 5000)
        except Exception as e:
            self.status_label.setText(f"Status: Failed to fetch episodes ({str(e)})")
            self.plugin.browser.statusBar.showMessage(f"Failed to fetch episodes: {str(e)}", 5000)

    def start_download(self):
        """Download single video or selected episodes."""
        urls = self.url_input.toPlainText().strip().split("\n")
        selected_episodes = [item.data(Qt.ItemDataRole.UserRole) for item in self.episode_list.selectedItems()]
        if selected_episodes:
            urls = selected_episodes  # Use selected episodes if available
        if not urls:
            self.status_label.setText("Status: No URLs or episodes selected")
            self.plugin.browser.statusBar.showMessage("No URLs or episodes selected", 5000)
            return

        quality = self.quality_combo.currentText()
        audio_lang = self.audio_combo.currentText().lower()
        subtitle_lang = self.subtitle_combo.currentText().lower() if self.subtitle_combo.currentText() != "None" else None

        output_dir = Path("downloads")
        output_dir.mkdir(exist_ok=True)
        output_path = str(output_dir / "%(title)s.%(ext)s")

        ydl_opts = {
            "format": "bestvideo[height<=?{}]+bestaudio/best".format(quality.replace("p", "")),
            "outtmpl": output_path,
            "merge_output_format": "mp4",
            "quiet": True,
            "progress_hooks": [self.update_progress],
            "noplaylist": False,  # Allow playlists/series
        }

        if subtitle_lang:
            ydl_opts["sub_lang"] = subtitle_lang
            ydl_opts["writesubtitles"] = True
            ydl_opts["writeautomaticsub"] = False
            ydl_opts["sub_format"] = "srt"

        try:
            self.status_label.setText("Status: Downloading...")
            self.download_btn.setEnabled(False)
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                for url in urls:
                    if not url.startswith("https://www.netflix.com/"):
                        self.status_label.setText(f"Status: Invalid Netflix URL: {url}")
                        self.plugin.browser.statusBar.showMessage(f"Invalid Netflix URL: {url}", 5000)
                        continue
                    ydl.download([url])
            self.status_label.setText("Status: Download completed")
            self.plugin.browser.statusBar.showMessage(f"Netflix video(s) downloaded to {output_dir}", 5000)
        except Exception as e:
            self.status_label.setText(f"Status: Download failed ({str(e)})")
            self.plugin.browser.statusBar.showMessage(f"Netflix download failed: {str(e)}", 5000)
        finally:
            self.download_btn.setEnabled(True)
            self.progress_bar.setValue(0)

    def update_progress(self, d):
        if d["status"] == "downloading":
            percent = d.get("downloaded_bytes", 0) / d.get("total_bytes", 1) * 100
            self.progress_bar.setValue(int(percent))
        elif d["status"] == "finished":
            self.progress_bar.setValue(100)

class Plugin(Plugin):
    def __init__(self, browser, name="Netflix Downloader Plugin", version="1.0"):
        super().__init__(browser, name, version)

    def add_to_menu(self, menu):
        try:
            action = QAction("Netflix Downloader", self.browser)
            action.triggered.connect(self.open_dialog)
            menu.addAction(action)
        except NameError as e:
            self.browser.statusBar.showMessage(f"Netflix Downloader Plugin: QAction not available: {str(e)}", 5000)

    def open_dialog(self):
        dialog = NetflixDownloaderDialog(plugin=self, parent=self.browser)
        dialog.exec()