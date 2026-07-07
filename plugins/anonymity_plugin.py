try:
    from PyQt6.QtWidgets import QDialog, QVBoxLayout, QPushButton, QLabel
    from PyQt6.QtGui import QAction
except ImportError as e:
    print(f"Failed to import PyQt6.QtWidgets: {str(e)}")
    raise
from interceptors import Plugin
import requests
from stem.control import Controller
from stem import Signal

class AnonymityDialog(QDialog):
    def __init__(self, plugin, parent=None):
        super().__init__(parent)
        self.plugin = plugin
        self.setWindowTitle("Anonymity Controls")
        self.setGeometry(200, 200, 400, 200)
        self.layout = QVBoxLayout()
        
        self.status_label = QLabel("Tor Status: Checking...")
        self.layout.addWidget(self.status_label)
        
        self.rotate_ip_btn = QPushButton("Rotate Tor IP")
        self.rotate_ip_btn.clicked.connect(self.rotate_tor_ip)
        self.layout.addWidget(self.rotate_ip_btn)
        
        self.verify_btn = QPushButton("Verify Tor Connection")
        self.verify_btn.clicked.connect(self.verify_tor)
        self.layout.addWidget(self.verify_btn)
        
        self.setLayout(self.layout)
        self.verify_tor()
    
    def rotate_tor_ip(self):
        try:
            with Controller.from_port(port=9051) as controller:
                controller.authenticate()
                controller.signal(Signal.NEWNYM)
                self.plugin.browser.statusBar.showMessage("Tor IP rotated successfully", 5000)
                self.verify_tor()
        except Exception as e:
            self.plugin.browser.statusBar.showMessage(f"Failed to rotate Tor IP: {str(e)}", 5000)
    
    def verify_tor(self):
        try:
            response = requests.get("https://check.torproject.org/api/ip", proxies={
                "http": "socks5h://127.0.0.1:9050",
                "https": "socks5h://127.0.0.1:9050"
            })
            if response.json().get("IsTor", False):
                self.status_label.setText("Tor Status: Connected (Exit IP: {})".format(response.json().get("IP")))
            else:
                self.status_label.setText("Tor Status: Not connected")
        except Exception as e:
            self.status_label.setText(f"Tor Status: Error ({str(e)})")
            self.plugin.browser.statusBar.showMessage(f"Tor verification failed: {str(e)}", 5000)

class Plugin(Plugin):
    def __init__(self, browser, name="Anonymity Plugin", version="1.0"):
        super().__init__(browser, name, version)
    
    def add_to_menu(self, menu):
        try:
            action = QAction("Anonymity Controls", self.browser)
            action.triggered.connect(self.open_dialog)
            menu.addAction(action)
        except NameError as e:
            self.browser.statusBar.showMessage(f"Anonymity Plugin: QAction not available: {str(e)}", 5000)
    
    def open_dialog(self):
        dialog = AnonymityDialog(plugin=self, parent=self.browser)
        dialog.exec()