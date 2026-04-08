import asyncio

import maya.tools  # noqa: F401
from maya.agents.state import AgentState
from maya.tools.executor import execute_tool


def test_smoke_shared_context_and_skill_tools() -> None:
    async def _run() -> None:
        state = AgentState(agent_name="root", task="t")

        w = await execute_tool("shared_context_write", {"key": "discovered_urls", "value": '["https://a"]'}, state)
        assert w["status"] == "ok"

        r = await execute_tool("shared_context_read", {"key": "discovered_urls"}, state)
        assert r["value"] == ["https://a"]

        skills = await execute_tool("list_available_skills", {}, state)
        assert skills["status"] == "ok"

    asyncio.run(_run())
