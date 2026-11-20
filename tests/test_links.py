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


def test_analyze_link_returns_asin_and_final_url_for_direct_and_short_links():
    from dealbot.links import analyze_link
    direct = "https://www.amazon.es/Cecotec-Freidora-Cecofry/dp/B0B5VPLXRB?ref=x"
    assert analyze_link(direct) == ("B0B5VPLXRB", direct)
    final = "https://www.amazon.es/Marvels-Guardians-Galaxy-Nintendo-Switch/dp/B0HJH8BB6Y?th=1"
    assert analyze_link("https://amzn.to/3xyz", resolve=lambda u: final) == ("B0HJH8BB6Y", final)
    assert analyze_link("https://example.com/x") == (None, None)
    assert analyze_link("https://amzn.to/3xyz", resolve=lambda u: "https://example.com/dp/B0B5VPLXRB") == (None, None)


def test_title_from_url_reads_the_product_slug():
    from dealbot.links import title_from_url
    f = title_from_url
    assert f("https://www.amazon.es/Cecotec-Freidora-Cecofry-Experience-Ventana/dp/B0B5VPLXRB") == \
        "Cecotec Freidora Cecofry Experience Ventana"
    assert f("https://www.amazon.es/Caf%C3%A9-Molido-Natural-500g/dp/B0B5VPLXRB?x=1") == "Café Molido Natural 500g"
    assert f("https://www.amazon.es/-/en/Nintendo-Switch-Pro-Controller/dp/B0B5VPLXRB") == "Nintendo Switch Pro Controller"
    assert f("https://www.amazon.es/Nombre-Producto/gp/product/B0B5VPLXRB") == "Nombre Producto"


def test_title_from_url_without_a_slug_is_none():
    from dealbot.links import title_from_url
    for url in ("https://www.amazon.es/dp/B0B5VPLXRB", "https://www.amazon.es/gp/product/B0B5VPLXRB",
                "https://www.amazon.es/dp/B0B5VPLXRB/?tag=x", "https://www.amazon.es/s/dp/B0B5VPLXRB",
                "https://www.amazon.es/ab/dp/B0B5VPLXRB", "", None, "https://example.com/Nome-Produto/dp/B0B5VPLXRB"):
        assert title_from_url(url) is None, url


def test_asin_in_a_redirector_path_is_recognized():
    from dealbot.links import analyze_link
    url = "https://descontosainanas.com/amz/B0F4QXRPT1"
    assert analyze_link(url) == ("B0F4QXRPT1", url)
    assert analyze_link("https://outro.pt/amazon/B0GC565CTD?x=1")[0] == "B0GC565CTD"
    assert analyze_link("https://outro.pt/amz/curto") == (None, None)
    assert analyze_link("https://outro.pt/categoria/B0GC565CTD") == (None, None)      # sem /amz/ ou /amazon/


def test_more_amazon_es_formats_are_recognized():
    from dealbot.links import extract_asin
    for url in ("https://m.amazon.es/dp/B0B5VPLXRB", "https://www.amazon.es/gp/aw/d/B0B5VPLXRB",
                "https://www.amazon.es/gp/offer-listing/B0B5VPLXRB/ref=x", "https://amazon.es/product/B0B5VPLXRB",
                "https://smile.amazon.es/dp/B0B5VPLXRB"):
        assert extract_asin(url) == "B0B5VPLXRB", url


def test_follow_falls_back_to_get_when_head_is_refused(monkeypatch):
    import io
    import urllib.error
    import urllib.request
    from dealbot import links

    calls = []

    class FakeOpener:
        def open(self, req, timeout=0):
            calls.append(req.get_method())
            if req.get_method() == "HEAD":
                raise urllib.error.HTTPError(req.full_url, 405, "no", {}, io.BytesIO(b""))
            raise urllib.error.HTTPError(req.full_url, 302, "found",
                                         {"Location": "https://www.amazon.es/dp/B0B5VPLXRB"}, io.BytesIO(b""))

    monkeypatch.setattr(urllib.request, "build_opener", lambda *a, **k: FakeOpener())
    assert links._follow("https://amzn.to/x") == "https://www.amazon.es/dp/B0B5VPLXRB"
    assert calls == ["HEAD", "GET"]
