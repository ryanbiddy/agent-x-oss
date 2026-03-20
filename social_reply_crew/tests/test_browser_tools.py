from social_reply_crew.browser_tools import XBrowserService


def test_parse_metric_text_handles_plain_and_compact_values():
    assert XBrowserService._parse_metric_text("17") == 17
    assert XBrowserService._parse_metric_text("1.2K Likes") == 1200
    assert XBrowserService._parse_metric_text("3M reposts") == 3_000_000
    assert XBrowserService._parse_metric_text(None) == 0


def test_to_bool_handles_common_browser_return_values():
    assert XBrowserService._to_bool(True) is True
    assert XBrowserService._to_bool("true") is True
    assert XBrowserService._to_bool("false") is False
    assert XBrowserService._to_bool(1) is True
    assert XBrowserService._to_bool(0) is False
