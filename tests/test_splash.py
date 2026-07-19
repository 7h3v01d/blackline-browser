"""
Splash screen and vault password dialog.

Runs offscreen (QT_QPA_PLATFORM set in conftest), so these are safe on CI.
Covers the layered-window crash that spammed the console at 60fps.
"""

import pytest

pytest.importorskip("PyQt6.QtWidgets")

from PyQt6.QtCore import QRect
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QDialog, QFrame, QGraphicsDropShadowEffect, QLabel, QLineEdit,
)

import splash as splash_mod
from splash import BlacklineSplash, VaultPasswordDialog, asset, load_pixmap


# ── assets ───────────────────────────────────────────────────────────────

def test_splash_art_is_present():
    assert asset("splash.png"), "assets/splash.png is missing"


def test_logo_loads_as_a_pixmap(qapp):
    pix = load_pixmap("splash.png", "blackline_banner_blk.png")
    assert not pix.isNull()
    assert pix.width() > 0


def test_asset_returns_empty_for_unknown_name():
    assert asset("definitely-not-a-real-asset.png") == ""


def test_load_pixmap_of_missing_asset_is_null(qapp):
    assert load_pixmap("definitely-not-a-real-asset.png").isNull()


# ── splash construction ──────────────────────────────────────────────────

def test_splash_constructs_and_sizes(qapp):
    s = BlacklineSplash()
    assert s.width() == s.CARD_W + s.MARGIN * 2
    assert s.height() == s.CARD_H + s.MARGIN * 2


class TestNoGraphicsEffectOnTopLevel:
    """
    Shipped bug: a QGraphicsDropShadowEffect on a translucent frameless
    top-level window inflates the dirty rect past the window bounds, and
    Windows rejects every repaint with
    "UpdateLayeredWindowIndirect failed ... The parameter is incorrect."
    logged once per frame. The shadow must be painted, not an effect.
    """

    def test_splash_has_no_graphics_effect(self, qapp):
        assert BlacklineSplash().graphicsEffect() is None

    def test_splash_paints_its_own_shadow(self, qapp):
        assert hasattr(BlacklineSplash(), "_draw_shadow")

    def test_dialog_shadow_stays_inside_its_gutter(self, qapp):
        """
        The dialog's effect lives on the child card, which is legal — but the
        blur plus offset must fit the 24px margin or it clips.
        """
        dlg = VaultPasswordDialog(vault_exists=True)
        card = dlg.findChild(QFrame, "card")
        assert card is not None
        eff = card.graphicsEffect()
        assert isinstance(eff, QGraphicsDropShadowEffect)
        reach = eff.blurRadius() / 2 + abs(eff.yOffset())
        assert reach <= 24, f"shadow reaches {reach}px into a 24px gutter"


# ── progress and staging ─────────────────────────────────────────────────

def test_progress_starts_at_zero(qapp):
    assert BlacklineSplash()._progress == 0.0


@pytest.mark.parametrize("frames", [1, 10, 60, 400])
def test_progress_stays_in_range(qapp, frames):
    s = BlacklineSplash()
    s._duration = 1000
    for _ in range(frames):
        s._on_frame()
    assert 0.0 <= s._progress <= 1.0


def test_progress_is_monotonic(qapp):
    s = BlacklineSplash()
    s._duration = 1000
    seen = []
    for _ in range(80):
        s._on_frame()
        seen.append(s._progress)
    assert seen == sorted(seen)


def test_progress_reaches_one_by_the_end(qapp):
    s = BlacklineSplash()
    s._duration = 200
    for _ in range(40):        # 40 * 16ms > 200ms
        s._on_frame()
    assert s._progress == pytest.approx(1.0, abs=1e-6)


def test_stages_advance_with_progress(qapp):
    s = BlacklineSplash()
    s._duration = 1000
    first = s._status
    for _ in range(70):
        s._on_frame()
    assert s._status != first
    assert s._status == s.STAGES[-1][1]


def test_stage_thresholds_are_sorted(qapp):
    thresholds = [t for t, _ in BlacklineSplash.STAGES]
    assert thresholds == sorted(thresholds)
    assert thresholds[0] == 0.0
    assert thresholds[-1] == 1.0


# ── set_status ───────────────────────────────────────────────────────────

def test_set_status_uppercases_and_sets_progress(qapp):
    s = BlacklineSplash()
    s.set_status("compiling filter lists", 0.42)
    assert s._status == "COMPILING FILTER LISTS"
    assert s._progress == pytest.approx(0.42)


@pytest.mark.parametrize("given,expected", [(-5.0, 0.0), (0.5, 0.5), (99.0, 1.0)])
def test_set_status_clamps_progress(qapp, given, expected):
    s = BlacklineSplash()
    s.set_status("x", given)
    assert s._progress == pytest.approx(expected)


def test_manual_status_is_not_overwritten_by_frames(qapp):
    s = BlacklineSplash()
    s.set_status("REAL WORK", 0.1)
    s._duration = 1000
    for _ in range(30):
        s._on_frame()
    assert s._status == "REAL WORK"


# ── painting doesn't explode ─────────────────────────────────────────────

def test_paints_without_error_at_every_stage(qapp):
    s = BlacklineSplash()
    for threshold, _ in BlacklineSplash.STAGES:
        s._progress = threshold
        s.grab()               # forces a full paintEvent


def test_paints_with_missing_logo(qapp, monkeypatch):
    """Falls back to a drawn wordmark rather than crashing."""
    monkeypatch.setattr(splash_mod, "load_pixmap", lambda *a: QPixmap())
    s = BlacklineSplash()
    s.grab()


# ── vault dialog ─────────────────────────────────────────────────────────

class TestVaultPasswordDialog:

    def test_password_field_is_masked(self, qapp):
        dlg = VaultPasswordDialog(vault_exists=True)
        assert dlg.edit.echoMode() == QLineEdit.EchoMode.Password

    def test_reveal_toggle_switches_echo_mode(self, qapp):
        dlg = VaultPasswordDialog(vault_exists=True)
        dlg.reveal_btn.setChecked(True)
        assert dlg.edit.echoMode() == QLineEdit.EchoMode.Normal
        assert dlg.reveal_btn.text() == "HIDE"
        dlg.reveal_btn.setChecked(False)
        assert dlg.edit.echoMode() == QLineEdit.EchoMode.Password
        assert dlg.reveal_btn.text() == "SHOW"

    def test_wording_differs_for_new_vs_existing_vault(self, qapp):
        existing = VaultPasswordDialog(vault_exists=True)
        fresh = VaultPasswordDialog(vault_exists=False)
        assert "UNLOCK" in existing.findChild(QLabel, "subtitle").text()
        assert "CREATE" in fresh.findChild(QLabel, "subtitle").text()

    def test_empty_password_does_not_accept(self, qapp):
        dlg = VaultPasswordDialog(vault_exists=True)
        dlg.edit.setText("")
        dlg._on_accept()
        assert dlg.result() != QDialog.DialogCode.Accepted

    def test_non_empty_password_accepts(self, qapp):
        dlg = VaultPasswordDialog(vault_exists=True)
        dlg.edit.setText("hunter2")
        dlg._on_accept()
        assert dlg.result() == QDialog.DialogCode.Accepted
        assert dlg.password() == "hunter2"

    def test_reject_returns_no_password(self, qapp):
        dlg = VaultPasswordDialog(vault_exists=True)
        dlg.edit.setText("hunter2")
        dlg.reject()
        assert dlg.result() == QDialog.DialogCode.Rejected

    def test_caps_row_reserves_height_when_hidden(self, qapp):
        """
        The dialog is fixed-size, so the caps warning must occupy space
        even when inactive or it clips the layout when it appears.
        """
        dlg = VaultPasswordDialog(vault_exists=True)
        idle = dlg.caps.sizeHint().height()
        dlg._set_caps(True)
        assert dlg.caps.sizeHint().height() == idle

    def test_caps_toggles_text(self, qapp):
        dlg = VaultPasswordDialog(vault_exists=True)
        dlg._set_caps(True)
        assert "CAPS LOCK" in dlg.caps.text()
        dlg._set_caps(False)
        assert "CAPS LOCK" not in dlg.caps.text()
