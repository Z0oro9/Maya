from types import SimpleNamespace

from maya.runtime.docker_runtime import DockerRuntime
from maya.runtime.runtime import Runtime


class _DummyContainer:
    id = "0123456789abcdef"

    def __init__(self):
        self.attrs = {
            "NetworkSettings": {
                "Ports": {
                    "8000/tcp": [{"HostPort": "18000"}],
                }
            }
        }

    def reload(self):
        return None

    def stop(self, timeout=10):
        return None

    def remove(self):
        return None


class _DummyContainers:
    def run(self, *args, **kwargs):
        return _DummyContainer()


class _DummyClient:
    containers = _DummyContainers()


def test_create_sandbox_health_and_register(monkeypatch) -> None:
    runtime = DockerRuntime()
    assert isinstance(runtime, Runtime)
    runtime._client = _DummyClient()  # type: ignore[attr-defined]

    calls = {"health": 0, "register": 0}

    def fake_get(url, timeout):
        calls["health"] += 1
        # fail once, then pass
        if calls["health"] < 2:
            return SimpleNamespace(status_code=503)
        return SimpleNamespace(status_code=200)

    def fake_post(url, json, headers, timeout):
        calls["register"] += 1
        return SimpleNamespace(status_code=200)

    monkeypatch.setattr("maya.runtime.docker_runtime.requests.get", fake_get)
    monkeypatch.setattr("maya.runtime.docker_runtime.requests.post", fake_post)

    info = runtime.create_sandbox(agent_id="a1", auth_token="tok", local_sources=[])
    assert info.agent_id == "a1"
    assert info.server_url.startswith("http://127.0.0.1:")
    assert calls["health"] >= 2
    assert calls["register"] == 1
