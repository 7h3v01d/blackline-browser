import sys
import os
import glob
import logging
import re
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication
from browser import WebBrowser
from splash import BlacklineSplash, asset

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def find_widevine_path():
    """
    Dynamically find the Widevine CDM regardless of Chrome version.
    Searches all installed Chrome versions and returns the first match.
    """
    base = r"C:\Program Files\Google\Chrome\Application"
    pattern = os.path.join(base, "*", "WidevineCdm", "_platform_specific", "win_x64", "widevinecdm.dll")
    matches = glob.glob(pattern)
    if matches:
        # Pick the highest version number
        def version_key(p):
            # Split on both separators: os.sep alone silently fails to find
            # any version component when the separator does not match the
            # host platform, and every path then sorts equal.
            for part in re.split(r"[\\/]", p):
                segments = part.split('.')
                if len(segments) >= 2 and all(s.isdigit() for s in segments):
                    return [int(s) for s in segments]
            return [0]
        matches.sort(key=version_key, reverse=True)
        return matches[0]

    # Also check Chrome Beta / Dev channels
    for channel in ("Chrome Beta", "Chrome Dev", "Chrome SxS"):
        pattern2 = os.path.join(
            r"C:\Program Files\Google", channel,
            "Application", "*", "WidevineCdm", "_platform_specific", "win_x64", "widevinecdm.dll"
        )
        matches2 = glob.glob(pattern2)
        if matches2:
            return matches2[0]

    return None


def build_chromium_flags(widevine_path=None):
    """
    Assemble QTWEBENGINE_CHROMIUM_FLAGS.

    Kept as a function so it can be tested without launching Qt. The logging
    flags were previously appended with os.environ.setdefault() on a key that
    had already been assigned, which is a no-op — they never reached Chromium.
    """
    flags = ["--enable-proprietary-codecs"]
    if widevine_path:
        flags.append("--enable-widevine")
        flags.append(f'--widevine-path="{widevine_path}"')
    flags.append("--disable-logging")
    flags.append("--log-level=3")
    return " ".join(flags)


def main():
    widevine_path = find_widevine_path()
    if widevine_path:
        logger.info(f"Widevine CDM found: {widevine_path}")
    else:
        logger.warning(
            "Widevine CDM not found. Netflix/DRM video will not work. "
            "Make sure Google Chrome is installed."
        )

    os.environ['QTWEBENGINE_CHROMIUM_FLAGS'] = build_chromium_flags(widevine_path)

    app = QApplication(sys.argv)
    app.setApplicationName("Blackline Browser")
    app.setApplicationDisplayName("Blackline Browser")
    app.setOrganizationName("Blackline")
    app.setOrganizationDomain("blackline.local")

    icon_path = asset("icon.ico")
    if icon_path:
        app.setWindowIcon(QIcon(icon_path))

    # ── Boot experience ────────────────────────────────────────────────────
    splash = BlacklineSplash()
    splash.run(5000)                # animated; click to skip, holds final frame

    window = WebBrowser()           # vault prompt appears over the splash
    window.show()
    splash.finish(window)           # fade out and hand focus to the browser

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
