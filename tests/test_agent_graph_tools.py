import asyncio

import maya.tools  # noqa: F401
from maya.agents.maya_agent import MayaAgent
from maya.agents.state import AgentState
from maya.tools.executor import execute_tool


def test_create_view_and_message_tools() -> None:
    async def _run() -> None:
        root = MayaAgent(task="root-task", name="root")
        await root.initialize()

        create_result = await execute_tool(
            "create_agent",
            {
                "task": "child-task",
                "name": "child",
                "skills": "ssl_pinning_bypass,api_security",
            },
            root.state,
        )
        assert create_result["status"] == "ok"
        child_id = create_result["agent_id"]

        graph_view = await execute_tool("view_agent_graph", {}, root.state)
        assert graph_view["total_agents"] >= 2

        msg_result = await execute_tool(
            "send_message_to_agent",
            {"target_agent_id": child_id, "message": "hello-child"},
            root.state,
        )
        assert msg_result["status"] == "ok"

    asyncio.run(_run())


def test_send_message_fails_for_unknown_agent() -> None:
    async def _run() -> None:
        state = AgentState(agent_name="root", task="t")
        result = await execute_tool(
            "send_message_to_agent",
            {"target_agent_id": "missing", "message": "x"},
            state,
        )
        assert result["status"] == "error"

    asyncio.run(_run())
