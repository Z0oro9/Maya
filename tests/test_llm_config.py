from maya.llm.config import LLMConfig


def test_llm_config_apply_overrides() -> None:
    cfg = LLMConfig().apply_overrides(
        model="openai/gpt-4o",
        api_key="test-key",
        api_base="http://localhost:4000",
    )
    assert cfg.model == "openai/gpt-4o"
    assert cfg.api_key == "test-key"
    assert cfg.api_base == "http://localhost:4000"
