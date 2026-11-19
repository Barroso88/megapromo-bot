"""Cliente mínimo da Telegram Bot API."""
import json
import urllib.error
import urllib.request


class TelegramError(Exception):
    pass


def _description(e: urllib.error.HTTPError) -> str:
    try:
        return str(json.loads(e.read().decode()).get("description", ""))
    except Exception:
        return ""


class Telegram:
    def __init__(self, token: str, opener=urllib.request.urlopen):
        self._token = token
        self._opener = opener

    def _call(self, method: str, payload: dict):
        url = f"https://api.telegram.org/bot{self._token}/{method}"
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            with self._opener(req, timeout=30) as resp:
                data = json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            raise TelegramError(f"{method}: HTTP {e.code} {_description(e)}".strip()) from None
        except Exception as e:
            raise TelegramError(f"{method}: {type(e).__name__}") from None
        if not data.get("ok"):
            raise TelegramError(f"{method}: {data.get('description', 'erro')}")
        return data["result"]

    def get_updates(self, offset: int) -> list[dict]:
        return self._call("getUpdates", {"offset": offset, "timeout": 0})

    def send_message(self, chat_id, text: str, reply_to: int | None = None) -> int:
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        if reply_to is not None:
            payload["reply_to_message_id"] = reply_to
        return self._call("sendMessage", payload)["message_id"]

    def send_photo(self, chat_id, photo_url: str, caption: str) -> int:
        payload = {"chat_id": chat_id, "photo": photo_url, "caption": caption, "parse_mode": "HTML"}
        return self._call("sendPhoto", payload)["message_id"]
