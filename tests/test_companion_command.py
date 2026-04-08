from types import SimpleNamespace

from maya.tools.device_bridge import companion_app_command


def test_companion_command_http_fallback(monkeypatch) -> None:
    def fake_post(url, json, timeout):
        return SimpleNamespace(
            headers={"content-type": "application/json"},
            json=lambda: {"id": json["id"], "status": "success"},
            text="",
        )

    monkeypatch.setattr("maya.tools.device_bridge.websockets", None)
    monkeypatch.setattr("maya.tools.device_bridge.requests.post", fake_post)

    result = companion_app_command("get_status", "{}", "5")
    assert result["status"] == "ok"
    assert result["response"]["status"] == "success"
