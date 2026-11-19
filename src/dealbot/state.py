"""Estado persistente do bot (JSON)."""
import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .feed import Deal


@dataclass
class State:
    offset: int = 0
    seen: list[str] = field(default_factory=list)
    pending: dict[str, dict] = field(default_factory=dict)
    published: list[str] = field(default_factory=list)

    @classmethod
    def load(cls, path) -> "State":
        try:
            data = json.loads(Path(path).read_text(encoding="utf8"))
            return cls(
                offset=int(data.get("offset", 0)),
                seen=list(data.get("seen", [])),
                pending=dict(data.get("pending", {})),
                published=list(data.get("published", [])),
            )
        except (OSError, ValueError, TypeError, AttributeError):
            return cls()

    def save(self, path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf8") as f:
            json.dump(asdict(self), f, ensure_ascii=False, indent=1)
        os.replace(tmp, path)

    def add_pending(self, message_id: int, deal: Deal) -> None:
        self.pending[str(message_id)] = {
            "title": deal.title,
            "category": deal.category,
            "price": deal.price,
            "image": deal.image,
        }

    def mark_published(self, asin: str) -> None:
        if asin not in self.published:
            self.published.append(asin)

    def trim(self) -> None:
        self.seen = self.seen[-500:]
        self.published = self.published[-2000:]
        if len(self.pending) > 100:
            keys = sorted(self.pending, key=int)[-100:]
            self.pending = {k: self.pending[k] for k in keys}
