"""Limpeza e reformatação de mensagens copiadas de outros canais."""
import re
from html import escape
from urllib.parse import urlparse
from .compose import DISCLOSURE, short_title
from .links import find_url, extract_asin, build_affiliate_link

# Regex para limpar arrobas de canais concorrentes e links t.me
USERNAME_RE = re.compile(r"@([a-zA-Z0-9_]{4,32})")
TELEGRAM_LINK_RE = re.compile(r"https?://(?:t|telegram)\.me/[a-zA-Z0-9_+/]+")
HTTP_LINK_RE = re.compile(r"https?://[^\s<>\[\]()]+")      # pára em ] e ) do markdown [texto](url)
URL_TRAILING = ".,;:!?'\"*_~»"
MARKDOWN_RE = re.compile(r"\*\*|__|``?|~~")

CLICKBAIT_RE = re.compile(
    r"^(?:🔥|⚡|💥|✨|🎯|👉|🏷️|📢|\s)*(?:\d{1,2}\s*%|excelente|bom\s+pre[cç]o|pre[cç]o\s+m[íi]nimo|m[íi]nimo\s+hist[óo]rico|super\s+desconto|grande\s+baixa|oportunidade|imperd[íi]vel|aproveita|chollazo|chollo|oferta|promo[cç][ãa]o)",
    re.IGNORECASE,
)


GENERIC_TITLE = "Oferta Especial"      # devolvido quando o texto não tem o nome do produto
HEADLINE_WORDS = {
    "mega", "super", "preço", "preco", "preços", "precos", "mínimo", "minimo", "histórico", "historico",
    "excelente", "oferta", "ofertas", "desconto", "descontos", "imperdível", "imperdivel", "aproveita",
    "bom", "bons", "grande", "grandes", "queda", "incrível", "incrivel", "black", "friday", "deal",
    "promo", "promoção", "promocao", "agora", "só", "apenas", "urgente", "corre", "flash", "relâmpago",
    "relampago", "erro", "últimas", "ultimas", "chollo", "chollazo", "oportunidade", "baixa",
    "praticamente", "quase", "poupa", "poupe", "cada", "levar", "leva", "leve", "voltou", "baixou",
}
STOPWORDS = {"de", "do", "da", "dos", "das", "a", "o", "as", "os", "e", "em", "na", "no", "com", "por", "para", "um", "uma",
             "ao", "aos", "à", "às", "mais", "pelo", "pela"}
INSTRUCTION_RE = re.compile(
    r"subscreva|poupe|cancel[aá]vel|\bseleciona|cup[aã]o|c[oó]digo|\baplica\b|\bclica|\bativa\b|resgata|vendido por|enviado por",
    re.IGNORECASE,
)


LABEL_LINE_RE = re.compile(
    r"^(antes|agora|pvp|pre[cç]o|link|url|cup[aã]o|c[oó]digo|tamanhos?|tallas?|sizes?|cores?|cor|colou?rs?|colores|"
    r"dispon[ií]ve(l|is)|envio|entrega|v[aá]lid[oa]|stock|medidas?)\b",
    re.IGNORECASE,
)
PRICE_RE_TITLE = re.compile(r"[\d.,]+\s*€|€\s*[\d.,]+")


def mostly_numbers(text: str) -> bool:
    """'38.5, 39.5, 40, 41, 42': lista de números (tamanhos, quantidades), não o nome de um produto."""
    tokens = text.split()
    numeric = [t for t in tokens if re.fullmatch(r"[\d.,/:;()x-]+", t)]
    return bool(tokens) and len(numeric) / len(tokens) > 0.5


def is_headline(text: str) -> bool:
    """'🤯 -48%! MEGA preço! Mínimo histórico!': frase de chamariz, não o nome de um produto."""
    tokens = re.findall(r"\d+\s*%|[^\W\d_]+", text.lower())
    words = [t for t in tokens if t not in STOPWORDS]
    if not words:
        return True
    hits = sum(1 for t in words if t in HEADLINE_WORDS or t.endswith("%"))
    return hits / len(words) >= 0.6


MARKER_RE = re.compile(r"▫️|▫|▪️|◾|🔹|🔸")          # "Marca ▫️ Produto" (@cupoes) e "🔹 Produto" (@bilbiamtengarsada)
BRAND_SEPARATOR_RE = re.compile(r"\s*(?:▫️|▫|▪️|◾)\s*")


def _title_candidate(line: str) -> str | None:
    """A linha limpa, se puder ser o nome de um produto; None se for chamariz, preço, instrução, etiqueta..."""
    line = MARKDOWN_RE.sub("", line)                          # **negrito**, __itálico__, `código`, ~~riscado~~
    clean = re.sub(r"^[^\w€]+", "", line).strip(" -—•*~#")       # tira emojis e símbolos do início
    if not clean or clean.lower().startswith("http") or LABEL_LINE_RE.search(clean):
        return None
    if "€" in clean:                                          # "Gafas Hawkers 25,40€" -> "Gafas Hawkers"
        clean = PRICE_RE_TITLE.sub("", clean).strip(" -—•*~#[]()")
        if len(re.findall(r"[^\W\d_]+", clean)) < 2:
            return None
    if mostly_numbers(clean) or is_headline(clean) or INSTRUCTION_RE.search(clean):
        return None
    # Frases de chamariz ("32%! Excelente preço! Mínimo histórico!") não são o nome do produto
    if CLICKBAIT_RE.search(clean) and len(clean.split()) <= 8:
        return None
    return clean


def _finish_title(clean: str) -> str:
    clean = BRAND_SEPARATOR_RE.sub(" – ", clean)               # "Rexona ▫️ Desodorizante" -> "Rexona – Desodorizante"
    head, sep, rest = clean.partition(" | ")
    if sep and len(head.strip()) < 15:                         # "Ubisoft | Prince of Persia": a marca é curta, mantém tudo
        clean = f"{head.strip()} – {rest}"
    if len(clean) > 80:                                        # descrições compridas: fica o nome, antes da 1.ª vírgula/frase
        m = re.search(r"[,.](?:\s|$)", clean[25:])
        if m:
            clean = clean[: 25 + m.start()].rstrip(" ,.;:")
    return short_title(clean, 140)


def extract_product_title(raw_text: str, resolved_url: str | None = None) -> str:
    """Extrai o nome real do produto ignorando chamadas genéricas como 'Preço mínimo histórico'.

    Uma linha marcada como produto ("Marca ▫️ Nome", "🔹 Nome") tem prioridade sobre as outras candidatas.
    """
    lines = [l.strip() for l in (raw_text or "").splitlines() if l.strip()]
    candidates = [(line, _title_candidate(line)) for line in lines]
    marked = [c for line, c in candidates if c and MARKER_RE.search(line)]
    chosen = marked[0] if marked else next((c for _, c in candidates if c), None)
    if chosen:
        return _finish_title(chosen)

    # Fallback: extrai do slug do URL da Amazon (ex: amazon.es/Nome-Do-Produto/dp/ASIN)
    if resolved_url:
        parsed = urlparse(resolved_url)
        if "/dp/" in parsed.path:
            slug = parsed.path.split("/dp/")[0].strip("/")
            if slug and not slug.startswith("gp"):
                clean_slug = slug.replace("-", " ").strip()
                if len(clean_slug) >= 5:
                    return short_title(clean_slug, 140)

    return GENERIC_TITLE



def extract_links_from_telethon_message(message) -> list[str]:
    """URLs do texto (incl. markdown [texto](url)), das entidades de hiperligação e dos botões, sem repetidos."""
    urls: list[str] = []

    def add(url):
        if isinstance(url, str):
            url = url.strip().rstrip(URL_TRAILING)
            if url.startswith(("http://", "https://")) and url not in urls:
                urls.append(url)

    text = (message.text or "") + "\n" + (getattr(message, "message", "") or "")
    for match in HTTP_LINK_RE.finditer(text):
        add(match.group(0))

    for entity in getattr(message, "entities", None) or []:     # hiperligações escondidas atrás de texto
        add(getattr(entity, "url", None))

    reply_markup = getattr(message, "reply_markup", None)
    if reply_markup and hasattr(reply_markup, "rows"):
        for row in reply_markup.rows:
            for btn in getattr(row, "buttons", []):
                add(getattr(btn, "url", None))
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


def compose_repost_caption(title: str, clean_body: str, affiliate_link: str, target_handle: str,
                           disclosure: str = DISCLOSURE) -> str:
    """
    Formata o post com a descrição limpa definida pelo utilizador:
    - 🔥 Nome do produto
    - 💥 Link: (o meu link)
    - Aviso de afiliado: o completo, só a etiqueta curta (#pub) ou nenhum, conforme `disclosure`
    """
    parts = []
    header_title = short_title(title, 160) if title else "Oferta Amazon"
    parts.append(f"🔥 <b>{escape(header_title)}</b>")

    parts.append(f"💥 Link: {escape(affiliate_link, quote=True)}")

    if disclosure:
        parts.append(f"<i>{escape(disclosure)}</i>")
    return "\n\n".join(parts)
