try:
    from PyQt6.QtWidgets import QDialog, QVBoxLayout, QPushButton, QLabel, QComboBox, QHBoxLayout, QFileDialog, QWidget
    from PyQt6.QtGui import QAction, QPixmap, QImage, QPainter, QPen
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
    from PyQt6.QtCore import Qt, QDateTime, QPoint, QRect
except ImportError as e:
    print(f"Failed to import PyQt6 modules: {str(e)}")
    raise
from interceptors import Plugin
from PIL import Image
from pathlib import Path
import os

class SelectionOverlay(QWidget):
    """Custom widget for selecting a screenshot region."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setStyleSheet("background: rgba(255, 0, 0, 0.1);")
        self.start_pos = None
        self.end_pos = None
        self.selection_rect = None

    def mousePressEvent(self, event):
        self.start_pos = event.position().toPoint()
        self.end_pos = self.start_pos
        self.selection_rect = QRect(self.start_pos, self.end_pos)
        self.update()

    def mouseMoveEvent(self, event):
        if self.start_pos:
            self.end_pos = event.position().toPoint()
            self.selection_rect = QRect(self.start_pos, self.end_pos).normalized()
            self.update()

    def mouseReleaseEvent(self, event):
        self.end_pos = event.position().toPoint()
        self.selection_rect = QRect(self.start_pos, self.end_pos).normalized()
        self.update()

    def paintEvent(self, event):
        if self.selection_rect:
            painter = QPainter(self)
            painter.setPen(QPen(Qt.GlobalColor.red, 2, Qt.PenStyle.DashLine))
            painter.drawRect(self.selection_rect)

class ScreenshotDialog(QDialog):
    def __init__(self, plugin, parent=None):
        super().__init__(parent)
        self.plugin = plugin
        self.browser = self.plugin.browser.tabs.currentWidget()
        self.setWindowTitle("Screenshot Webpage")
        self.setGeometry(200, 200, 600, 400)
        self.layout = QVBoxLayout()

        # Ensure JavaScript is enabled
        if self.browser:
            settings = self.browser.page().settings()
            settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)

        # Capture mode selection
        self.mode_label = QLabel("Capture Mode:")
        self.layout.addWidget(self.mode_label)
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Full Page", "Chosen Section"])
        self.mode_combo.currentTextChanged.connect(self.toggle_mode)
        self.layout.addWidget(self.mode_combo)

        # Preview label
        self.preview_label = QLabel("Preview (scaled):")
        self.layout.addWidget(self.preview_label)
        self.preview = QLabel()
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.preview)

        # Buttons
        self.button_layout = QHBoxLayout()
        self.capture_btn = QPushButton("Capture Screenshot")
        self.capture_btn.clicked.connect(self.capture_screenshot)
        self.button_layout.addWidget(self.capture_btn)
        self.save_btn = QPushButton("Save Screenshot")
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self.save_screenshot)
        self.button_layout.addWidget(self.save_btn)
        self.layout.addLayout(self.button_layout)

        # Status label
        self.status_label = QLabel("Status: Ready")
        self.layout.addWidget(self.status_label)

        self.setLayout(self.layout)
        self.screenshot = None
        self.selection_overlay = None

    def toggle_mode(self, mode):
        """Show/hide selection overlay based on mode."""
        if mode == "Chosen Section" and self.browser:
            if not self.selection_overlay:
                self.selection_overlay = SelectionOverlay(self.browser)
                self.selection_overlay.setGeometry(self.browser.rect())
                self.selection_overlay.show()
            self.status_label.setText("Status: Click and drag to select a region")
        else:
            if self.selection_overlay:
                self.selection_overlay.hide()
                self.selection_overlay = None
            self.status_label.setText("Status: Ready")

    def capture_screenshot(self):
        """Capture full page or selected section."""
        if not self.browser:
            self.status_label.setText("Status: No active tab")
            self.plugin.browser.statusBar.showMessage("No active tab for screenshot", 5000)
            return

        try:
            self.status_label.setText("Status: Capturing...")
            self.capture_btn.setEnabled(False)

            if self.mode_combo.currentText() == "Full Page":
                # Capture full page
                self.browser.page().toHtml(lambda _: self.capture_full_page())
            else:
                # Capture selected section
                if not self.selection_overlay or not self.selection_overlay.selection_rect:
                    self.status_label.setText("Status: No valid selection")
                    self.plugin.browser.statusBar.showMessage("No valid selection made", 5000)
                    self.capture_btn.setEnabled(True)
                    return
                self.capture_selected_section()

        except Exception as e:
            self.status_label.setText(f"Status: Capture failed ({str(e)})")
            self.plugin.browser.statusBar.showMessage(f"Screenshot failed: {str(e)}", 5000)
            self.capture_btn.setEnabled(True)

    def capture_full_page(self):
        """Capture the entire webpage."""
        try:
            # Get page dimensions
            self.browser.page().runJavaScript("""
                ({
                    width: Math.max(document.body.scrollWidth, document.documentElement.scrollWidth),
                    height: Math.max(document.body.scrollHeight, document.documentElement.scrollHeight)
                })
            """, lambda result: self.render_full_page(result))

        except Exception as e:
            self.status_label.setText(f"Status: Capture failed ({str(e)})")
            self.plugin.browser.statusBar.showMessage(f"Screenshot failed: {str(e)}", 5000)
            self.capture_btn.setEnabled(True)

    def render_full_page(self, dimensions):
        """Render full page with adjusted viewport."""
        try:
            width = dimensions.get("width", 1920)
            height = dimensions.get("height", 1080)
            self.browser.setFixedSize(width, height)
            self.browser.grab().save("temp_screenshot.png")
            self.screenshot = QPixmap("temp_screenshot.png")
            self.browser.setFixedSize(self.plugin.browser.width(), self.plugin.browser.height())
            os.remove("temp_screenshot.png")

            # Show preview (scaled)
            scaled_screenshot = self.screenshot.scaled(580, 300, Qt.AspectRatioMode.KeepAspectRatio)
            self.preview.setPixmap(scaled_screenshot)
            self.status_label.setText("Status: Screenshot captured")
            self.plugin.browser.statusBar.showMessage("Screenshot captured successfully", 5000)
            self.save_btn.setEnabled(True)
        except Exception as e:
            self.status_label.setText(f"Status: Capture failed ({str(e)})")
            self.plugin.browser.statusBar.showMessage(f"Screenshot failed: {str(e)}", 5000)
        finally:
            self.capture_btn.setEnabled(True)

    def capture_selected_section(self):
        """Capture the selected section."""
        try:
            rect = self.selection_overlay.selection_rect
            x, y, width, height = rect.x(), rect.y(), rect.width(), rect.height()
            if width <= 0 or height <= 0:
                self.status_label.setText("Status: Invalid selection size")
                self.plugin.browser.statusBar.showMessage("Invalid selection size", 5000)
                self.capture_btn.setEnabled(True)
                return

            # Capture viewport
            screenshot = self.browser.grab()
            screenshot.save("temp_screenshot.png")
            image = Image.open("temp_screenshot.png")
            cropped_image = image.crop((x, y, x + width, y + height))
            cropped_image.save("temp_cropped.png")
            self.screenshot = QPixmap("temp_cropped.png")
            os.remove("temp_screenshot.png")
            os.remove("temp_cropped.png")

            # Show preview (scaled)
            scaled_screenshot = self.screenshot.scaled(580, 300, Qt.AspectRatioMode.KeepAspectRatio)
            self.preview.setPixmap(scaled_screenshot)
            self.status_label.setText("Status: Screenshot captured")
            self.plugin.browser.statusBar.showMessage("Screenshot captured successfully", 5000)
            self.save_btn.setEnabled(True)

            # Hide overlay after capture
            if self.selection_overlay:
                self.selection_overlay.hide()
                self.selection_overlay = None
        except Exception as e:
            self.status_label.setText(f"Status: Capture failed ({str(e)})")
            self.plugin.browser.statusBar.showMessage(f"Screenshot failed: {str(e)}", 5000)
        finally:
            self.capture_btn.setEnabled(True)

    def save_screenshot(self):
        """Save the captured screenshot."""
        if not self.screenshot:
            self.status_label.setText("Status: No screenshot to save")
            self.plugin.browser.statusBar.showMessage("No screenshot to save", 5000)
            return

        output_dir = Path("downloads")
        output_dir.mkdir(exist_ok=True)
        timestamp = QDateTime.currentDateTime().toString("yyyy-MM-dd_HHmm")
        default_path = output_dir / f"screenshot_{timestamp}.png"

        save_path, _ = QFileDialog.getSaveFileName(
            self, "Save Screenshot", str(default_path), "PNG Files (*.png);;All Files (*)"
        )
        if save_path:
            try:
                self.screenshot.save(save_path, "PNG")
                self.status_label.setText(f"Status: Screenshot saved to {save_path}")
                self.plugin.browser.statusBar.showMessage(f"Screenshot saved to {save_path}", 5000)
            except Exception as e:
                self.status_label.setText(f"Status: Save failed ({str(e)})")
                self.plugin.browser.statusBar.showMessage(f"Save failed: {str(e)}", 5000)

class Plugin(Plugin):
    def __init__(self, browser, name="Screenshot Plugin", version="1.0"):
        super().__init__(browser, name, version)

    def add_to_menu(self, menu):
        try:
            action = QAction("Screenshot Webpage", self.browser)
            action.triggered.connect(self.open_dialog)
            menu.addAction(action)
        except NameError as e:
            self.browser.statusBar.showMessage(f"Screenshot Plugin: QAction not available: {str(e)}", 5000)

    def open_dialog(self):
        if not self.browser.tabs.currentWidget():
            self.browser.statusBar.showMessage("No active tab for screenshot", 5000)
            return
        dialog = ScreenshotDialog(plugin=self, parent=self.browser)
        dialog.exec()