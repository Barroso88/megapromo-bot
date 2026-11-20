"""Estado do monitor (data/status.json) e vigia que o mantém ligado ao Telegram."""
import asyncio
import json
import logging
import os
import tempfile
import time
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("dealbot.status")


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class Status:
    def __init__(self, path):
        self.path = Path(path)
        self.data = {
            "started_at": _now(), "last_event_at": None, "last_event_source": None, "events_total": 0,
            "connected": None, "reconnects": 0, "last_catch_up_at": None, "last_error": None,
        }

    def event(self, source: str) -> None:
        self.data["events_total"] += 1
        self.data["last_event_at"] = _now()
        self.data["last_event_source"] = source

    def set(self, **kwargs) -> None:
        self.data.update(kwargs)

    def bump(self, key: str) -> None:
        self.data[key] = self.data.get(key, 0) + 1

    def save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=self.path.parent, suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf8") as f:
                json.dump(self.data, f, ensure_ascii=False)
            os.replace(tmp, self.path)
        except OSError as e:
            logger.warning("Não foi possível guardar o estado do monitor: %s", e)


async def watchdog_tick(client, status: Status, do_catch_up: bool = False) -> None:
    """Uma verificação: reconecta se a ligação caiu e, se pedido, pede ao Telegram as mensagens em falta."""
    try:
        if not client.is_connected():
            logger.warning("Ligação ao Telegram perdida; a tentar reconectar...")
            await client.connect()
            status.bump("reconnects")
        status.set(connected=client.is_connected(), last_error=None)
        if do_catch_up:
            await client.catch_up()
            status.set(last_catch_up_at=_now())
    except Exception as e:
        logger.warning("Vigia: %s: %s", type(e).__name__, e)
        status.set(connected=False, last_error=f"{type(e).__name__}: {e}")
    finally:
        status.save()


async def watchdog_loop(client, status: Status, interval: int = 60, catch_up_every: int = 300) -> None:
    last_catch_up = time.monotonic()
    while True:
        await asyncio.sleep(interval)
        due = time.monotonic() - last_catch_up >= catch_up_every
        if due:
            last_catch_up = time.monotonic()
        await watchdog_tick(client, status, do_catch_up=due)
