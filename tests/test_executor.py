import asyncio

import maya.tools  # noqa: F401
from maya.agents.state import AgentState
from maya.tools.executor import execute_tool


def test_executor_validates_missing_params() -> None:
    state = AgentState(agent_name="t", task="x")

    async def _run() -> dict:
        return await execute_tool("report_vulnerability", {"title": "x"}, state)

    result = asyncio.run(_run())
    assert "error" in result
    assert "Missing required params" in result["error"]


def test_executor_injects_agent_state() -> None:
    state = AgentState(agent_name="t", task="x")

    async def _run() -> dict:
        return await execute_tool("add_note", {"note": "hello"}, state)

    result = asyncio.run(_run())
    assert result["status"] == "ok"
    assert state.notes[-1] == "hello"
