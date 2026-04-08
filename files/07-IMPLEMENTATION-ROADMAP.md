# Maya AI Agent â€” Implementation Roadmap

## Phase Overview

| Phase | Focus | Duration | Deliverable |
|-------|-------|----------|-------------|
| 1 | Core Framework | 2-3 weeks | Agent loop, LLM integration, tool system working end-to-end |
| 2 | Security Tools | 2-3 weeks | All tool modules implemented and tested in sandbox |
| 3 | Skills & Prompt | 1-2 weeks | System prompt polished, all skills authored, agent orchestration working |
| 4 | Docker Runtime | 1-2 weeks | Sandbox container image, tool_server, device networking |
| 5 | Companion App | 2-3 weeks | Android app with WebSocket server and all modules |
| 6 | CLI & Reporting | 1 week | CLI interface, report generation, headless mode |
| 7 | Testing & Polish | 1-2 weeks | Integration tests, edge cases, documentation |

---

## Phase 1: Core Framework

**Goal**: Get a single agent running the full Think â†’ Plan â†’ Act â†’ Observe loop with one simple tool.

### Step 1.1: Project Scaffold

- Initialize Python project with Poetry
- Set up directory structure as specified in `01-ARCHITECTURE.md`
- Add dependencies: `litellm`, `jinja2`, `pydantic`, `asyncio`, `aiohttp`, `httpx`, `defusedxml`, `docker`, `rich`, `click`, `pyyaml`
- Set up ruff linter and pytest

### Step 1.2: Data Models

Implement all models from `02-MODELS-AND-DATA-STRUCTURES.md`:
- `AgentState` dataclass with all fields and methods
- `AgentStatus` enum
- `LLMConfig` with env var loading and file persistence
- `LLMResponse` dataclass
- `ScanConfig` for CLI arguments

### Step 1.3: LLM Client

- Implement `LLMClient` wrapping `litellm.acompletion()`
- Handle retries with exponential backoff for `RateLimitError` and `APIConnectionError`
- Implement `generate()` and `generate_with_schema()`
- Test with a simple prompt to verify LiteLLM integration works

### Step 1.4: Tool Invocation Parser

- Implement `normalize_tool_format()` â€” regex substitution for variant XML formats
- Implement `parse_tool_invocations()` â€” two-level regex extraction
- Implement `truncate_result()` â€” first 4K + last 4K for long outputs
- Write unit tests with various XML formats including edge cases (multi-line values, nested tags, multiple tools per response)

### Step 1.5: Tool Registry

- Implement `@register_tool` decorator with `sandbox_execution` flag
- Implement XML schema loading from file + auto-generation from signature
- Implement parameter constraint parsing from XML
- Implement `get_tools_prompt()` â€” group by module, wrap in named XML tags
- Implement `should_execute_in_sandbox()`, `validate_tool_availability()`, `needs_agent_state()`

### Step 1.6: Tool Executor

- Implement `execute_tool()` with local/sandbox routing
- Implement `_execute_locally()` â€” call function, inject agent_state if needed
- For now, stub `_execute_in_sandbox()` to also run locally (Docker comes in Phase 4)
- Implement `process_tool_invocations()` â€” batch execution with termination signal detection
- Implement `_validate_tool_arguments()` â€” check required params, no unknowns

### Step 1.7: Base Agent

- Implement `BaseAgent` with `AgentMeta` metaclass and auto-registration
- Implement `initialize()` â€” build system prompt, add to messages
- Implement `agent_loop()` â€” the full iteration loop with error recovery
- Implement `_process_iteration()` â€” LLM call â†’ parse â†’ execute â†’ observe
- Implement `spawn_subagent()` â€” calls AgentGraph.create_agent()

### Step 1.8: Agent Graph

- Implement `AgentGraph` singleton with all operations
- Implement `create_agent()` â€” instantiate child, add to graph, launch async task
- Implement `view_graph()`, `send_message()`, `agent_finish()`, `finish_scan()`
- Enforce tree structure (each child has exactly one parent)

### Step 1.9: Smoke Test

Register ONE simple tool (e.g., `terminal_execute` that runs `echo`), create a basic system prompt, and verify the full loop works:

```
Agent starts â†’ LLM sees tools â†’ LLM calls terminal_execute â†’ Result observed â†’ LLM reasons â†’ Loop continues â†’ LLM calls agent_finish â†’ Loop ends
```

---

## Phase 2: Security Tools

**Goal**: Implement all tool modules from `03-TOOLS-IMPLEMENTATION-GUIDE.md`.

### Step 2.1: Terminal & File Tools

- `terminal_execute` â€” shell command execution with timeout
- `python_execute` â€” Python code execution
- `file_read`, `file_write` â€” filesystem operations
- `semgrep_scan` â€” Semgrep invocation
- `nuclei_scan` â€” Nuclei invocation

### Step 2.2: Frida Tools

- `frida_attach`, `frida_spawn` â€” process attachment
- `frida_run_script` â€” arbitrary script injection (most important tool)
- `frida_enumerate_classes` â€” class listing with filter
- `frida_hook_method` â€” specific method hooking
- `frida_bypass_ssl_pinning` â€” universal bypass script
- `frida_bypass_root_detection` â€” RootBeer + common checks bypass
- `frida_trace_crypto` â€” Cipher/SecretKeySpec/MessageDigest hooking

**Testing**: Use a vulnerable test app (DIVA, InsecureBankv2, OWASP MSTG apps) on a rooted emulator.

### Step 2.3: MobSF Tools

- `mobsf_upload_scan` â€” upload and scan via REST API
- `mobsf_get_results` â€” retrieve full scan results
- `mobsf_get_source_code` â€” view specific decompiled file
- `mobsf_search_code` â€” search through decompiled source

**Setup**: Run MobSF as a Docker container alongside the sandbox.

### Step 2.4: Objection Tools

- `objection_explore`, `objection_run_command`
- `objection_dump_keychain`, `objection_enum_storage`
- `objection_list_activities`

### Step 2.5: Reflutter Tools

- `reflutter_analyze`, `reflutter_patch_traffic`
- `reflutter_extract_dart_symbols`
- `flutter_frida_hooks`

### Step 2.6: APK/IPA RE Tools

- `apktool_decompile`, `jadx_decompile`
- `analyze_manifest`, `search_decompiled_code`
- `ios_class_dump`, `extract_strings`

### Step 2.7: Proxy Tools

- `proxy_start_intercept` â€” mitmproxy startup with modes
- `proxy_get_captured_traffic` â€” flow retrieval with filters
- `proxy_replay_request` â€” modified replay
- `proxy_export_api_schema` â€” OpenAPI/HAR export
- `api_fuzz_endpoint` â€” payload injection testing

### Step 2.8: Device Bridge Tools

- `device_list`, `device_install_app`, `device_uninstall_app`
- `device_pull_file`, `device_push_file`, `device_shell`
- `device_get_app_info`, `device_dump_app_data`
- `device_start_frida_server`
- `companion_app_command` â€” WebSocket command sender

### Step 2.9: Agent Management & Reporting Tools

- `create_agent`, `view_agent_graph`, `send_message_to_agent`
- `agent_finish`, `finish_scan`
- `report_vulnerability` (with dedup), `report_api_endpoint`
- `add_note`, `update_todo`, `thinking`

---

## Phase 3: Skills & System Prompt

**Goal**: Author the system prompt template and all skill files. This is the most important phase for agent quality.

### Step 3.1: System Prompt Template

Write the Jinja2 template following the structure in `04-AGENT-SYSTEM-AND-LLM-INTEGRATION.md`:
- `<identity>` block
- `<methodology>` block (OWASP MASTG steps)
- `<root_agent_instructions>` conditional block
- `<targets>`, `<device_capabilities>`, `<agent_graph_rules>`
- `<tools>` injection point
- `<tool_usage_guidelines>` â€” critical for tool selection priority
- `<finding_format>` â€” structured reporting format
- `<thinking_process>` â€” before/after checklist
- `<specialized_knowledge>` â€” skill injection loop

### Step 3.2: Core Skills

Author the 6 minimum viable skills listed in `05-SKILLS-RUNTIME-COMPANION-APP.md`:
1. `insecure_storage.md`
2. `ssl_pinning_bypass.md`
3. `api_security.md`
4. `auth_bypass.md`
5. `insecure_crypto.md`
6. `flutter_analysis.md`

Each skill should be 100-300 lines covering discovery, exploitation, severity, and remediation with concrete Frida scripts and shell commands.

### Step 3.3: Additional Skills

Author remaining skills as needed:
- `ipc_vulnerabilities.md`, `webview_attacks.md`, `code_tampering.md`
- `binary_protections.md`, `data_leakage.md`
- `react_native_analysis.md`, `xamarin_analysis.md`
- `android_internals.md`, `ios_internals.md`
- `root_strategy.md` (for root agent coordination)

### Step 3.4: Prompt Testing

Test the system prompt with various scenarios:
- Does the root agent correctly delegate to sub-agents?
- Do sub-agents use the right tools for their skills?
- Does the LLM follow the methodology in order?
- Are findings reported in the correct format?
- Does inter-agent communication work?

**Iterate heavily on the prompt** â€” this is the highest-ROI activity.

---

## Phase 4: Docker Runtime

### Step 4.1: Sandbox Dockerfile

Build `containers/Dockerfile.sandbox` with all security tools installed. See the complete list in `05-SKILLS-RUNTIME-COMPANION-APP.md`.

### Step 4.2: Tool Server

Implement the FastAPI tool_server that runs inside the container:
- `/health` endpoint
- `/register_agent` endpoint
- `/execute` endpoint with dispatch routing
- Handlers for: terminal, python, frida, proxy, file operations

### Step 4.3: DockerRuntime Class

- `create_sandbox()` â€” run container, wait for health, register agent
- `destroy_sandbox()` â€” stop container
- `destroy_all()` â€” cleanup at scan end
- Handle port mapping, volume mounts, capabilities (SYS_PTRACE)

### Step 4.4: Device Networking

Configure container networking so the sandbox can reach the device:
- Host network mode (`--network=host`) for USB-connected devices
- Bridge + port forwarding for WiFi-connected devices
- ADB server forwarding (`adb forward tcp:27042 tcp:27042` for Frida)

---

## Phase 5: Companion App

### Step 5.1: Android App

Build a Kotlin Android app with:
- WebSocket server on port 9999 (Ktor)
- Command router dispatching to handler modules
- Root shell execution via `su -c`
- All modules: AppManager, FridaGadgetInjector, TrafficCapture, FilesystemInspector, LogCollector, ExploitRunner, ScreenshotCapture

### Step 5.2: iOS App (if targeting iOS)

Build a Swift app or jailbreak tweak with equivalent capabilities:
- WebSocket server
- Keychain dumping
- Filesystem access
- SSH-based operations

### Step 5.3: Integration with `companion_app_command` Tool

Wire the `companion_app_command` tool to actually connect via WebSocket, send commands, and return results. The tool_server in the sandbox makes the WebSocket connection to the device.

---

## Phase 6: CLI & Reporting

### Step 6.1: CLI Entry Point

Build the main CLI using Click:

```
maya --target ./app.apk --device <id> --platform android
maya --target com.target.app --device <id> --instruction "Focus on auth bypass"
maya -t ./app.apk -t https://api.target.com --scan-mode comprehensive
maya -n --target ./app.apk  # headless mode
```

### Step 6.2: TUI Mode (Optional)

Using Textual/Rich, build an interactive terminal UI showing:
- Agent graph with real-time status updates
- Current tool being executed per agent
- Findings panel with severity colors
- Log output

### Step 6.3: Report Generation

- Generate `findings.json`, `api_endpoints.json`
- Generate `report.md` and `report.html`
- Exit with non-zero code if critical/high findings (for CI/CD)

---

## Phase 7: Testing & Polish

### Integration Tests

- Full scan against DIVA (Android vulnerable app)
- Full scan against InsecureBankv2
- Full scan against OWASP MSTG test apps
- Multi-agent coordination test
- Flutter app analysis test (using a test Flutter app)

### Edge Cases

- Device disconnects mid-scan
- LLM rate limiting during scan
- Tool timeout handling
- Container crash recovery
- Very large APKs (>100MB)
- Obfuscated apps (ProGuard, R8)

### Documentation

- README.md with quick start
- Contributing guide
- Skill authoring guide
- Custom tool development guide

---

## Minimum Viable Product (MVP) Checklist

For the first working version, you need these components:

- [ ] `AgentState` and `AgentStatus`
- [ ] `LLMClient` with LiteLLM
- [ ] `parse_tool_invocations()` and `normalize_tool_format()`
- [ ] `@register_tool` decorator and registry
- [ ] `execute_tool()` with local execution (skip Docker initially)
- [ ] `BaseAgent` with agent loop
- [ ] `MayaAgent` with Jinja2 system prompt
- [ ] `AgentGraph` with create_agent, agent_finish, finish_scan
- [ ] Tools: `terminal_execute`, `frida_run_script`, `frida_bypass_ssl_pinning`, `device_shell`
- [ ] Tools: `report_vulnerability`, `create_agent`, `agent_finish`, `finish_scan`, `thinking`
- [ ] Skills: `ssl_pinning_bypass`, `api_security` (just 2 to start)
- [ ] Basic CLI entry point
- [ ] Test against one vulnerable app on a rooted emulator

Everything else â€” Docker sandbox, companion app, TUI, full skill library â€” can be layered on after the core loop is working.
