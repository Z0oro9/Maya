# Maya AI Agent â€” Models & Data Structures

## 1. AgentState

The central data structure for each agent instance. Tracks everything an agent needs across its lifecycle.

### Fields

| Field | Type | Purpose |
|-------|------|---------|
| `agent_id` | `str` | Unique 8-char UUID prefix, auto-generated |
| `agent_name` | `str` | Human-readable name (e.g., "static_analyzer", "frida_ssl_agent") |
| `task` | `str` | The task description assigned to this agent |
| `parent_id` | `str or None` | ID of the parent agent; `None` for root |
| `status` | `AgentStatus` | Current lifecycle status (see enum below) |
| `skills` | `list[str]` | Skill names loaded into this agent's prompt |
| `messages` | `list[dict]` | Full conversation history (system, user, assistant, tool) |
| `tool_call_count` | `int` | Total tool invocations made |
| `tool_errors` | `int` | Count of failed tool calls |
| `iteration_count` | `int` | Current iteration number in the agent loop |
| `max_iterations` | `int` | Hard limit on iterations (default: 50) |
| `sandbox_id` | `str or None` | Docker container ID |
| `sandbox_token` | `str or None` | Auth token for the tool_server |
| `sandbox_info` | `dict` | Connection details: `server_url`, `auth_token`, etc. |
| `connected_device` | `str or None` | Device ID (ADB serial or iOS UDID) |
| `device_platform` | `str or None` | `"android"` or `"ios"` |
| `target_app` | `str or None` | Package name (Android) or bundle ID (iOS) |
| `findings` | `list[dict]` | Reported vulnerabilities (see Finding model below) |
| `api_endpoints` | `list[dict]` | Discovered API endpoints (see APIEndpoint below) |
| `decompiled_paths` | `dict` | Paths to decompiled source: `{"apktool": "/path", "jadx": "/path"}` |
| `intercepted_traffic` | `list[dict]` | Captured HTTP flows |
| `notes` | `list[str]` | Agent's working notes (persist across iterations) |
| `todo_items` | `list[dict]` | Task tracking: `{"id": str, "item": str, "done": bool}` |
| `started_at` | `float or None` | Unix timestamp of agent start |
| `finished_at` | `float or None` | Unix timestamp of agent completion |

### AgentStatus Enum

| Value | Meaning |
|-------|---------|
| `IDLE` | Created but not yet started |
| `RUNNING` | Actively executing the agent loop |
| `WAITING` | Waiting for sub-agents or external input |
| `COMPLETED` | Successfully finished task |
| `FAILED` | Terminated due to errors |
| `TERMINATED` | Manually stopped |

### Key Methods to Implement

| Method | Behavior |
|--------|----------|
| `add_message(role, content, **kwargs)` | Append a message to conversation history with timestamp |
| `get_conversation_history()` | Return messages formatted for LLM consumption (filter to role in system/user/assistant/tool) |
| `add_finding(finding_dict)` | Append a finding, auto-tagging with `agent_id` and timestamp |
| `add_api_endpoint(endpoint_dict)` | Record discovered API endpoint |
| `record_tool_call(success: bool)` | Increment counters |
| `should_terminate()` | Returns `True` if `iteration_count >= max_iterations` or status is terminal |
| `to_summary()` | Returns a compact dict for graph display |

---

## 2. AgentNode (Graph Node)

Lightweight representation of an agent in the graph. Separate from `AgentState` to keep the graph view fast.

| Field | Type | Purpose |
|-------|------|---------|
| `agent_id` | `str` | Matches the `AgentState.agent_id` |
| `name` | `str` | Display name |
| `task` | `str` | Task description |
| `status` | `AgentStatus` | Current status |
| `parent_id` | `str or None` | Parent agent ID |
| `children` | `list[str]` | List of child agent IDs |
| `skills` | `list[str]` | Assigned skills |

---

## 3. AgentGraph

Global singleton managing the tree of all agents in a scan.

### Internal State

| Field | Type | Purpose |
|-------|------|---------|
| `nodes` | `dict[str, AgentNode]` | All agent nodes by ID |
| `edges` | `list[dict]` | Delegation and message links |
| `_agent_messages` | `dict[str, list[dict]]` | Per-agent message queues |
| `_agent_instances` | `dict[str, BaseAgent]` | Live agent object references |
| `_agent_states` | `dict[str, AgentState]` | State objects per agent |
| `_agent_tasks` | `dict[str, asyncio.Task]` | Running async tasks per agent |
| `_lock` | `asyncio.Lock` | Thread-safety for graph mutations |

### Operations (exposed as tools to the LLM)

| Operation | Who Can Call | What It Does |
|-----------|-------------|--------------|
| `create_agent(task, name, skills)` | Any agent | Spawns a child agent as an async task, adds node to graph, launches agent loop |
| `view_agent_graph()` | Any agent | Returns structured summary of all nodes, statuses, relationships |
| `send_message_to_agent(agent_id, message)` | Any agent | Posts a message to another agent's queue, injected into their conversation |
| `agent_finish(report)` | Sub-agents | Marks agent complete, forwards findings summary to parent |
| `finish_scan(summary)` | Root only | Waits for all children (with timeout), collects all findings, returns final report |

### Graph Enforcement Rules

- Tree structure only â€” no circular references
- Each `create_agent` call adds a parentâ†’child edge
- `agent_finish` reports upward to parent
- `finish_scan` blocks until children complete or timeout (30s per child)
- Graph view shows: total agents, active count, per-agent status/task/children

---

## 4. Finding (Vulnerability Report)

Produced by the `report_vulnerability` tool.

| Field | Type | Example |
|-------|------|---------|
| `id` | `str` | SHA256 hash of `title + category` (first 16 chars) â€” used for dedup |
| `title` | `str` | `"Hardcoded API Key in BuildConfig"` |
| `severity` | `str` | `"critical"`, `"high"`, `"medium"`, `"low"`, `"info"` |
| `category` | `str` | OWASP MASVS: `"MASVS-STORAGE"`, `"MASVS-CRYPTO"`, `"MASVS-AUTH"`, `"MASVS-NETWORK"`, `"MASVS-PLATFORM"`, `"MASVS-CODE"`, `"MASVS-RESILIENCE"` |
| `description` | `str` | Detailed vulnerability description |
| `poc` | `str` | Step-by-step proof of concept with actual commands/scripts |
| `impact` | `str` | What an attacker can achieve |
| `remediation` | `str` | How to fix the issue |
| `evidence` | `str` | Tool output, intercepted data (sanitized, max 2000 chars) |
| `agent_id` | `str` | Which agent discovered this |
| `agent_name` | `str` | Human-readable agent name |
| `timestamp` | `float` | Unix timestamp of discovery |

### Deduplication Logic

Before recording a finding, hash `title.lower().strip() + "|" + category.lower().strip()` using SHA256 and check against a global set. If already present, return `{"status": "duplicate"}`. This prevents multiple agents from reporting the same issue.

---

## 5. APIEndpoint

Produced by the `report_api_endpoint` tool.

| Field | Type | Example |
|-------|------|---------|
| `url` | `str` | `"https://api.target.com/v2/users/{id}/profile"` |
| `method` | `str` | `"GET"`, `"POST"`, `"PUT"`, `"DELETE"` |
| `auth_type` | `str` | `"bearer_jwt"`, `"api_key"`, `"oauth2"`, `"session_cookie"`, `"none"` |
| `parameters` | `str` | JSON string of params: `{"headers": {...}, "query": {...}, "body": {...}}` |
| `response_type` | `str` | `"application/json"`, `"text/html"`, etc. |
| `notes` | `str` | Agent observations: rate limiting, interesting behavior, etc. |
| `discovered_by` | `str` | Agent ID |
| `timestamp` | `float` | Unix timestamp |

---

## 6. LLMConfig

Configuration for the LLM client. Loaded from environment variables with fallback to `~/.maya/config.json`.

| Field | Source (env var) | Default | Purpose |
|-------|-----------------|---------|---------|
| `model` | `MAYA_LLM` | `"openai/gpt-4o"` | LiteLLM model string (provider/model format) |
| `api_key` | `LLM_API_KEY` | `None` | API key for the LLM provider |
| `api_base` | `LLM_API_BASE` | `None` | Custom API base URL (for Ollama, LM Studio, etc.) |
| `temperature` | â€” | `0.1` | Low temp for deterministic security analysis |
| `max_tokens` | â€” | `8192` | Max response tokens per LLM call |
| `max_retries` | â€” | `3` | Retry count for transient failures |
| `verbose` | â€” | `False` | Enable LiteLLM debug logging |
| `reasoning_effort` | `MAYA_REASONING_EFFORT` | `"high"` | `"low"`, `"medium"`, `"high"` â€” controls scan depth |

### Config Persistence

On first run, save config to `~/.maya/config.json` so users don't re-enter settings. Environment variables always override saved config.

---

## 7. LLMResponse

Returned by `LLMClient.generate()`.

| Field | Type | Purpose |
|-------|------|---------|
| `content` | `str or None` | The text response from the LLM |
| `tool_calls` | `list` | Native tool calls (if using function calling mode) |
| `usage` | `dict` | Token counts: `{"prompt_tokens": N, "completion_tokens": N}` |
| `model` | `str` | Actual model used |
| `finish_reason` | `str` | `"stop"`, `"length"`, `"tool_calls"` |

---

## 8. ToolInvocation (Parsed from LLM output)

When the LLM wants to use a tool, it emits XML in its response. The parser extracts:

| Field | Type | Example |
|-------|------|---------|
| `toolName` | `str` | `"frida_bypass_ssl_pinning"` |
| `args` | `dict[str, str]` | `{"package_name": "com.target.app"}` |

### XML Format

```xml
<function=frida_bypass_ssl_pinning>
<parameter=package_name>com.target.app</parameter>
</function>
```

The parser also handles the variant `<invoke name="X"><param name="Y">` format by normalizing it first.

---

## 9. ScanConfig

Top-level configuration for a scan session, created from CLI arguments.

| Field | Type | Purpose |
|-------|------|---------|
| `targets` | `list[dict]` | Each: `{"type": "local"|"github"|"device"|"url", "value": "..."}` |
| `device_id` | `str or None` | ADB serial or iOS UDID |
| `platform` | `str or None` | `"android"` or `"ios"` |
| `instruction` | `str` | Custom testing instructions from user |
| `instruction_file` | `str or None` | Path to instruction markdown file |
| `scan_mode` | `str` | `"quick"` (high-impact only), `"standard"`, `"comprehensive"` (deep) |
| `non_interactive` | `bool` | Headless mode (no TUI) |
| `output_dir` | `str` | Where to save results (default: `maya_runs/<run_name>`) |
| `max_agents` | `int` | Maximum concurrent sub-agents (default: 7) |

---

## 10. ToolRegistryEntry

Internal structure stored in the global `tools` list.

| Field | Type | Purpose |
|-------|------|---------|
| `name` | `str` | Tool function name |
| `function` | `Callable` | The actual Python function |
| `module` | `str` | Module group name (e.g., `"frida_tool"`, `"reporting"`) |
| `xml_schema` | `str` | Full XML schema string describing the tool for the LLM |
| `sandbox_execution` | `bool` | If `True`, forwarded to sandbox container; if `False`, runs locally |

### Supporting Registries

| Registry | Type | Purpose |
|----------|------|---------|
| `_tools_by_name` | `dict[str, Callable]` | Fast nameâ†’function lookup |
| `_tool_param_schemas` | `dict[str, dict]` | Per-tool `{"required": set, "params": set}` for validation |

---

## 11. SandboxInfo

Returned by `DockerRuntime.create_sandbox()`, stored in `AgentState.sandbox_info`.

| Field | Type | Example |
|-------|------|---------|
| `workspace_id` | `str` | Docker container ID (first 12 chars) |
| `server_url` | `str` | `"http://localhost:32789"` (mapped port) |
| `auth_token` | `str` | Bearer token for authenticating with tool_server |
| `agent_id` | `str` | The agent this sandbox belongs to |

---

## 12. Message Format (Conversation History)

Each message in `AgentState.messages`:

| Field | Type | Purpose |
|-------|------|---------|
| `role` | `str` | `"system"`, `"user"`, `"assistant"`, `"tool"` |
| `content` | `str` | Message text |
| `tool_name` | `str or None` | For tool messages, which tool produced this |
| `tool_call_id` | `str or None` | Correlation ID for native function calling |
| `images` | `list[dict]` | Base64-encoded screenshots from tools |
| `timestamp` | `float` | Unix timestamp |

### How Messages Map to the Agent Loop

1. `system` â€” Rendered system prompt (injected once at initialization)
2. `user` â€” The initial task + all tool observations (wrapped in `<tool_result>` tags)
3. `assistant` â€” LLM responses (may contain `<function=...>` tool invocations)
4. `user` â€” Inter-agent messages (wrapped in `<message from='agent_id'>` tags)

The `get_conversation_history()` method filters to only `role in (system, user, assistant)` and strips metadata before sending to the LLM.
