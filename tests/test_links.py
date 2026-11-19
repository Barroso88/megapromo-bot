import http.server
import threading

import pytest
from dealbot.links import LinkError, _follow, build_affiliate_link, extract_asin, find_url

ASIN = "B0DWDH32M8"


def test_extract_asin_dp():
    assert extract_asin(f"https://www.amazon.es/dp/{ASIN}") == ASIN


def test_extract_asin_gp_product_with_ref():
    assert extract_asin(f"https://www.amazon.es/gp/product/{ASIN}/ref=x") == ASIN


def test_extract_asin_slug_and_query():
    assert extract_asin(f"https://www.amazon.es/Nome-Produto/dp/{ASIN}?th=1") == ASIN


def test_extract_asin_short_link_resolved():
    r = lambda u: "https://www.amazon.es/dp/B0DWF3Y3P3"
    assert extract_asin("https://amzn.to/abc", resolve=r) == "B0DWF3Y3P3"


def test_extract_asin_rejects_other_domains():
    assert extract_asin(f"https://www.amazon.com/dp/{ASIN}") is None
    assert extract_asin(f"https://evil.com/dp/{ASIN}") is None
    assert extract_asin(f"https://amazon.es.evil.com/dp/{ASIN}") is None


def test_short_link_resolving_outside_amazon_es():
    r = lambda u: f"https://www.amazon.com/dp/{ASIN}"
    assert extract_asin("https://amzn.to/abc", resolve=r) is None


def test_resolve_failure_raises_linkerror():
    def r(u):
        raise OSError("boom")

    with pytest.raises(LinkError):
        extract_asin("https://a.co/x", resolve=r)


def test_build_affiliate_link():
    assert build_affiliate_link(ASIN, "meu-21") == f"https://www.amazon.es/dp/{ASIN}?tag=meu-21"


def test_build_affiliate_link_invalid_asin():
    with pytest.raises(ValueError):
        build_affiliate_link("curto", "meu-21")


def test_find_url():
    assert find_url("olá https://amzn.to/x?y=1 obrigado") == "https://amzn.to/x?y=1"
    assert find_url("sem link") is None


def test_foreign_tag_is_dropped():
    asin = extract_asin(f"https://www.amazon.es/dp/{ASIN}?tag=outro-21&ref=x")
    link = build_affiliate_link(asin, "meu-21")
    assert "outro-21" not in link and "ref=x" not in link and link.endswith("tag=meu-21")


def test_find_url_strips_trailing_punctuation():
    assert find_url("ver https://amzn.to/x).") == "https://amzn.to/x"
    assert find_url("(https://www.amazon.es/dp/B0DWDH32M8)") == "https://www.amazon.es/dp/B0DWDH32M8"


def test_amzn_eu_is_a_short_host():
    r = lambda u: "https://www.amazon.es/dp/B0DWF3Y3P3"
    assert extract_asin("https://amzn.eu/d/abc", resolve=r) == "B0DWF3Y3P3"


def test_follow_reads_location_without_fetching_target():
    target = "http://127.0.0.1:1/dp/B0DWDH32M8?x=1"

    class H(http.server.BaseHTTPRequestHandler):
        def do_HEAD(self):
            self.send_response(301)
            self.send_header("Location", target)
            self.end_headers()

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        assert _follow(f"http://127.0.0.1:{srv.server_port}/") == target
    finally:
        srv.shutdown()
