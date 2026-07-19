"""Shared fixtures. Puts src/ on sys.path so modules import as they do at runtime."""

import os
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# Qt tests must not try to open a real window on CI or a headless box.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture
def project_root() -> Path:
    return PROJECT_ROOT


@pytest.fixture
def src_dir() -> Path:
    return SRC


@pytest.fixture
def vault_path(tmp_path) -> str:
    """An isolated vault file path. Never touches the real credentials.vault."""
    return str(tmp_path / "credentials.vault")


@pytest.fixture
def sample_rules():
    """
    A miniature filter list covering the shapes that matter, including the
    real EasyList lines that caused the substring-matching outage.
    """
    return [
        "[Adblock Plus 2.0]",
        "! Title: test list",
        "||doubleclick.net^$third-party",
        "||ads.example.com^",
        "||pagead2.googlesyndication.com^",
        "||tracker.co.uk^$script",
        # scoped to one site — must NOT become a global rule
        "||t.co^$subdocument,domain=kshow123.tv",
        "||www.youtube.com/get_midroll_$domain=youtube.com",
        # element hiding / exceptions / regex — not domain rules
        "example.com##.ad-banner",
        "@@||goodsite.com^$document",
        "/banner\\d+\\.gif/",
        "###ad-googleAdSense",
        "||exam*ple.net^",
        "||localhost^",
        "",
        "   ",
    ]


@pytest.fixture
def qapp():
    """A single QApplication for the whole session, offscreen."""
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def new_tab_html(src_dir) -> str:
    return (src_dir / "new_tab.html").read_text(encoding="utf-8")
