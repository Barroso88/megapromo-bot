import os
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


LISTENER_REQUIRED = ("TELEGRAM_API_ID", "TELEGRAM_API_HASH", "AMAZON_TAG", "SOURCE_CHANNELS", "TARGET_CHANNEL")


@dataclass(frozen=True)
class ListenerConfig:
    api_id: int
    api_hash: str
    amazon_tag: str
    source_channels: list[str]
    target_channel: str
    session_path: str = "data/dealbot.session"
    audit_chat: str = "me"
    show_prices: bool = True        # ler (OCR/texto) e mostrar os preços no cartão, quando legíveis
    require_prices: bool = False    # True: descartar ofertas sem os dois preços (antes: sempre assim)
    amazon_images: bool = True      # imagem oficial por ASIN primeiro; o recorte da foto do canal é o plano B

    @classmethod
    def from_env(cls) -> "ListenerConfig":
        missing = [k for k in LISTENER_REQUIRED if not os.environ.get(k, "").strip()]
        if missing:
            raise SystemExit(f"Variáveis de ambiente em falta para o monitor: {', '.join(missing)}")

        sources = [c.strip() for c in os.environ["SOURCE_CHANNELS"].split(",") if c.strip()]
        session = os.environ.get("TELEGRAM_SESSION_PATH", "data/dealbot.session").strip()
        audit = os.environ.get("AUDIT_CHAT", "me").strip()
        show_prices = os.environ.get("SHOW_PRICES", "1").strip().lower() not in ("0", "false", "no", "off")
        require_prices = os.environ.get("REQUIRE_PRICES", "0").strip().lower() in ("1", "true", "yes", "on")
        amazon_images = os.environ.get("AMAZON_IMAGES", "1").strip().lower() not in ("0", "false", "no", "off")

        return cls(
            api_id=int(os.environ["TELEGRAM_API_ID"].strip()),
            api_hash=os.environ["TELEGRAM_API_HASH"].strip(),
            amazon_tag=os.environ["AMAZON_TAG"].strip(),
            source_channels=sources,
            target_channel=os.environ["TARGET_CHANNEL"].strip(),
            session_path=session,
            audit_chat=audit,
            show_prices=show_prices,
            require_prices=require_prices,
            amazon_images=amazon_images,
        )

