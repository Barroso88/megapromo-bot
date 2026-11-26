import os
import re
from dataclasses import dataclass

REQUIRED = ("TELEGRAM_BOT_TOKEN", "OWNER_CHAT_ID", "CHANNEL_ID", "AMAZON_TAG")


@dataclass(frozen=True)
class Config:
    token: str
    owner_chat_id: str
    channel_id: str
    amazon_tag: str

    @classmethod
    def from_env(cls) -> "Config":
        missing = [k for k in REQUIRED if not os.environ.get(k, "").strip()]
        if missing:
            raise SystemExit(f"Variáveis de ambiente em falta: {', '.join(missing)}")
        e = {k: os.environ[k].strip() for k in REQUIRED}  # segredos colados costumam trazer \n ou espaços
        return cls(e["TELEGRAM_BOT_TOKEN"], e["OWNER_CHAT_ID"], e["CHANNEL_ID"], e["AMAZON_TAG"])


def _peer(value: str) -> str | int:
    """'@canal' fica texto; '-1004462166713' passa a inteiro (o Telethon só o aceita assim)."""
    value = value.strip()
    return int(value) if re.fullmatch(r"-?\d+", value) else value


LISTENER_REQUIRED = ("TELEGRAM_API_ID", "TELEGRAM_API_HASH", "AMAZON_TAG", "SOURCE_CHANNELS", "TARGET_CHANNEL")


@dataclass(frozen=True)
class ListenerConfig:
    api_id: int
    api_hash: str
    amazon_tag: str
    source_channels: list[str]
    target_channel: str | int       # @username ou ID numérico (ex: -1004462166713), que não muda se o nome mudar
    session_path: str = "data/dealbot.session"
    audit_chat: str = "me"
    target_handle: str = ""         # nome a mostrar nos cartões (TARGET_HANDLE); por defeito o @ do canal
    show_prices: bool = True        # ler (OCR/texto) e mostrar os preços no cartão, quando legíveis
    require_prices: bool = True     # só publica com os dois preços lidos; REQUIRE_PRICES=0 publica também sem preços
    disclosure: str = "short"       # POST_DISCLOSURE: "short" (#pub; o aviso completo vai na descrição do canal) ou "full"
    strict: bool = False            # STRICT_MODE (ligado por defeito no ambiente): só publica o que é verificável
    amazon_images: bool = True      # imagem oficial por ASIN primeiro; o recorte da foto do canal é o plano B

    @property
    def disclosure_text(self) -> str:
        """Texto de afiliado no fim de cada publicação."""
        from .compose import DISCLOSURE
        return "#pub" if self.disclosure == "short" else DISCLOSURE

    @property
    def display_handle(self) -> str:
        if self.target_handle:
            return self.target_handle
        if isinstance(self.target_channel, str) and self.target_channel.startswith("@"):
            return self.target_channel
        return "MegaPromo"

    @classmethod
    def from_env(cls) -> "ListenerConfig":
        missing = [k for k in LISTENER_REQUIRED if not os.environ.get(k, "").strip()]
        if missing:
            raise SystemExit(f"Variáveis de ambiente em falta para o monitor: {', '.join(missing)}")

        sources = [c.strip() for c in os.environ["SOURCE_CHANNELS"].split(",") if c.strip()]
        session = os.environ.get("TELEGRAM_SESSION_PATH", "data/dealbot.session").strip()
        audit = os.environ.get("AUDIT_CHAT", "me").strip()
        show_prices = os.environ.get("SHOW_PRICES", "1").strip().lower() not in ("0", "false", "no", "off")
        require_prices = os.environ.get("REQUIRE_PRICES", "1").strip().lower() not in ("0", "false", "no", "off")
        disclosure = "short" if os.environ.get("POST_DISCLOSURE", "short").strip().lower() == "short" else "full"
        strict = os.environ.get("STRICT_MODE", "1").strip().lower() not in ("0", "false", "no", "off")
        amazon_images = os.environ.get("AMAZON_IMAGES", "1").strip().lower() not in ("0", "false", "no", "off")

        return cls(
            api_id=int(os.environ["TELEGRAM_API_ID"].strip()),
            api_hash=os.environ["TELEGRAM_API_HASH"].strip(),
            amazon_tag=os.environ["AMAZON_TAG"].strip(),
            source_channels=sources,
            target_channel=_peer(os.environ["TARGET_CHANNEL"]),
            target_handle=os.environ.get("TARGET_HANDLE", "").strip(),
            session_path=session,
            audit_chat=audit,
            show_prices=show_prices,
            require_prices=require_prices,
            disclosure=disclosure,
            strict=strict,
            amazon_images=amazon_images,
        )

