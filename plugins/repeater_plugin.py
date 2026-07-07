try:
    from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLineEdit, QPushButton, QTextEdit, QComboBox
    from PyQt6.QtGui import QAction
except ImportError as e:
    print(f"Failed to import PyQt6.QtWidgets: {str(e)}")
    raise
from PyQt6.QtCore import QUrl
from interceptors import Plugin
import urllib.request
import urllib.parse
import json

class RepeaterDialog(QDialog):
    def __init__(self, plugin, parent=None):
        super().__init__(parent)
        self.plugin = plugin
        self.setWindowTitle("Request Crafter & Repeater")
        self.setGeometry(200, 200, 600, 400)
        self.layout = QVBoxLayout()
        
        self.request_selector = QComboBox()
        self.request_selector.addItems([req["url"] for req in self.plugin.get_shared_requests()])
        self.request_selector.currentIndexChanged.connect(self.load_request)
        self.layout.addWidget(self.request_selector)
        
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("URL")
        self.layout.addWidget(self.url_input)
        
        self.method_input = QLineEdit()
        self.method_input.setPlaceholderText("Method (e.g., GET, POST)")
        self.layout.addWidget(self.method_input)
        
        self.headers_input = QTextEdit()
        self.headers_input.setPlaceholderText("Headers (JSON format)")
        self.layout.addWidget(self.headers_input)
        
        self.body_input = QTextEdit()
        self.body_input.setPlaceholderText("Body (for POST requests)")
        self.layout.addWidget(self.body_input)
        
        self.send_btn = QPushButton("Send Request")
        self.send_btn.clicked.connect(self.send_request)
        self.layout.addWidget(self.send_btn)
        
        self.response_output = QTextEdit()
        self.response_output.setReadOnly(True)
        self.response_output.setPlaceholderText("Response will appear here")
        self.layout.addWidget(self.response_output)
        
        self.setLayout(self.layout)
        if self.plugin.get_shared_requests():
            self.load_request(0)
    
    def load_request(self, index):
        requests = self.plugin.get_shared_requests()
        if index >= 0 and index < len(requests):
            req = requests[index]
            self.url_input.setText(req["url"])
            self.method_input.setText(req["method"])
            self.headers_input.setText(json.dumps(req["headers"], indent=2))
            self.body_input.setText(req.get("body", ""))
    
    def send_request(self):
        url = self.url_input.text()
        method = self.method_input.text().upper()
        headers = json.loads(self.headers_input.toPlainText()) if self.headers_input.toPlainText() else {}
        body = self.body_input.toPlainText().encode() if self.body_input.toPlainText() else None
        
        try:
            req = urllib.request.Request(url, data=body, headers=headers, method=method)
            with urllib.request.urlopen(req) as response:
                response_data = {
                    "url": url,
                    "status": response.getcode(),
                    "headers": dict(response.getheaders()),
                    "body": response.read().decode()
                }
                self.response_output.setText(json.dumps(response_data, indent=2))
                self.plugin.log_response(response_data)
                self.plugin.browser.statusBar.showMessage("Request sent successfully", 5000)
        except Exception as e:
            self.response_output.setText(f"Error: {str(e)}")
            self.plugin.browser.statusBar.showMessage(f"Failed to send request: {str(e)}", 5000)

class Plugin(Plugin):
    def __init__(self, browser, name="Repeater Plugin", version="1.0"):
        super().__init__(browser, name, version)
    
    def add_to_menu(self, menu):
        try:
            action = QAction("Open Repeater", self.browser)
            action.triggered.connect(self.open_repeater)
            menu.addAction(action)
        except NameError as e:
            self.browser.statusBar.showMessage(f"Repeater Plugin: QAction not available: {str(e)}", 5000)
    
    def open_repeater(self):
        dialog = RepeaterDialog(plugin=self, parent=self.browser)
        dialog.exec()