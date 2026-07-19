"""
new_tab.html integrity and startup flag assembly.

The page is static, so it is tested as an artefact: does the branding exist,
is the favicon fallback chain wired, is the embedded logo a real PNG, and
does the JavaScript parse (when node is available).
"""

import base64
import re
import shutil
import subprocess

import pytest


# ── branding ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("marker", [
    'id="brand-bar"',
    'id="brand"',
    'class="wordmark"',
    "BLACK",
    "BROWSER",
    'class="vcorner tl"',
    'class="vcorner br"',
    'id="net-chip"',
])
def test_branding_present(new_tab_html, marker):
    assert marker in new_tab_html


def test_palette_matches_house_style(new_tab_html):
    for token, value in [
        ("--obsidian", "#0b0f14"),
        ("--teal", "#2fd6c3"),
        ("--amber", "#ffb454"),
        ("--phosphor", "#4be08a"),
    ]:
        assert re.search(rf"{token}:\s*{value}", new_tab_html), f"{token} drifted"


def test_zero_border_radius_house_rule(new_tab_html):
    """House style is flat. Any non-zero radius is a regression."""
    radii = re.findall(r"border-radius:\s*([^;]+);", new_tab_html)
    for r in radii:
        assert r.strip() in ("0", "0px"), f"unexpected border-radius: {r}"


def test_embedded_logo_is_a_valid_png(new_tab_html):
    m = re.search(r'src="data:image/png;base64,([A-Za-z0-9+/=]+)"', new_tab_html)
    assert m, "brand mark is not embedded"
    raw = base64.b64decode(m.group(1))
    assert raw.startswith(b"\x89PNG\r\n\x1a\n")
    assert len(raw) > 1000


def test_logo_is_embedded_not_file_referenced(new_tab_html):
    """A file:// path would break if the page is ever served elsewhere."""
    assert "../assets/" not in new_tab_html


# ── favicons ─────────────────────────────────────────────────────────────

class TestFaviconFallback:
    """Tiles must never render empty, even with no network."""

    def test_old_single_source_helper_is_gone(self, new_tab_html):
        assert "function faviconUrl(" not in new_tab_html

    def test_chain_has_multiple_providers(self, new_tab_html):
        assert "icons.duckduckgo.com" in new_tab_html
        assert "google.com/s2/favicons" in new_tab_html
        assert "/favicon.ico" in new_tab_html

    def test_monogram_fallback_exists(self, new_tab_html):
        assert "function monogramIcon(" in new_tab_html
        assert "data:image/svg+xml" in new_tab_html

    def test_monogram_uses_teal(self, new_tab_html):
        block = new_tab_html[new_tab_html.index("function monogramIcon("):]
        assert "#2fd6c3" in block[:900]

    def test_error_handler_advances_the_chain(self, new_tab_html):
        assert "function attachFavicon(" in new_tab_html
        block = new_tab_html[new_tab_html.index("function attachFavicon("):]
        assert "addEventListener('error'" in block[:500]

    def test_hiding_the_image_is_no_longer_the_fallback(self, new_tab_html):
        assert "img.style.display = 'none'" not in new_tab_html


# ── structure ────────────────────────────────────────────────────────────

def test_speed_dial_defaults_are_well_formed(new_tab_html):
    """JS object literals, so parsed by shape rather than as JSON."""
    m = re.search(r"DEFAULT_SITES\s*=\s*\[(.*?)\];", new_tab_html, re.S)
    assert m, "DEFAULT_SITES not found"
    entries = re.findall(
        r"\{\s*name:\s*'([^']+)'\s*,\s*url:\s*'([^']+)'\s*\}", m.group(1))
    assert len(entries) >= 5, f"only parsed {len(entries)} default tiles"
    for name, url in entries:
        assert name.strip()
        assert url.startswith("https://")


def test_no_unclosed_style_or_script(new_tab_html):
    assert new_tab_html.count("<style>") == new_tab_html.count("</style>")
    assert new_tab_html.count("<script>") == new_tab_html.count("</script>")


def test_javascript_parses(new_tab_html, tmp_path):
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available")
    js = new_tab_html.split("<script>")[1].split("</script>")[0]
    path = tmp_path / "new_tab.js"
    path.write_text(js, encoding="utf-8")
    result = subprocess.run([node, "--check", str(path)],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


# ── startup flags ────────────────────────────────────────────────────────

class TestChromiumFlags:
    """
    Shipped bug: the logging flags were appended with
    os.environ.setdefault() on a key assigned the line before, which is a
    no-op, so --disable-logging never reached Chromium.
    """

    @pytest.fixture
    def build(self):
        from main import build_chromium_flags
        return build_chromium_flags

    def test_logging_is_disabled(self, build):
        assert "--disable-logging" in build(None)
        assert "--log-level=3" in build(None)

    def test_codecs_always_enabled(self, build):
        assert "--enable-proprietary-codecs" in build(None)

    def test_widevine_included_when_found(self, build):
        flags = build(r"C:\Program Files\Google\Chrome\widevinecdm.dll")
        assert "--enable-widevine" in flags
        assert "widevinecdm.dll" in flags

    def test_widevine_path_is_quoted(self, build):
        """The real path contains spaces — unquoted it truncates the flag."""
        flags = build(r"C:\Program Files\Google\Chrome\widevinecdm.dll")
        assert '--widevine-path="' in flags
        assert flags.count('"') == 2

    def test_widevine_omitted_when_absent(self, build):
        flags = build(None)
        assert "widevine" not in flags.lower()

    def test_logging_flags_survive_widevine_branch(self, build):
        """Both branches must end up with logging disabled."""
        for path in (None, r"C:\Chrome\widevinecdm.dll"):
            assert "--disable-logging" in build(path)


class TestWidevineDiscovery:

    def test_returns_none_when_nothing_installed(self, monkeypatch):
        import main
        monkeypatch.setattr(main.glob, "glob", lambda pattern: [])
        assert main.find_widevine_path() is None

    def test_picks_the_highest_version(self, monkeypatch):
        import main
        found = [
            r"C:\Program Files\Google\Chrome\Application\98.0.1\WidevineCdm\x\widevinecdm.dll",
            r"C:\Program Files\Google\Chrome\Application\150.0.7871.125\WidevineCdm\x\widevinecdm.dll",
            r"C:\Program Files\Google\Chrome\Application\120.0.2\WidevineCdm\x\widevinecdm.dll",
        ]
        monkeypatch.setattr(main.glob, "glob",
                            lambda pattern: found if "Chrome\\Application" in pattern else [])
        assert "150.0.7871.125" in main.find_widevine_path()
