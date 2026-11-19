import json

from dealbot.translate import to_pt


class Resp:
    def __init__(self, body): self.body = body
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def read(self): return self.body


def opener_for(data):
    def op(req, timeout=0):
        assert "tl=pt-PT" in req.full_url and "sl=es" in req.full_url
        return Resp(json.dumps(data).encode())
    return op


def test_joins_segments():
    data = [[["Câmara de ação. ", "Cámara de acción. ", None], ["Como novo", "Como Nuevo", None]], None, "es"]
    assert to_pt("Cámara de acción. Como Nuevo", opener=opener_for(data)) == "Câmara de ação. Como novo"


def test_failure_returns_original():
    def boom(req, timeout=0): raise OSError("rede")
    assert to_pt("Hola", opener=boom) == "Hola"


def test_garbage_returns_original():
    assert to_pt("Hola", opener=opener_for({"x": 1})) == "Hola"


def test_empty_text_no_call():
    def boom(req, timeout=0): raise AssertionError("não devia chamar")
    assert to_pt("  ", opener=boom) == "  "
