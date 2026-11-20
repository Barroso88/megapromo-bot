"""Extração de ASIN e construção do link de afiliado (só amazon.es)."""
import re
import urllib.error
import urllib.request
from typing import Callable
from urllib.parse import unquote, urljoin, urlparse

ASIN_RE = re.compile(r"^[A-Z0-9]{10}$")
PATH_ASIN_RE = re.compile(r"/(?:dp|gp/product|gp/aw/d|gp/offer-listing|product)/([A-Z0-9]{10})(?:[/?#]|$)")
# Redirectors de canais de ofertas, ex: descontosainanas.com/amz/B0F4QXRPT1 (o ASIN vem no caminho)
REDIRECTOR_RE = re.compile(r"/(?:amz|amazon)/([A-Z0-9]{10})(?:[/?#]|$)")
URL_RE = re.compile(r"https?://[^\s<>]+")
PUNCT = ".,;:!?)]}'\"»"
AMAZON_HOSTS = {"amazon.es", "www.amazon.es", "m.amazon.es", "smile.amazon.es"}
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
    """Resolve links curtos lendo o cabeçalho Location, sem abrir a página final.

    Usa HEAD; se o encurtador recusar (400/403/405/501), repete com GET sem seguir o redirecionamento.
    """
    opener = urllib.request.build_opener(_NoRedirect)
    method = "HEAD"
    for _ in range(max_hops + 2):
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}, method=method)
        try:
            with opener.open(req, timeout=10) as resp:
                return resp.geturl()
        except urllib.error.HTTPError as e:
            location = e.headers.get("Location")
            if e.code in (301, 302, 303, 307, 308) and location:
                url = urljoin(url, location)
                method = "HEAD"
                if (urlparse(url).hostname or "").lower() not in SHORT_HOSTS:
                    return url
                continue
            if method == "HEAD" and e.code in (400, 403, 405, 501):
                method = "GET"
                continue
            raise
    raise OSError("demasiados redirecionamentos")


def _asin_from_redirector(url: str) -> str | None:
    parsed = urlparse(url)
    if (parsed.hostname or "").lower() in AMAZON_HOSTS:
        return None
    m = REDIRECTOR_RE.search(parsed.path)
    return m.group(1) if m else None


def _asin_from_amazon_es(url: str) -> str | None:
    parsed = urlparse(url)
    if (parsed.hostname or "").lower() not in AMAZON_HOSTS:
        return None
    m = PATH_ASIN_RE.search(parsed.path)
    return m.group(1) if m else None


def analyze_link(url: str, resolve: Callable[[str], str] | None = None) -> tuple[str | None, str | None]:
    """(ASIN, endereço final da amazon.es) de um link direto ou curto; (None, None) se não for amazon.es."""
    host = (urlparse(url).hostname or "").lower()
    final = url
    if host in SHORT_HOSTS:
        try:
            final = (resolve or _follow)(url)
        except Exception as e:  # rede, timeout, HTTP
            raise LinkError(f"não consegui abrir o link curto: {e}") from e
    asin = _asin_from_amazon_es(final) or _asin_from_redirector(final)
    return (asin, final) if asin else (None, None)


def extract_asin(url: str, resolve: Callable[[str], str] | None = None) -> str | None:
    return analyze_link(url, resolve)[0]


def title_from_url(url: str | None) -> str | None:
    """Nome do produto escrito no endereço (amazon.es/<Nome-Do-Produto>/dp/<ASIN>), se existir."""
    if not url:
        return None
    parsed = urlparse(url)
    if (parsed.hostname or "").lower() not in AMAZON_HOSTS:
        return None
    segs = [unquote(p) for p in parsed.path.split("/") if p]
    idx = None
    for i, seg in enumerate(segs):
        if seg == "dp":
            idx = i
            break
        if seg == "product" and i > 0 and segs[i - 1] == "gp":
            idx = i - 1
            break
    if not idx:                        # sem 'dp', ou nada antes dele
        return None
    text = segs[idx - 1].replace("-", " ").strip()
    if len(text) < 4 or not any(c.isalpha() for c in text) or ASIN_RE.match(text.replace(" ", "")):
        return None
    return text


def build_affiliate_link(asin: str, tag: str) -> str:
    if not ASIN_RE.match(asin or ""):
        raise ValueError(f"ASIN inválido: {asin!r}")
    return f"https://www.amazon.es/dp/{asin}?tag={tag}"
