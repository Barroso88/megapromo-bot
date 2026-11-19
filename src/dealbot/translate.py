"""Tradução ES→PT-PT pelo endpoint público do Google Translate; em caso de falha devolve o original."""
import json
import urllib.parse
import urllib.request

URL = "https://translate.googleapis.com/translate_a/single?client=gtx&sl=es&tl=pt-PT&dt=t&q="


def to_pt(text: str, opener=urllib.request.urlopen) -> str:
    if not text.strip():
        return text
    req = urllib.request.Request(URL + urllib.parse.quote(text[:500]), headers={"User-Agent": "Mozilla/5.0"})
    try:
        with opener(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        out = "".join(seg[0] for seg in data[0] if seg and seg[0]).strip()
    except Exception:
        return text
    return out or text
