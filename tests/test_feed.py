from pathlib import Path

from dealbot.feed import Deal, parse_feed

XML = (Path(__file__).parent / "fixtures" / "feed.xml").read_text(encoding="utf8")


def test_only_amazon_items():
    deals = parse_feed(XML)
    assert len(deals) == 2
    assert all(isinstance(d, Deal) for d in deals)


def test_first_deal_fields():
    d = parse_feed(XML)[0]
    assert d.price.endswith("€") and d.price[0].isdigit()
    assert d.category
    assert d.thread_url.startswith("https://www.chollometro.com/ofertas/")
    assert d.image.startswith("https://")
    assert d.guid and d.title


def test_missing_price_is_empty_string():
    assert parse_feed(XML)[1].price == ""


def test_invalid_xml_returns_empty():
    assert parse_feed("<rss><nope") == []
    assert parse_feed("") == []


def test_large_image_url_and_fetch_failure():
    from dealbot.feed import fetch_image, large_image_url
    assert large_image_url("https://s/x/re/150x150/qt/55/a.jpg") == "https://s/x/re/768x768/qt/55/a.jpg"
    assert large_image_url("") == ""

    def boom(req, timeout=0): raise OSError
    assert fetch_image("https://s/a.jpg", opener=boom) is None
    assert fetch_image("", opener=boom) is None
