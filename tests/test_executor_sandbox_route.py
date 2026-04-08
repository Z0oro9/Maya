import asyncio

from maya.agents.state import AgentState
from maya.tools.executor import execute_tool


def test_executor_uses_sandbox_http_when_available(monkeypatch) -> None:
    class DummyResp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"result": {"status": "ok"}, "error": None}

    class DummyClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, json, headers):
            assert url.endswith("/execute")
            assert "Authorization" in headers
            assert json["tool_name"] == "terminal_execute"
            return DummyResp()

    state = AgentState(agent_name="root", task="t")
    state.sandbox_info = {"server_url": "http://127.0.0.1:8000", "auth_token": "tok"}

    monkeypatch.setattr("maya.tools.executor.httpx.AsyncClient", lambda timeout: DummyClient())

    async def _run():
        result = await execute_tool("terminal_execute", {"command": "echo hi", "timeout": "1"}, state)
        assert result["status"] == "ok"

    asyncio.run(_run())
