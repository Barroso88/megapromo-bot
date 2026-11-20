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
