import asyncio
import json
from datetime import datetime, timedelta

from dealbot.monitor_status import Status, watchdog_tick


def test_status_records_events_and_saves_json(tmp_path):
    st = Status(tmp_path / "status.json")
    st.event("@cupoes")
    st.event("@bilbiamtengarsada")
    st.set(connected=True)
    st.save()
    data = json.loads((tmp_path / "status.json").read_text())
    assert data["events_total"] == 2 and data["last_event_source"] == "@bilbiamtengarsada"
    assert data["connected"] is True and data["started_at"] and data["last_event_at"]
    datetime.fromisoformat(data["last_event_at"])


def test_status_survives_unwritable_path(tmp_path):
    st = Status(tmp_path / "nope" / "deeper" / "status.json")
    st.event("@x")
    st.save()                                   # cria as pastas, ou pelo menos não rebenta
    assert st.data["events_total"] == 1


class FakeClient:
    def __init__(self, connected=True, fail_connect=False):
        self.connected, self.fail_connect, self.calls = connected, fail_connect, []

    def is_connected(self):
        return self.connected

    async def connect(self):
        self.calls.append("connect")
        if self.fail_connect:
            raise OSError("sem rede")
        self.connected = True

    async def catch_up(self):
        self.calls.append("catch_up")


def test_watchdog_reconnects_a_dropped_client_and_counts_it(tmp_path):
    st, client = Status(tmp_path / "s.json"), FakeClient(connected=False)
    asyncio.run(watchdog_tick(client, st, do_catch_up=False))
    assert client.calls == ["connect"] and st.data["reconnects"] == 1 and st.data["connected"] is True


def test_watchdog_runs_catch_up_when_asked_and_records_it(tmp_path):
    st, client = Status(tmp_path / "s.json"), FakeClient()
    asyncio.run(watchdog_tick(client, st, do_catch_up=True))
    assert client.calls == ["catch_up"] and st.data["last_catch_up_at"]


def test_watchdog_never_raises_and_reports_disconnected(tmp_path):
    st, client = Status(tmp_path / "s.json"), FakeClient(connected=False, fail_connect=True)
    asyncio.run(watchdog_tick(client, st, do_catch_up=True))             # não pode rebentar
    assert st.data["connected"] is False and st.data["last_error"]


class _TargetClient:
    def __init__(self, entity_error=None, dialogs_error=None):
        self.entity_error, self.dialogs_error, self.calls = entity_error, dialogs_error, []

    async def get_dialogs(self, limit=None):
        self.calls.append("dialogs")
        if self.dialogs_error:
            raise self.dialogs_error

    async def get_entity(self, target):
        self.calls.append(("entity", target))
        if self.entity_error:
            raise self.entity_error
        return type("E", (), {"title": "MegaPromo", "username": "megapromo_pt"})()


def test_check_target_ok_records_the_channel_title(tmp_path):
    from dealbot.monitor_status import check_target
    st, client = Status(tmp_path / "s.json"), _TargetClient()
    assert asyncio.run(check_target(client, "@megapromo_pt", st)) is True
    assert st.data["target_error"] is None and st.data["target_title"] == "MegaPromo"
    assert client.calls[0] == "dialogs"                                   # preenche a cache (necessário para IDs numéricos)


def test_check_target_reports_an_unreachable_channel(tmp_path):
    from dealbot.monitor_status import check_target
    st = Status(tmp_path / "s.json")
    client = _TargetClient(entity_error=ValueError('No user has "megapromo_pt" as username'))
    assert asyncio.run(check_target(client, "@megapromo_pt", st)) is False
    assert "No user has" in st.data["target_error"]
    assert json.loads((tmp_path / "s.json").read_text())["target_error"]


def test_check_target_survives_a_failing_dialog_listing(tmp_path):
    from dealbot.monitor_status import check_target
    st = Status(tmp_path / "s.json")
    assert asyncio.run(check_target(_TargetClient(dialogs_error=OSError("rede")), "@x", st)) is True
