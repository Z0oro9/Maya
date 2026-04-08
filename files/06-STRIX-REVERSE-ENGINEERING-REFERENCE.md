# Maya AI Agent â€” Strix Reverse Engineering Reference

This document captures the key architectural patterns from Strix's codebase that should be replicated (adapted for mobile) in Maya.

---

## 1. Strix Module Structure (from `strix.spec`)

```
strix/
â”œâ”€â”€ agents/
â”‚   â”œâ”€â”€ base_agent.py        # BaseAgent class â€” core agent loop
â”‚   â”œâ”€â”€ state.py             # AgentState â€” conversation history + lifecycle
â”‚   â””â”€â”€ StrixAgent/
â”‚       â””â”€â”€ system_prompt.jinja  # Jinja2 system prompt (430+ lines)
â”œâ”€â”€ llm/
â”‚   â”œâ”€â”€ llm.py               # LLM client wrapping LiteLLM
â”‚   â”œâ”€â”€ config.py            # Configuration from env/file
â”‚   â”œâ”€â”€ utils.py             # parse_tool_invocations(), normalize_tool_format()
â”‚   â”œâ”€â”€ request_queue.py     # Rate limiting and request queuing
â”‚   â””â”€â”€ memory_compressor.py # Conversation summarization for long scans
â”œâ”€â”€ runtime/
â”‚   â”œâ”€â”€ runtime.py           # Abstract runtime interface
â”‚   â””â”€â”€ docker_runtime.py    # Docker container lifecycle management
â”œâ”€â”€ tools/
â”‚   â”œâ”€â”€ registry.py          # @register_tool, XML schema loading, get_tools_prompt()
â”‚   â”œâ”€â”€ executor.py          # Validation, routing (local vs sandbox), execution
â”‚   â””â”€â”€ argument_parser.py   # Type coercion for tool arguments
â”œâ”€â”€ skills/                  # .md files organized by category
â””â”€â”€ telemetry/
    â””â”€â”€ tracer.py            # Central tracing and reporting
```

**Key insight**: The structure is very clean â€” agents, LLM, runtime, tools, and skills are fully separated. Tools never import agents. Agents only know tools through the registry. This decoupling is what makes the system extensible.

---

## 2. The Agent Loop (from `base_agent.py`)

Strix's core pattern that Maya must replicate:

### Initialization
```
create_sandbox() â†’ wait for tool_server health check â†’ register agent
set task â†’ add "system" message (rendered prompt) â†’ add "user" message (task)
```

### Main Loop
```
while not should_terminate and not stop_event:
    iteration_count++
    response = llm.generate(conversation_history)
    add_message("assistant", response.content)
    
    tool_calls = parse_tool_invocations(normalize_tool_format(response.content))
    
    if no tool_calls:
        continue  # LLM is thinking
    
    results = process_tool_invocations(tool_calls, agent_state)
    
    for result in results:
        if result has scan_completed or agent_completed:
            stop loop
        add observation to conversation
```

### Critical Detail: Error Recovery

When a tool fails or the LLM makes a mistake, the error is injected back into the conversation as an observation. The LLM sees the error and self-corrects on the next iteration. This is why the system is resilient â€” errors don't crash the loop, they become learning signals.

---

## 3. Tool Registration Pattern (from `registry.py`)

### The Decorator

```python
@register_tool(sandbox_execution=False)
async def create_agent(task, name, skills, agent_state):
    ...
```

The decorator:
1. Reads `func.__name__` as the tool name
2. Derives the XML schema path from `func.__module__`
3. Loads and processes the XML schema (including `{{DYNAMIC_SKILLS_DESCRIPTION}}` replacement)
4. Parses parameter constraints (required/optional sets)
5. Appends to three global registries: `tools`, `_tools_by_name`, `_tool_param_schemas`

### Schema Location Convention

For function `strix.tools.terminal.terminal_actions.terminal_execute`:
- Module parts: `["strix", "tools", "terminal", "terminal_actions"]`
- Schema path: `strix/tools/terminal/terminal_actions_schema.xml`

### XML Tool Schema Example

```xml
<tool name="terminal_execute">
  <description>Execute a shell command in the sandbox terminal.</description>
  <parameters>
    <parameter name="command" type="string" required="true">
      The shell command to execute
    </parameter>
    <parameter name="timeout" type="string" required="false">
      Timeout in seconds (default: 60)
    </parameter>
  </parameters>
</tool>
```

---

## 4. Tool Invocation Format (from `llm/utils.py`)

### Canonical Format (taught in system prompt)

```xml
<function=terminal_execute>
<parameter=command>nmap -sV target.com</parameter>
</function>
```

### Variant Format (also parsed)

```xml
<invoke name="terminal_execute">
<param name="command">nmap -sV target.com</param>
</invoke>
```

### `normalize_tool_format()` â€” Lines 12-31

Regex substitutions to convert variant â†’ canonical:
- `<invoke\s+name="([^"]+)"\s*>` â†’ `<function=\1>`
- `</invoke>` â†’ `</function>`
- `<param\s+name="([^"]+)"\s*>` â†’ `<parameter=\1>`
- `</param>` â†’ `</parameter>`

### `parse_tool_invocations()` â€” Lines 84-111

Two-level regex extraction:
1. Outer: `<function=(\w+)>(.*?)</function>` with `re.DOTALL`
2. Inner: `<parameter=(\w+)>(.*?)</parameter>` with `re.DOTALL`

Returns: `[{"toolName": str, "args": dict[str, str]}]`

---

## 5. Tool Execution Routing (from `executor.py`)

### Decision Path

```
tool_name â†’ validate_tool_availability (exists in registry?)
          â†’ _validate_tool_arguments (required params? no unknown params?)
          â†’ should_execute_in_sandbox(tool_name)?
              YES â†’ _execute_tool_in_sandbox (HTTP POST to container)
              NO  â†’ _execute_tool_locally (call function directly)
```

### Sandbox Execution â€” HTTP Interface

```
POST {server_url}/execute
Authorization: Bearer {sandbox_token}
Content-Type: application/json

{
  "agent_id": "abc12345",
  "tool_name": "terminal_execute",
  "kwargs": {"command": "nmap -sV target.com"}
}

Response:
{"result": "...", "error": null}
```

### Result Formatting

- Results > 10,000 chars: truncated to first 4,000 + `[truncated]` + last 4,000
- If result contains `screenshot` key (base64 PNG): extracted as separate image content block
- Termination signals: `{"scan_completed": True}` or `{"agent_completed": True}` stop the agent loop

### Agent State Injection

If a tool function's signature includes `agent_state` parameter (detected via `inspect.signature()`), the executor injects the current agent's `AgentState` object. This gives tools access to device_id, platform, target_app, findings, etc.

---

## 6. Agent Graph (from `graph.py` and system prompt)

### Graph Structure

```python
_agent_graph = {
    "nodes": {agent_id: AgentNode(...)},
    "edges": [{"from": parent_id, "to": child_id, "type": "delegation"}],
    "_agent_messages": {agent_id: [{"from": ..., "content": ...}]},
    "_agent_instances": {agent_id: BaseAgent},
    "_agent_states": {agent_id: AgentState},
}
```

### Tree Enforcement (from system_prompt.jinja lines 209-220)

Strix's prompt explicitly tells the LLM:
- Agent graph must be a strict TREE â€” each agent has exactly one parent
- Flat or unrelated agent structures are prohibited
- Child agents must perform subtasks that directly support parent's goal
- No more than 5-7 concurrent agents

### Agent Lifecycle via Tools

The LLM manages agents through tool calls:
1. `create_agent(task, name, skills)` â†’ returns child agent_id
2. `view_agent_graph()` â†’ returns status of all agents
3. `send_message_to_agent(agent_id, message)` â†’ inter-agent communication
4. `agent_finish(report)` â†’ child reports to parent
5. `finish_scan(summary)` â†’ root concludes everything

---

## 7. Skills Injection (from system_prompt.jinja lines 423-431)

### Jinja2 Pattern

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

### Skills Loading

- Skills stored as `.md` files under `strix/skills/{category}/`
- YAML frontmatter (name, description) stripped on load
- `generate_skills_description()` produces the listing injected into `create_agent`'s XML schema via `{{DYNAMIC_SKILLS_DESCRIPTION}}`

---

## 8. Sandbox Environment (from system_prompt.jinja lines 364-420)

Strix uses a Kali Linux container with pre-installed tools. The system prompt lists all available tools so the LLM knows what it can use.

### Container Components

| Component | Implementation | Purpose |
|-----------|---------------|---------|
| `tool_server` | FastAPI on port 8000 | HTTP API for receiving tool requests |
| `TerminalManager` | libtmux sessions | Persistent shell sessions per agent |
| `BrowserTabManager` | Playwright/Chromium | Web testing (not needed for mobile) |
| `PythonSessionManager` | IPython kernel | Persistent Python REPL per agent |
| `ProxyManager` | Caido process | HTTP proxy (replace with mitmproxy for mobile) |

### What Maya Replaces/Adds

| Strix Component | Maya Equivalent |
|----------------|-------------------|
| Browser automation (Playwright) | **Not needed** â€” remove this |
| HTTP proxy (Caido) | **mitmproxy** â€” better for mobile traffic interception |
| â€” | **Frida integration** â€” frida-tools pre-installed, scripts executed by tool_server |
| â€” | **ADB/idevice** â€” device communication tools |
| â€” | **MobSF client** â€” API calls to MobSF container |
| â€” | **APKTool/JADX** â€” mobile decompilation tools |
| â€” | **Objection** â€” Frida automation framework |
| â€” | **Reflutter/Blutter** â€” Flutter RE tools |

---

## 9. Key Patterns to Replicate Exactly

1. **The `@register_tool` + XML schema + `get_tools_prompt()` pipeline** â€” This is the most important pattern. It cleanly separates tool capabilities from agent logic and makes the system extensible without touching core code.

2. **The agent loop with error-as-observation recovery** â€” Don't crash on tool failures. Feed errors back so the LLM can adapt. This is what makes the system autonomous.

3. **Jinja2 system prompt with skill injection** â€” The prompt IS the agent's brain. Spending time making it excellent is the highest-ROI activity.

4. **Module-level conditional imports in `tools/__init__.py`** â€” Based on sandbox mode flag. This ensures the host process doesn't load sandbox-only code, and the container doesn't load host-only code.

5. **`needs_agent_state()` check via `inspect.signature()`** â€” Elegant pattern for optionally injecting agent state into tools that need it.

6. **Global dedup set for findings** â€” Simple but effective cross-agent deduplication via content hashing.

7. **Memory compression at 70% context utilization** â€” Keeps long scans running without losing critical context.
