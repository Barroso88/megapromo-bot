"""Leitura do feed RSS público do Chollometro (só ofertas da Amazon)."""
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass

FEED_URL = "https://www.chollometro.com/rss"
NS = {"pepper": "http://www.pepper.com/rss", "media": "http://search.yahoo.com/mrss/"}


@dataclass(frozen=True)
class Deal:
    guid: str
    title: str
    category: str
    price: str
    image: str
    thread_url: str


def fetch_feed(url: str = FEED_URL) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read().decode("utf-8")


def parse_feed(xml_text: str) -> list[Deal]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    deals = []
    for item in root.iter("item"):
        merchant = item.find("pepper:merchant", NS)
        if merchant is None or merchant.get("name") != "Amazon":
            continue
        thumb = item.find("media:thumbnail", NS)
        link = (item.findtext("link") or "").strip()
        deals.append(
            Deal(
                guid=(item.findtext("guid") or link).strip(),
                title=(item.findtext("title") or "").strip(),
                category=(item.findtext("category") or "").strip(),
                price=merchant.get("price") or "",
                image=thumb.get("url") if thumb is not None else "",
                thread_url=link,
            )
        )
    return deals
