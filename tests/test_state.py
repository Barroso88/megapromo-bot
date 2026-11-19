from dealbot.feed import Deal
from dealbot.state import State


def test_roundtrip(tmp_path):
    p = tmp_path / "s.json"
    s = State(offset=7, seen=["a"], published=["B0DWDH32M8"])
    s.add_pending(42, Deal("g", "T", "C", "1€", "i", "u"))
    s.save(p)
    s2 = State.load(p)
    assert s2.offset == 7 and s2.seen == ["a"] and s2.published == ["B0DWDH32M8"]
    assert s2.pending["42"] == {"title": "T", "category": "C", "price": "1€", "image": "i"}


def test_missing_and_corrupt_give_empty(tmp_path):
    assert State.load(tmp_path / "nope.json") == State()
    p = tmp_path / "bad.json"
    p.write_text("{not json")
    assert State.load(p) == State()
    p.write_text("{}")
    assert State.load(p) == State()


def test_trim():
    s = State(seen=[str(i) for i in range(600)])
    for i in range(120):
        s.add_pending(i, Deal("g", "T", "C", "", "", ""))
    s.trim()
    assert len(s.seen) == 500 and s.seen[-1] == "599" and s.seen[0] == "100"
    assert len(s.pending) == 100 and "119" in s.pending and "0" not in s.pending


def test_mark_published_no_duplicates():
    s = State()
    s.mark_published("B0DWDH32M8")
    s.mark_published("B0DWDH32M8")
    assert s.published == ["B0DWDH32M8"]
