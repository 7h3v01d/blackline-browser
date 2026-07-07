try:
    from PyQt6.QtWidgets import QMessageBox
    from PyQt6.QtGui import QAction
except ImportError as e:
    print(f"Failed to import PyQt6.QtWidgets: {str(e)}")
    raise
from PyQt6.QtWebEngineCore import QWebEngineUrlRequestInterceptor
from interceptors import Plugin

class WhitelistInterceptor(QWebEngineUrlRequestInterceptor):
    def __init__(self):
        super().__init__()
        self.whitelist = ["duckduckgo.com", "www.example.com"]
    
    def interceptRequest(self, info):
        url = info.requestUrl().host().lower()
        if any(domain in url for domain in self.whitelist):
            return  # Allow whitelisted domains
        print(f"Whitelist check: {url}")

class Plugin(Plugin):
    def __init__(self, browser, name="Whitelist Plugin", version="1.0"):
        super().__init__(browser, name, version)
        self.interceptor = WhitelistInterceptor()
    
    def add_to_menu(self, menu):
        try:
            action = QAction("Whitelist Info", self.browser)
            action.triggered.connect(self.show_whitelist_info)
            menu.addAction(action)
        except NameError as e:
            self.browser.statusBar.showMessage(f"Whitelist Plugin: QAction not available: {str(e)}", 5000)
    
    def get_interceptor(self):
        return self.interceptor
    
    def show_whitelist_info(self):
        try:
            QMessageBox.information(self.browser, "Whitelist Info", f"Whitelisted domains: {', '.join(self.interceptor.whitelist)}")
        except NameError as e:
            self.browser.statusBar.showMessage(f"Whitelist Plugin: QMessageBox not available: {str(e)}", 5000)