from tracker.data import rss_monitor

_SAMPLE_RSS = b"""<?xml version="1.0"?>
<rss version="2.0"><channel>
  <item>
    <title>Iran strikes Israel with ballistic missiles</title>
    <link>https://example.com/a1</link>
    <description>Overnight attack raises fears of wider war</description>
    <pubDate>Fri, 28 Aug 2026 22:05:41 GMT</pubDate>
  </item>
  <item>
    <title>Local council approves new bike lane</title>
    <link>https://example.com/a2</link>
    <description>Residents split on the plan</description>
    <pubDate>Fri, 28 Aug 2026 20:00:00 GMT</pubDate>
  </item>
</channel></rss>
"""


def test_parse_rss_extracts_expected_fields():
    articles = rss_monitor._parse_rss(_SAMPLE_RSS, source="test_feed")
    assert len(articles) == 2
    assert articles[0].title == "Iran strikes Israel with ballistic missiles"
    assert articles[0].link == "https://example.com/a1"
    assert articles[0].source == "test_feed"
    assert articles[0].published is not None
    assert articles[0].published.year == 2026


def test_parse_rss_handles_malformed_xml_without_raising():
    articles = rss_monitor._parse_rss(b"<not><valid", source="broken")
    assert articles == []


def test_parse_rss_skips_items_missing_title_or_link():
    xml = b"""<rss><channel><item><description>no title or link</description></item></channel></rss>"""
    assert rss_monitor._parse_rss(xml, source="x") == []


def test_filter_new_articles_dedupes_by_link():
    articles = rss_monitor._parse_rss(_SAMPLE_RSS, source="test_feed")
    state = {"seen_links": [], "open_signals": []}

    first_pass = rss_monitor.filter_new_articles(articles, state)
    assert len(first_pass) == 2

    second_pass = rss_monitor.filter_new_articles(articles, state)
    assert second_pass == []  # already recorded as seen


def test_filter_new_articles_caps_seen_list_size():
    state = {"seen_links": [f"https://example.com/{i}" for i in range(4990)], "open_signals": []}
    new_articles = [
        rss_monitor.Article(source="x", title=f"t{i}", link=f"https://example.com/new{i}", description="", published=None)
        for i in range(20)
    ]
    rss_monitor.filter_new_articles(new_articles, state, max_seen=5000)
    assert len(state["seen_links"]) == 5000
