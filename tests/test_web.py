import json
import urllib.request
from dealbot.web import start_web_server, save_deal_to_history

def test_web_server_serves_dashboard_and_api(tmp_path):
    # Guarda uma oferta no histórico
    save_deal_to_history(
        data_dir=tmp_path,
        asin="B0DWDH32M8",
        title="Auriculares Beats",
        source="@canal_teste",
        affiliate_link="https://www.amazon.es/dp/B0DWDH32M8?tag=megapromopt-21",
        card_bytes=b"dummy_image"
    )

    port = 8899
    httpd = start_web_server(data_dir=tmp_path, port=port)
    try:
        # Testa página inicial
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/") as resp:
            assert resp.status == 200
            html = resp.read().decode("utf-8")
            assert "MegaPromo Dashboard" in html

        # Testa API history
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/history") as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert len(data) == 1
            assert data[0]["asin"] == "B0DWDH32M8"
            assert data[0]["source"] == "@canal_teste"
    finally:
        httpd.shutdown()
