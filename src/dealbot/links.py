"""Extração de ASIN e construção do link de afiliado (só amazon.es)."""
import re
import urllib.error
import urllib.request
from typing import Callable
from urllib.parse import urljoin, urlparse

ASIN_RE = re.compile(r"^[A-Z0-9]{10}$")
PATH_ASIN_RE = re.compile(r"/(?:dp|gp/product)/([A-Z0-9]{10})(?:[/?]|$)")
URL_RE = re.compile(r"https?://[^\s<>]+")
PUNCT = ".,;:!?)]}'\"»"
AMAZON_HOSTS = {"amazon.es", "www.amazon.es"}
SHORT_HOSTS = {"amzn.to", "www.amzn.to", "a.co", "amzn.eu", "bit.ly", "tinyurl.com", "cutt.ly", "t.co"}


class LinkError(Exception):
    pass


def find_url(text: str) -> str | None:
    m = URL_RE.search(text or "")
    return m.group(0).rstrip(PUNCT) if m else None


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def _follow(url: str, max_hops: int = 5) -> str:
    """Resolve links curtos lendo o cabeçalho Location, sem abrir a página final."""
    opener = urllib.request.build_opener(_NoRedirect)
    for _ in range(max_hops):
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}, method="HEAD")
        try:
            with opener.open(req, timeout=10) as resp:
                return resp.geturl()
        except urllib.error.HTTPError as e:
            location = e.headers.get("Location")
            if e.code not in (301, 302, 303, 307, 308) or not location:
                raise
            url = urljoin(url, location)
            if (urlparse(url).hostname or "").lower() not in SHORT_HOSTS:
                return url
    raise OSError("demasiados redirecionamentos")


def _asin_from_amazon_es(url: str) -> str | None:
    parsed = urlparse(url)
    if (parsed.hostname or "").lower() not in AMAZON_HOSTS:
        return None
    m = PATH_ASIN_RE.search(parsed.path)
    return m.group(1) if m else None


def extract_asin(url: str, resolve: Callable[[str], str] | None = None) -> str | None:
    host = (urlparse(url).hostname or "").lower()
    if host in SHORT_HOSTS:
        try:
            final = (resolve or _follow)(url)
        except Exception as e:  # rede, timeout, HTTP
            raise LinkError(f"não consegui abrir o link curto: {e}") from e
        return _asin_from_amazon_es(final)
    return _asin_from_amazon_es(url)


def build_affiliate_link(asin: str, tag: str) -> str:
    if not ASIN_RE.match(asin or ""):
        raise ValueError(f"ASIN inválido: {asin!r}")
    return f"https://www.amazon.es/dp/{asin}?tag={tag}"
