# Maya AI Agent â€” Master Architecture Document

## 1. Project Overview

Maya AI Agent is an autonomous AI-powered mobile application security testing platform. It uses a multi-agent graph architecture (inspired by Strix) to coordinate static analysis, dynamic instrumentation, traffic interception, API reverse engineering, and exploit validation against real rooted/jailbroken mobile devices.

The system integrates with LiteLLM for provider-agnostic LLM access, uses Frida/Objection/Reflutter for runtime instrumentation, MobSF for static scanning, and deploys a companion app on test devices to receive and execute commands from the agent system.

---

## 2. Core Design Principles (Learned from Strix)

### 2.1 The Agent Loop: Think â†’ Plan â†’ Act â†’ Observe

Every agent in the system runs the same cognitive loop. This is the foundational pattern from Strix and is what makes the system autonomous rather than scripted.

1. **Think** â€” The LLM receives the full conversation history (system prompt + messages + tool observations) and reasons about the current state.
2. **Plan** â€” The LLM decides which tool(s) to call next and formulates the parameters.
3. **Act** â€” The system parses tool invocations from the LLM response, validates arguments, and routes execution to either the local host or the Docker sandbox.
4. **Observe** â€” Tool results are appended to the conversation history as observations, and the loop repeats.

The loop terminates when the agent calls `agent_finish` (sub-agent) or `finish_scan` (root agent), or hits the max iteration limit.

### 2.2 Everything Is a Tool

Agents don't "know how" to run Frida or decompile an APK. Instead, they have access to tools described in XML schemas injected into the system prompt. The LLM decides which tool to call based on its task and observations. This means:

- Adding a new capability = registering a new tool (no agent code changes)
- The LLM self-corrects when a tool fails (it sees the error as an observation)
- Tools are composable â€” the LLM can chain tools in creative ways

### 2.3 Skills = Injected Domain Knowledge

Skills are markdown files loaded into the system prompt. They encode:

- Vulnerability discovery techniques and tool usage
- Exploitation methodology and payloads
- Bypass techniques for specific protections
- Validation approaches and severity criteria

When a sub-agent is spawned with skills like `["ssl_pinning_bypass", "api_security"]`, those skill files are loaded and injected verbatim into the agent's system prompt inside `<specialized_knowledge>` XML blocks.

### 2.4 Multi-Agent Tree Graph

The agent graph is a strict tree. The root orchestrator spawns specialized sub-agents, each focused on a specific testing domain. Sub-agents can spawn their own children for further specialization. Key rules:

- Each agent has exactly one parent
- Child tasks must directly support the parent's goal
- Agents communicate via inter-agent messages
- Findings are reported up the tree and deduplicated globally

### 2.5 Sandboxed Tool Execution

All security tools run inside isolated Docker containers. The host process never executes nmap, Frida scripts, or shell commands directly. Instead:

- A `tool_server` (FastAPI) runs inside each container
- The host sends tool execution requests via HTTP POST
- The container executes and returns results
- This isolates dangerous operations and allows parallel agent execution

---

## 3. System Architecture Layers

```
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚                     CLI / TUI Interface                       â”‚
â”‚  (click + textual/rich for interactive mode, or headless)     â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚                    Root Orchestrator Agent                     â”‚
â”‚  (Plans assessment, spawns sub-agents, aggregates findings)   â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚ Static   â”‚  Dynamic     â”‚  API Disc.   â”‚ Platform-specific   â”‚
â”‚ Analysis â”‚  Testing     â”‚  Agent       â”‚ agents (Flutter,    â”‚
â”‚ Agent    â”‚  Agent       â”‚              â”‚ RN, etc.)           â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”´â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”´â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”´â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚                     Tool System                               â”‚
â”‚  @register_tool decorator â†’ XML schema â†’ registry â†’ executor  â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚                    LLM Integration (LiteLLM)                  â”‚
â”‚  Any provider: OpenAI, Anthropic, Google, local/Ollama        â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚                    Docker Sandbox Runtime                      â”‚
â”‚  Kali container + tool_server + pre-installed security tools  â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚                    Device Bridge Layer                         â”‚
â”‚  ADB (Android) / idevice+SSH (iOS) / USB / WiFi              â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚              Rooted Android / Jailbroken iOS                  â”‚
â”‚  frida-server + companion app + target application            â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

---

## 4. Data Flow â€” A Complete Scan

1. User runs: `maya --target ./app.apk --device <device_id> --platform android`
2. CLI parses arguments, creates `ScanConfig`, initializes the Docker runtime
3. Root `MayaAgent` is created with the scan task
4. System prompt is rendered from Jinja2 template with tools + skills
5. Root agent enters the agent loop:
   - Analyzes the target (APK file + live device)
   - Decides to spawn sub-agents for parallel work
   - Calls `create_agent` tool to spawn: static_analyzer, dynamic_tester, api_discoverer
6. Each sub-agent gets its own sandbox container and agent loop
7. Static agent: decompiles APK â†’ runs MobSF â†’ searches code â†’ reports findings
8. Dynamic agent: attaches Frida â†’ bypasses SSL â†’ hooks auth â†’ traces crypto â†’ reports
9. API agent: starts mitmproxy â†’ maps endpoints â†’ fuzzes parameters â†’ reports
10. Sub-agents finish and report back to root via `agent_finish`
11. Root agent aggregates, deduplicates, assesses risk, calls `finish_scan`
12. CLI generates the final report and exits

---

## 5. Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| LiteLLM over direct API calls | Provider-agnostic; switch models without code changes; supports 100+ providers |
| XML tool invocation format (not JSON) | Strix pattern; more reliable for streaming; LLMs handle XML well in system prompts |
| Docker sandbox per agent | Isolation; parallel execution; reproducibility; security |
| Skills as markdown files | Easy to author; version-controlled; injected verbatim into prompts; no code needed |
| Tree graph (not DAG) | Simpler coordination; clear ownership; prevents circular dependencies |
| Companion app on device | Some operations need to run ON the device; WebSocket allows real-time bidirectional control |
| Frida for dynamic analysis | Industry standard; supports both Android and iOS; JavaScript scripting; huge community |
| Deduplication via content hash | Prevents the same finding from being reported by multiple agents |

---

## 6. Directory Structure

```
maya-agent/
â”œâ”€â”€ pyproject.toml              # Poetry project config
â”œâ”€â”€ Makefile                    # Build, test, docker targets
â”œâ”€â”€ README.md
â”œâ”€â”€ maya/
â”‚   â”œâ”€â”€ main.py                 # CLI entry point
â”‚   â”œâ”€â”€ agents/
â”‚   â”‚   â”œâ”€â”€ base_agent.py       # BaseAgent + AgentMeta metaclass
â”‚   â”‚   â”œâ”€â”€ state.py            # AgentState dataclass
â”‚   â”‚   â”œâ”€â”€ graph.py            # AgentGraph singleton + operations
â”‚   â”‚   â””â”€â”€ MayaAgent/
â”‚   â”‚       â”œâ”€â”€ __init__.py     # MayaAgent class
â”‚   â”‚       â””â”€â”€ system_prompt.jinja  # Jinja2 prompt template
â”‚   â”œâ”€â”€ llm/
â”‚   â”‚   â”œâ”€â”€ llm.py              # LLMClient (wraps LiteLLM)
â”‚   â”‚   â”œâ”€â”€ config.py           # LLMConfig from env/file
â”‚   â”‚   â”œâ”€â”€ utils.py            # XML tool invocation parser
â”‚   â”‚   â””â”€â”€ memory_compressor.py # Conversation summarization
â”‚   â”œâ”€â”€ runtime/
â”‚   â”‚   â”œâ”€â”€ docker_runtime.py   # DockerRuntime container management
â”‚   â”‚   â””â”€â”€ tool_server.py      # FastAPI server (inside container)
â”‚   â”œâ”€â”€ tools/
â”‚   â”‚   â”œâ”€â”€ __init__.py         # Conditional tool loading
â”‚   â”‚   â”œâ”€â”€ registry.py         # @register_tool + schema system
â”‚   â”‚   â”œâ”€â”€ executor.py         # Validation + routing + execution
â”‚   â”‚   â”œâ”€â”€ frida_tool/         # Frida instrumentation tools
â”‚   â”‚   â”œâ”€â”€ mobsf_tool/         # MobSF static analysis tools
â”‚   â”‚   â”œâ”€â”€ objection_tool/     # Objection exploration tools
â”‚   â”‚   â”œâ”€â”€ reflutter_tool/     # Flutter-specific RE tools
â”‚   â”‚   â”œâ”€â”€ apk_tool/           # APKTool, JADX, class-dump
â”‚   â”‚   â”œâ”€â”€ proxy_tool/         # mitmproxy interception tools
â”‚   â”‚   â”œâ”€â”€ device_bridge/      # ADB, idevice, companion app
â”‚   â”‚   â”œâ”€â”€ terminal/           # Shell + Python execution
â”‚   â”‚   â”œâ”€â”€ agents_graph/       # Agent management tools
â”‚   â”‚   â””â”€â”€ reporting/          # Finding reports, notes, todos
â”‚   â”œâ”€â”€ skills/
â”‚   â”‚   â”œâ”€â”€ __init__.py         # Skill loading system
â”‚   â”‚   â”œâ”€â”€ vulnerabilities/    # OWASP Mobile Top 10 skills
â”‚   â”‚   â”œâ”€â”€ frameworks/         # Flutter, RN, Xamarin skills
â”‚   â”‚   â””â”€â”€ platforms/          # Android/iOS specific skills
â”‚   â””â”€â”€ telemetry/
â”‚       â””â”€â”€ tracer.py           # Scan tracing and report persistence
â”œâ”€â”€ companion_app/
â”‚   â”œâ”€â”€ android/                # Android companion app source
â”‚   â””â”€â”€ ios/                    # iOS companion app source
â”œâ”€â”€ containers/
â”‚   â””â”€â”€ Dockerfile.sandbox      # Kali-based sandbox image
â”œâ”€â”€ scripts/
â”‚   â””â”€â”€ install.sh              # Installer script
â””â”€â”€ tests/
    â”œâ”€â”€ test_agent_loop.py
    â”œâ”€â”€ test_tool_registry.py
    â””â”€â”€ test_skills.py
```
