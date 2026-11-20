import http.client
import json

import pytest

from dealbot.web import HTML_TEMPLATE, save_deal_to_history, save_discard_to_history, start_web_server


@pytest.fixture
def server(tmp_path):
    (tmp_path / "cards").mkdir()
    (tmp_path / "dealbot.session").write_bytes(b"SEGREDO-DA-SESSAO")
    (tmp_path / "state.json").write_text('{"x": 1}')
    httpd = start_web_server(tmp_path, port=0)
    yield tmp_path, httpd.server_address[1]
    httpd.shutdown()


def get(port, path):
    c = http.client.HTTPConnection("127.0.0.1", port)
    c.request("GET", path)            # http.client não normaliza '..' no caminho
    r = c.getresponse()
    return r.status, r.read()


@pytest.mark.parametrize("path", [
    "/images/../dealbot.session",
    "/images/../state.json",
    "/images/..%2Fdealbot.session",
    "/images/%2e%2e/dealbot.session",
    "/images/cards/../../dealbot.session",
    "/images/..\\dealbot.session",
    "/images/a/b.jpg",
])
def test_images_endpoint_never_serves_files_outside_cards(server, path):
    _, port = server
    status, body = get(port, path)
    assert status == 404 and b"SEGREDO" not in body


def test_images_endpoint_serves_a_card(server):
    tmp, port = server
    (tmp / "cards" / "B0TEST12345.jpg").write_bytes(b"\xff\xd8JPEG")
    status, body = get(port, "/images/B0TEST12345.jpg")
    assert status == 200 and body == b"\xff\xd8JPEG"


def test_discards_are_saved_and_listed(server):
    tmp, port = server
    save_discard_to_history(tmp, asin="B09NYDLHYZ", title="Gafas", source="@canal",
                            original_url="https://amzn.to/x", reason="preços antes/depois não detetados",
                            price_before=None, price_after="25,40€")
    status, body = get(port, "/api/discarded")
    items = json.loads(body)
    assert status == 200 and len(items) == 1
    assert items[0]["asin"] == "B09NYDLHYZ" and "preços" in items[0]["reason"]
    assert items[0]["price_after"] == "25,40€" and items[0]["timestamp"]


def test_discards_list_is_empty_by_default_newest_first_and_capped(server):
    tmp, port = server
    assert json.loads(get(port, "/api/discarded")[1]) == []
    for i in range(205):
        save_discard_to_history(tmp, asin=f"A{i:09d}", title="t", source="s", original_url="u", reason="r")
    items = json.loads(get(port, "/api/discarded")[1])
    assert len(items) == 200 and items[0]["asin"] == "A000000204"


def test_published_history_still_works(server):
    tmp, port = server
    save_deal_to_history(tmp, "B0TEST12345", "Gafas", "@c", "https://amazon.es/dp/B0TEST12345?tag=t-21", b"JPG")
    assert json.loads(get(port, "/api/history")[1])[0]["asin"] == "B0TEST12345"


def test_dashboard_escapes_third_party_text_and_lists_discards():
    assert "function esc(" in HTML_TEMPLATE
    assert "${deal.title}" not in HTML_TEMPLATE and "${deal.source" not in HTML_TEMPLATE
    assert "/api/discarded" in HTML_TEMPLATE and "descartad" in HTML_TEMPLATE.lower()
