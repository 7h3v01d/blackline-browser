try:
    from PyQt6.QtGui import QAction
except ImportError as e:
    print(f"Failed to import PyQt6.QtWidgets: {str(e)}")
    raise
from PyQt6.QtCore import QUrl
from interceptors import Plugin

class Plugin(Plugin):
    def __init__(self, browser, name="Sample Plugin", version="1.0"):
        super().__init__(browser, name, version)
    
    def add_to_menu(self, menu):
        try:
            action = QAction("Open Example.com", self.browser)
            action.triggered.connect(lambda: self.browser.tabs.currentWidget().setUrl(QUrl("https://www.example.com")))
            menu.addAction(action)
        except NameError as e:
            self.browser.statusBar.showMessage(f"Sample Plugin: QAction not available: {str(e)}", 5000)