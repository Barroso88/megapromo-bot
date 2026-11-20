"""Limpeza e reformatação de mensagens copiadas de outros canais."""
import re
from html import escape
from urllib.parse import urlparse
from .compose import DISCLOSURE, short_title
from .links import find_url, extract_asin, build_affiliate_link

# Regex para limpar arrobas de canais concorrentes e links t.me
USERNAME_RE = re.compile(r"@([a-zA-Z0-9_]{4,32})")
TELEGRAM_LINK_RE = re.compile(r"https?://(?:t|telegram)\.me/[a-zA-Z0-9_+/]+")
HTTP_LINK_RE = re.compile(r"https?://\S+")
MARKDOWN_RE = re.compile(r"\*\*|__|``?|~~")

CLICKBAIT_RE = re.compile(
    r"^(?:🔥|⚡|💥|✨|🎯|👉|🏷️|📢|\s)*(?:\d{1,2}\s*%|excelente|bom\s+pre[cç]o|pre[cç]o\s+m[íi]nimo|m[íi]nimo\s+hist[óo]rico|super\s+desconto|grande\s+baixa|oportunidade|imperd[íi]vel|aproveita|chollazo|chollo|oferta|promo[cç][ãa]o)",
    re.IGNORECASE,
)


def extract_product_title(raw_text: str, resolved_url: str | None = None) -> str:
    """Extrai o nome real do produto ignorando chamadas genéricas como 'Preço mínimo histórico'."""
    lines = [l.strip() for l in (raw_text or "").splitlines() if l.strip()]
    for line in lines:
        line = MARKDOWN_RE.sub("", line)                      # **negrito**, __itálico__, `código`, ~~riscado~~
        clean = line.strip(" -—•*~#🔥⚡💥🎯👉 ")
        if not clean or clean.lower().startswith("http"):
            continue
        # Frases de chamariz ("32%! Excelente preço! Mínimo histórico!") não são o nome do produto
        if CLICKBAIT_RE.search(clean) and len(clean.split()) <= 8:
            continue
        return short_title(clean, 140)

    # Fallback: extrai do slug do URL da Amazon (ex: amazon.es/Nome-Do-Produto/dp/ASIN)
    if resolved_url:
        parsed = urlparse(resolved_url)
        if "/dp/" in parsed.path:
            slug = parsed.path.split("/dp/")[0].strip("/")
            if slug and not slug.startswith("gp"):
                clean_slug = slug.replace("-", " ").strip()
                if len(clean_slug) >= 5:
                    return short_title(clean_slug, 140)

    return "Oferta Especial"



def extract_links_from_telethon_message(message) -> list[str]:
    """Extrai URLs do texto, caption e botões inline da mensagem do Telethon."""
    urls = []
    text = (message.text or "") + "\n" + (getattr(message, "message", "") or "")
    for match in HTTP_LINK_RE.finditer(text):
        urls.append(match.group(0))

    # Verifica botões inline (reply_markup)
    reply_markup = getattr(message, "reply_markup", None)
    if reply_markup and hasattr(reply_markup, "rows"):
        for row in reply_markup.rows:
            for btn in getattr(row, "buttons", []):
                url = getattr(btn, "url", None)
                if url:
                    urls.append(url)
    return urls


def clean_text_for_repost(raw_text: str, target_handle: str) -> str:
    """
    Remove menções a outros canais (@outro, t.me/outro),
    remove links brutos e prepara o texto limpo mantendo descrição/preço.
    """
    if not raw_text:
        return ""

    lines = []
    for line in raw_text.splitlines():
        line = line.strip()
        if not line:
            continue
        # Remove links do Telegram e arrobas
        line = TELEGRAM_LINK_RE.sub("", line)
        line = USERNAME_RE.sub("", line)
        # Se a linha continha apenas o link ou ficou vazia/irrelevante, ignora
        line = line.strip(" -—•*~")
        if line and not line.lower().startswith("http"):
            lines.append(line)

    cleaned = "\n".join(lines).strip()
    return cleaned


def compose_repost_caption(title: str, clean_body: str, affiliate_link: str, target_handle: str) -> str:
    """
    Formata o post com a descrição limpa definida pelo utilizador:
    - 🔥 Nome do produto
    - 💥 Link: (o meu link)
    - Aviso de afiliado da Amazon
    """
    parts = []
    header_title = short_title(title, 160) if title else "Oferta Amazon"
    parts.append(f"🔥 <b>{escape(header_title)}</b>")

    parts.append(f"💥 Link: {escape(affiliate_link, quote=True)}")

    parts.append(f"<i>{DISCLOSURE}</i>")
    return "\n\n".join(parts)
