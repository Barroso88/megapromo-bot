import io
import urllib.error

import pytest
from PIL import Image

from dealbot.amazon_image import fetch_amazon_image


def jpeg(w, h, color=(200, 30, 30)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), color).save(buf, "JPEG")
    return buf.getvalue()


def gif_1x1() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (1, 1), (255, 255, 255)).save(buf, "GIF")
    return buf.getvalue()


class Resp:
    def __init__(self, body, ctype="image/jpeg", status=200):
        self.body, self.status, self.headers = body, status, {"Content-Type": ctype}

    def __enter__(self): return self
    def __exit__(self, *a): return False
    def read(self, n=-1): return self.body


def opener_returning(resp, seen=None):
    def op(req, timeout=0):
        if seen is not None:
            seen.append(req)
        return resp
    return op


def test_returns_a_real_product_image():
    data = jpeg(500, 500)
    assert fetch_amazon_image("B0GXWFNVSH", opener=opener_returning(Resp(data))) == data


def test_accepts_tall_images_like_a_mouse_262x500():
    data = jpeg(262, 500)
    assert fetch_amazon_image("B0FPDBK2M6", opener=opener_returning(Resp(data))) == data


def test_blank_1x1_gif_is_rejected():
    assert fetch_amazon_image("B0FBWWW131", opener=opener_returning(Resp(gif_1x1(), "image/gif"))) is None


def test_too_small_image_is_rejected():
    assert fetch_amazon_image("B0FBWWW131", opener=opener_returning(Resp(jpeg(120, 120)))) is None


def test_non_image_or_error_responses_are_rejected():
    assert fetch_amazon_image("B0FBWWW131", opener=opener_returning(Resp(b"<html>", "text/html"))) is None
    assert fetch_amazon_image("B0FBWWW131", opener=opener_returning(Resp(b"", status=404))) is None
    assert fetch_amazon_image("B0FBWWW131", opener=opener_returning(Resp(b"not an image"))) is None


def test_network_errors_return_none():
    def boom(req, timeout=0):
        raise urllib.error.URLError("sem rede")
    assert fetch_amazon_image("B0FBWWW131", opener=boom) is None


@pytest.mark.parametrize("asin", ["", "x", "B0FBWWW13", "B0FBWWW1311", "../etc/passwd", "B0FBWWW13/", "b0fbwww131 "])
def test_invalid_asin_never_builds_a_url(asin):
    def boom(req, timeout=0):
        raise AssertionError("não devia pedir nada")
    assert fetch_amazon_image(asin, opener=boom) is None


def test_request_identifies_itself_as_a_bot_and_uses_the_asin_only():
    seen = []
    fetch_amazon_image("B0GXWFNVSH", opener=opener_returning(Resp(jpeg(500, 500)), seen))
    req = seen[0]
    assert "/images/P/B0GXWFNVSH.01.LZZZZZZZ.jpg" in req.full_url
    ua = req.get_header("User-agent")
    assert "bot" in ua.lower() and "Mozilla" not in ua


def test_oversized_download_is_rejected():
    class Big(Resp):
        def read(self, n=-1):
            return b"\xff" * (6 * 1024 * 1024)
    assert fetch_amazon_image("B0GXWFNVSH", opener=opener_returning(Big(b""))) is None
