"""
Filter-list parsing and host matching.

The regression tests at the bottom of this file cover a bug that shipped:
EasyList rules were reduced to bare domains and matched with a substring
test, so `||t.co^$subdocument,domain=kshow123.tv` blocked reddi(t.co)m,
and github.com and www.youtube.com were unreachable.
"""

import pytest

from adblock import FilterSet, host_matches_any


# ── parse_rule ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("line,expected", [
    ("||doubleclick.net^", "doubleclick.net"),
    ("||doubleclick.net^$third-party", "doubleclick.net"),
    ("||ads.example.com^$script,image", "ads.example.com"),
    ("||tracker.co.uk", "tracker.co.uk"),
    ("||CAPS.EXAMPLE.COM^", "caps.example.com"),
    ("  ||spaced.example.com^  ", "spaced.example.com"),
])
def test_parses_plain_domain_anchors(line, expected):
    assert FilterSet.parse_rule(line) == expected


@pytest.mark.parametrize("line", [
    "",
    "   ",
    "[Adblock Plus 2.0]",
    "! comment",
    "@@||goodsite.com^$document",          # exception rule
    "example.com##.ad-banner",             # cosmetic
    "###ad-googleAdSense",                 # cosmetic, id form
    "/banner\\d+\\.gif/",                  # regex rule
    "-advertisement-",                     # substring rule, no anchor
    "||exam*ple.net^",                     # wildcard
    "||example.com/path/to/ad^",           # carries a path
    "||localhost^",                        # no dot, not a public host
    "||^",                                 # empty domain
    "||.leadingdot.com^",
    "||trailingdot.com.^",
    "||double..dot.com^",
])
def test_rejects_non_domain_rules(line):
    assert FilterSet.parse_rule(line) is None


@pytest.mark.parametrize("line", [
    "||t.co^$subdocument,domain=kshow123.tv",
    "||www.youtube.com/get_midroll_$domain=youtube.com",
    "||example.net^$third-party,domain=~foo.com",
    "||example.net^$DOMAIN=foo.com",        # case-insensitive option
])
def test_rejects_site_scoped_rules(line):
    """$domain= needs page context the interceptor does not have."""
    assert FilterSet.parse_rule(line) is None


# ── from_lines ───────────────────────────────────────────────────────────

def test_from_lines_counts_kept_and_skipped(sample_rules):
    fs = FilterSet.from_lines(sample_rules)
    assert fs.domains == {
        "doubleclick.net",
        "ads.example.com",
        "pagead2.googlesyndication.com",
        "tracker.co.uk",
    }
    assert fs.skipped == len(sample_rules) - 4
    assert len(fs) == 4


def test_from_file_reads_a_list(tmp_path, sample_rules):
    path = tmp_path / "easylist.txt"
    path.write_text("\n".join(sample_rules), encoding="utf-8")
    fs = FilterSet.from_file(str(path))
    assert "doubleclick.net" in fs.domains


def test_from_file_tolerates_bad_encoding(tmp_path):
    path = tmp_path / "easylist.txt"
    path.write_bytes(b"||ads.example.com^\n||caf\xe9.example.com^\n")
    fs = FilterSet.from_file(str(path))
    assert "ads.example.com" in fs.domains


# ── is_blocked ───────────────────────────────────────────────────────────

@pytest.fixture
def blocklist():
    return FilterSet({"doubleclick.net", "ads.example.com", "tracker.co.uk"})


@pytest.mark.parametrize("host", [
    "doubleclick.net",
    "ad.doubleclick.net",
    "deep.nested.doubleclick.net",
    "ads.example.com",
    "cdn.ads.example.com",
    "DOUBLECLICK.NET",
    "doubleclick.net.",                    # trailing root dot
    "  doubleclick.net  ",
])
def test_blocks_exact_and_subdomains(blocklist, host):
    assert blocklist.is_blocked(host)


@pytest.mark.parametrize("host", [
    "example.com",
    "notdoubleclick.net",                  # suffix without a label boundary
    "doubleclick.net.evil.com",            # rule appears as a prefix label
    "mydoubleclick.net",
    "example.ads.example.com.evil.net",
    "",
    "   ",
    None,
])
def test_does_not_block_near_misses(blocklist, host):
    assert not blocklist.is_blocked(host)


def test_contains_operator(blocklist):
    assert "ad.doubleclick.net" in blocklist
    assert "example.com" not in blocklist


# ── whitelist ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("host,expected", [
    ("netflix.com", True),
    ("www.netflix.com", True),
    ("api.nflxvideo.net", True),
    ("notnetflix.com", False),
    ("netflix.com.evil.net", False),
    ("", False),
])
def test_whitelist_matches_on_boundaries(host, expected):
    suffixes = {"netflix.com", "nflxvideo.net"}
    assert host_matches_any(host, suffixes) is expected


# ── regressions ──────────────────────────────────────────────────────────

class TestSubstringMatchingRegression:
    """
    Shipped bug: filters were matched with `if f in host`, so any rule that
    happened to be a substring of a hostname blocked it. Real casualties
    below — these must never block again.
    """

    @pytest.fixture
    def real_world(self, sample_rules):
        return FilterSet.from_lines(sample_rules)

    @pytest.mark.parametrize("host", [
        "www.reddit.com",       # contained "t.co" from a kshow123.tv rule
        "github.com",
        "www.youtube.com",
        "www.google.com",
        "icons.duckduckgo.com",
        "store.steampowered.com",
        "www.netflix.com",
        "client.com",           # contains "t.co"
        "latest.company.net",   # contains "t.co"
    ])
    def test_real_sites_are_not_blocked(self, real_world, host):
        assert not real_world.is_blocked(host)

    @pytest.mark.parametrize("host", [
        "doubleclick.net",
        "ad.doubleclick.net",
        "pagead2.googlesyndication.com",
        "ads.example.com",
    ])
    def test_ad_hosts_still_blocked(self, real_world, host):
        assert real_world.is_blocked(host)

    def test_scoped_rule_never_becomes_global(self, real_world):
        """The rule that caused the outage must not be in the domain set."""
        assert "t.co" not in real_world.domains
        assert not real_world.is_blocked("t.co")
