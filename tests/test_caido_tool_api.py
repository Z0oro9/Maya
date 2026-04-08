from types import SimpleNamespace

from maya.tools.caido_tool import (
    caido_command,
    caido_search_traffic,
    caido_set_scope,
)


def test_caido_tool_api_calls(monkeypatch) -> None:
    def fake_get(url, headers, timeout):
        if url.endswith("/api/openapi.json") or url.endswith("/openapi.json"):
            return SimpleNamespace(status_code=404, json=lambda: {}, text="")
        return SimpleNamespace(status_code=200, json=lambda: {"ok": True}, text="")

    def fake_options(url, headers, timeout):
        return SimpleNamespace(status_code=200, text="")

    def fake_post(url, json, headers, timeout):
        assert "/api/" in url
        return SimpleNamespace(status_code=200, json=lambda: {"ok": True}, text="")

    monkeypatch.setattr("maya.tools.caido_tool.requests.get", fake_get)
    monkeypatch.setattr("maya.tools.caido_tool.requests.options", fake_options)
    monkeypatch.setattr("maya.tools.caido_tool.requests.post", fake_post)

    out1 = caido_search_traffic('req.host.cont:"api"')
    assert out1["status"] == "ok"

    out2 = caido_set_scope("*.example.com")
    assert out2["status"] == "ok"


def test_caido_command_passthrough(monkeypatch) -> None:
    def fake_post(url, json, headers, timeout):
        return SimpleNamespace(status_code=200, json=lambda: {"ok": True}, text="")

    monkeypatch.setattr("maya.tools.caido_tool.requests.post", fake_post)

    out = caido_command(method="/api/replay/send", params='{"requestId": "1"}')
    assert out["status"] == "ok"
