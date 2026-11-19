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
        missing = [k for k in REQUIRED if not os.environ.get(k)]
        if missing:
            raise SystemExit(f"Variáveis de ambiente em falta: {', '.join(missing)}")
        e = os.environ
        return cls(e["TELEGRAM_BOT_TOKEN"], e["OWNER_CHAT_ID"], e["CHANNEL_ID"], e["AMAZON_TAG"])
