import asyncio
from pathlib import Path

import maya.tools  # noqa: F401
from maya.agents.maya_agent import MayaAgent
from maya.llm.llm import LLMResponse


class FakeLLM:
    async def generate(self, messages, temperature=None, max_tokens=None):
        del messages, temperature, max_tokens
        return LLMResponse(
            content="<function=agent_finish><parameter=report>done</parameter></function>",
            tool_calls=[],
            usage={"prompt_tokens": 1, "completion_tokens": 1},
            model="fake",
            finish_reason="stop",
        )


def test_agent_loop_completes_on_agent_finish() -> None:
    async def _run():
        agent = MayaAgent(task="test", llm=FakeLLM(), max_iterations=5)
        return await agent.execute_scan()

    result = asyncio.run(_run())
    assert result["status"] == "completed"
    assert result["iterations"] == 1


def test_system_prompt_uses_template_and_skills() -> None:
    agent = MayaAgent(task="test", skills=["ssl_pinning_bypass"], max_iterations=1)
    prompt = agent.build_system_prompt()

    assert Path(agent._template_path).exists()
    assert "<identity>" in prompt
    assert "<tool_usage_guidelines>" in prompt
    assert "<specialized_knowledge>" in prompt
    assert "SSL Pinning Bypass Skill" in prompt
