from maya.llm.utils import normalize_tool_format, parse_tool_invocations, truncate_result


def test_parse_invoke_variant() -> None:
    raw = '<invoke name="thinking"><param name="thought">hello</param></invoke>'
    normalized = normalize_tool_format(raw)
    calls = parse_tool_invocations(normalized)
    assert len(calls) == 1
    assert calls[0]["toolName"] == "thinking"
    assert calls[0]["args"]["thought"] == "hello"


def test_parse_multiple_calls() -> None:
    raw = (
        "<function=thinking><parameter=thought>a</parameter></function>"
        "<function=agent_finish><parameter=report>done</parameter></function>"
    )
    calls = parse_tool_invocations(raw)
    assert [c["toolName"] for c in calls] == ["thinking", "agent_finish"]


def test_truncate_result() -> None:
    text = "a" * 12000
    out = truncate_result(text)
    assert "[truncated" in out
    assert len(out) < len(text)
