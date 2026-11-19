import os

from .bot import run_once
from .config import Config
from .state import State
from .telegram import Telegram

STATE_PATH = os.environ.get("STATE_PATH", "data/state.json")


def main() -> None:
    cfg = Config.from_env()
    state = State.load(STATE_PATH)
    try:
        run_once(cfg, Telegram(cfg.token), state)
    finally:
        state.save(STATE_PATH)


if __name__ == "__main__":
    main()
