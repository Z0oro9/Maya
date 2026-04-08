# Maya AI Agent â€” Agent System & LLM Integration

## 1. BaseAgent Implementation

BaseAgent is the abstract class that implements the core agent loop. Every agent type (root orchestrator, static analyzer, dynamic tester) inherits from it.

### Metaclass: AgentMeta

Implement a metaclass that automatically registers every `BaseAgent` subclass into a global `_agent_registry: dict[str, type]` when the class is defined. This allows `create_agent` to look up agent classes by name string without manual mapping.

```
_agent_registry = {}

class AgentMeta(type(ABC)):
    def __init__(cls, name, bases, namespace):
        super().__init__(name, bases, namespace)
        if name != "BaseAgent":
            _agent_registry[name] = cls
```

### Constructor Parameters

| Parameter | Purpose |
|-----------|---------|
| `agent_id` | Optional override; auto-generated UUID[:8] otherwise |
| `name` | Human-readable name for display |
| `llm` | LLMClient instance (or creates default) |
| `skills` | List of skill names to load |
| `parent_id` | Parent agent ID for sub-agents |
| `max_iterations` | Hard stop for the loop (default 50) |
| `target_app` | Package name/bundle ID |
| `device_id` | Connected device identifier |
| `platform` | "android" or "ios" |

### Abstract Methods (must be implemented by subclasses)

1. `build_system_prompt() â†’ str` â€” Renders the full system prompt including skills, tools, and context
2. `on_scan_complete(findings: list[dict]) â†’ None` â€” Called when the agent finishes; handles cleanup and reporting

### The Agent Loop (`agent_loop`)

```
async def agent_loop(tracer):
    while not should_terminate() and not stop_event:
        iteration_count += 1
        try:
            should_stop = await _process_iteration(tracer)
            if should_stop:
                break
        except Exception as e:
            # Inject error as observation so LLM can self-correct
            add_message("user", f"<e>Error: {e}. Adjust your approach.</e>")
            tool_errors += 1
            if tool_errors > 10:
                break
    
    status = COMPLETED
    await on_scan_complete(findings)
```

### Single Iteration (`_process_iteration`)

```
async def _process_iteration(tracer):
    # 1. LLM call
    response = await llm.generate(get_conversation_history())
    
    # 2. Record assistant message
    add_message("assistant", response.content)
    
    # 3. Parse tool calls
    normalized = normalize_tool_format(response.content)
    tool_calls = parse_tool_invocations(normalized)
    
    if not tool_calls:
        return False  # LLM is thinking, continue
    
    # 4. Execute tools
    results = await process_tool_invocations(tool_calls, agent_state)
    
    # 5. Check termination signals and append observations
    for result in results:
        if isinstance(result, dict) and (result.get("scan_completed") or result.get("agent_completed")):
            return True  # Stop the loop
        add_message("user", format_observation(result))
    
    return False
```

### Spawning Sub-Agents

Any agent can spawn children via:

```
child_id = await spawn_subagent(
    task="Bypass SSL pinning on com.target.app and map all API endpoints",
    name="ssl_api_agent",
    skills=["ssl_pinning_bypass", "api_security"],
    agent_class="MayaAgent"
)
```

This calls `AgentGraph.create_agent()` which instantiates the child, adds it to the graph, and launches its `agent_loop` as an `asyncio.Task`.

---

## 2. MayaAgent Implementation

The concrete agent class for mobile security testing. Inherits from `BaseAgent`.

### Additional Constructor Parameters

| Parameter | Purpose |
|-----------|---------|
| `targets` | List of target dicts: `[{"type": "local", "value": "./app.apk"}, ...]` |
| `instruction` | Custom testing instructions from user |
| `scan_mode` | "quick", "standard", or "comprehensive" |

### `build_system_prompt()` Implementation

1. Validate and load skills: `validate_skill_names(state.skills)` â†’ `load_skills(valid)`
2. Assemble tools prompt: `get_tools_prompt()`
3. Determine testing mode: white-box (source), black-box (live app), grey-box (both)
4. Render the Jinja2 template `system_prompt.jinja` with all context variables

### System Prompt Template Structure

The Jinja2 template should contain these sections (in order):

1. **`<identity>`** â€” Who the agent is, its role, its capabilities
2. **`<methodology>`** â€” The OWASP MASTG testing methodology steps
3. **`<root_agent_instructions>`** â€” (conditional, root only) Delegation rules, agent management strategy
4. **`<targets>`** â€” Current target configuration, device info, testing mode
5. **`<custom_instructions>`** â€” (conditional) User-provided focus areas
6. **`<device_capabilities>`** â€” What's available on the connected device (rooted/jailbroken features)
7. **`<agent_graph_rules>`** â€” How to use create_agent, send_message, agent_finish, finish_scan
8. **`<tools>`** â€” Full tool XML schemas from `{{ tools_prompt }}`
9. **`<tool_usage_guidelines>`** â€” Priority rules, critical instructions, tool selection heuristics
10. **`<finding_format>`** â€” How to structure vulnerability reports
11. **`<thinking_process>`** â€” Before/after checklist for each iteration
12. **`<specialized_knowledge>`** â€” (conditional) Skill content injected via Jinja loop

### Skill Injection (in the template)

```jinja
{% if loaded_skill_names %}
<specialized_knowledge>
{% for skill_name in loaded_skill_names %}
<{{ skill_name }}>
{{ get_skill(skill_name) }}
</{{ skill_name }}>
{% endfor %}
</specialized_knowledge>
{% endif %}
```

This means an agent spawned with `skills=["ssl_pinning_bypass", "insecure_storage"]` gets the full content of both skill markdown files embedded in its system prompt.

### `execute_scan()` Entry Point

This is the top-level method called by the CLI:

```
async def execute_scan(task, tracer):
    if not task:
        task = build_default_task()  # from targets + instruction
    await initialize(task)
    await agent_loop(tracer)
    return {findings, api_endpoints, intercepted_traffic, iterations, tool_calls, status}
```

---

## 3. LLM Integration via LiteLLM

### Why LiteLLM

LiteLLM provides a unified `completion()` interface across 100+ LLM providers. You configure the model as `provider/model_name` (e.g., `openai/gpt-4o`, `anthropic/claude-sonnet-4-20250514`, `ollama/llama3`). LiteLLM handles:

- API key management per provider
- Request format translation
- Streaming support
- Token counting
- Rate limit handling
- Fallback models

### LLMClient Implementation

The `LLMClient` class wraps LiteLLM's async completion:

1. **Constructor**: Takes `LLMConfig`, sets up LiteLLM options (`drop_params=True` for compatibility, verbose mode)
2. **`generate(messages, temperature, max_tokens)`**: The main method
   - Calls `litellm.acompletion()` with model, messages, temperature, max_tokens
   - Handles retries: `RateLimitError` â†’ exponential backoff (5s, 10s, 20s), `APIConnectionError` â†’ retry with backoff
   - Returns `LLMResponse` with content, usage, model, finish_reason
3. **`generate_with_schema(messages, response_schema)`**: For structured JSON output
   - Appends schema instruction to last message
   - Parses JSON from response, stripping markdown fences if present

### Configuration Loading Priority

1. Environment variables (highest): `MAYA_LLM`, `LLM_API_KEY`, `LLM_API_BASE`, `MAYA_REASONING_EFFORT`
2. Saved config file: `~/.maya/config.json`
3. Defaults (lowest): `openai/gpt-4o`, temperature 0.1, max_tokens 8192

### Recommended Models

| Provider | Model | Best For |
|----------|-------|----------|
| OpenAI | `openai/gpt-4o` | Best overall reasoning for security analysis |
| Anthropic | `anthropic/claude-sonnet-4-20250514` | Strong code analysis, long context |
| Google | `vertex_ai/gemini-2.0-flash` | Fast, cost-effective for sub-agents |
| Local | `ollama/llama3.1:70b` | Air-gapped environments, no data leaves machine |

---

## 4. Memory Compression

For long-running scans, the conversation history grows beyond the context window. Implement a `MemoryCompressor` that:

1. **Detects threshold**: When total tokens exceed 70% of model's context window
2. **Summarizes**: Takes the middle portion of the conversation (preserving first 5 messages for system/task context and last 10 for recent state)
3. **Compresses**: Uses a secondary LLM call with prompt "Summarize this conversation, preserving all findings, tool results, and key observations"
4. **Replaces**: Swaps the middle section with the summary wrapped in `<compressed_history>` tags

### When to Trigger

Check after each iteration. The Strix approach: if `token_count > 0.7 * max_context`, compress. Use LiteLLM's `litellm.token_counter()` for accurate counting per model.

---

## 5. Vulnerability Deduplication

Multiple agents may discover the same vulnerability independently (e.g., static analysis finds a hardcoded key, and dynamic analysis extracts it at runtime).

### Implementation

Maintain a global `_reported_hashes: set[str]` (module-level in the reporting tool).

For each finding:
1. Compute `hash = SHA256(title.lower().strip() + "|" + category.lower().strip())[:16]`
2. If hash in `_reported_hashes`, return `{"status": "duplicate"}`
3. Otherwise, add to set and proceed with recording

### Cross-Agent Deduplication

Since `_reported_hashes` is a global module-level set and all agents run in the same host process (only tool execution is sandboxed), deduplication works automatically across all agents.

---

## 6. Inter-Agent Communication Patterns

### Pattern 1: Discovery Sharing

Static agent finds API URLs in decompiled code â†’ sends message to API agent:
```
send_message_to_agent(
    target_agent_id="api_agent_id",
    message="Found API base URL: https://api.target.com/v2. Key endpoints: /auth/login, /users/{id}, /payments/process"
)
```

### Pattern 2: Testing Coordination

Root agent sees that SSL pinning bypass failed â†’ sends redirect to dynamic agent:
```
send_message_to_agent(
    target_agent_id="dynamic_agent_id",
    message="Standard SSL pinning bypass failed. The app uses a custom TrustManager. Try hooking com.target.security.CustomTrustManager.verify directly."
)
```

### Pattern 3: Findings Escalation

Dynamic agent finds a critical auth bypass â†’ root agent decides to spawn a focused exploitation agent:
```
create_agent(
    task="Exploit the JWT signature bypass found by dynamic_agent. Chain it with the IDOR on /users/{id} endpoint to demonstrate full account takeover.",
    name="exploit_chain_agent",
    skills="auth_bypass,api_security"
)
```

### How Messages Are Delivered

When `send_message_to_agent` is called:
1. Message is added to `_agent_messages[target_id]` queue
2. Message is also injected directly into the target agent's conversation history as:
   ```xml
   <message from='sender_agent_id'>
   Found API base URL: https://api.target.com/v2...
   </message>
   ```
3. On the target agent's next iteration, the LLM sees this message and can act on it

---

## 7. Root Agent Orchestration Strategy

The root agent's system prompt includes delegation rules. Here is how a typical root agent execution flows:

### Phase 1: Reconnaissance (iterations 1-3)
- Analyze target type (APK, IPA, URL, device)
- If APK/IPA provided, spawn static analysis agent
- Connect to device, verify frida-server running

### Phase 2: Delegation (iterations 4-8)
- Spawn sub-agents based on what was learned:
  - `static_analyzer` with skills: `["insecure_storage", "insecure_crypto", "api_security"]`
  - `dynamic_tester` with skills: `["ssl_pinning_bypass", "auth_bypass", "frida_instrumentation"]`
  - `api_discoverer` with skills: `["api_security", "traffic_analysis"]`
- If Flutter/RN detected, spawn framework-specific agent

### Phase 3: Monitoring (iterations 9-30)
- Periodically call `view_agent_graph` to check sub-agent progress
- Read inter-agent messages for discoveries
- Redirect agents if they get stuck or loop
- Share cross-agent discoveries

### Phase 4: Aggregation (iterations 31-40)
- Wait for sub-agents to finish
- Review all findings
- Identify exploit chains
- Assess overall risk

### Phase 5: Completion (iterations 41+)
- Call `finish_scan` with comprehensive summary
- Include: total findings by severity, key exploit chains, risk assessment, remediation priorities
