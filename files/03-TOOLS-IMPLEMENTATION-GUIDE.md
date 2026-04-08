# Maya AI Agent â€” Tools Implementation Guide

## 1. Tool System Overview

Tools are the hands of the agent. Every action the agent takes â€” running a command, hooking a function, scanning code â€” goes through the tool system. This design means the agent's capabilities are entirely defined by what tools are registered, and new capabilities can be added without touching agent logic.

### How It Works End-to-End

1. **Registration**: A Python function decorated with `@register_tool` gets added to the global registry along with its XML schema.
2. **Prompt Injection**: `get_tools_prompt()` aggregates all XML schemas into the system prompt so the LLM knows what tools are available and how to call them.
3. **LLM Output**: The LLM emits tool calls in XML format within its text response.
4. **Parsing**: `parse_tool_invocations()` extracts `{"toolName": ..., "args": {...}}` dicts from the response.
5. **Validation**: Check tool exists, required params present, no unknown params.
6. **Routing**: `should_execute_in_sandbox(tool_name)` decides local vs. container execution.
7. **Execution**: Local tools call the function directly; sandbox tools send HTTP POST to the container's `tool_server`.
8. **Result**: Output is formatted, truncated if too long (first 4K + last 4K chars), and appended to conversation as an observation.

---

## 2. The `@register_tool` Decorator

### How to Implement

Create a decorator that does the following when applied to a function:

1. Derive the tool name from `function.__name__`
2. Look for an XML schema file at `tools/<module_folder>/<file_stem>_schema.xml`
3. If no schema file exists, auto-generate one from the function signature using `inspect.signature()`
4. Parse parameter constraints (required/optional) from the schema
5. Store everything in three global structures:
   - `tools: list[dict]` â€” full metadata including schema and sandbox flag
   - `_tools_by_name: dict[str, Callable]` â€” fast lookup
   - `_tool_param_schemas: dict[str, dict]` â€” validation constraints

### The `sandbox_execution` Flag

- `@register_tool` (default `sandbox_execution=True`) â€” tool runs inside the Docker container
- `@register_tool(sandbox_execution=False)` â€” tool runs locally on the host (used for agent graph operations, reporting, thinking)

---

## 3. XML Schema Format

Each tool needs an XML schema that tells the LLM what it does, what parameters it accepts, and which are required. This is what gets injected into the system prompt.

### Schema Structure

```xml
<tool name="frida_bypass_ssl_pinning">
  <description>
    Bypass SSL certificate pinning using universal Frida scripts.
    Covers: TrustManager, OkHttp, custom implementations, network_security_config.
    Run this BEFORE starting traffic interception.
  </description>
  <parameters>
    <parameter name="package_name" type="string" required="true">
      The package name of the target app (e.g., com.example.app)
    </parameter>
  </parameters>
</tool>
```

### Dynamic Content Placeholder

Schema files can contain `{{DYNAMIC_SKILLS_DESCRIPTION}}` which gets replaced at load time with the output of `generate_skills_description()`. This is used by the `create_agent` tool's schema to list all available skills so the LLM knows what specializations it can assign to sub-agents.

### Auto-Generated Schemas

If no XML file exists, generate the schema from the function's docstring and signature. The docstring becomes the `<description>`, and each parameter (excluding `agent_state`, `self`, `kwargs`) becomes a `<parameter>` element. Parameters with no default are marked `required="true"`.

---

## 4. Tool Invocation XML Format

The LLM emits tool calls in this format (teach this in the system prompt):

```xml
<function=tool_name>
<parameter=param_name>value</parameter>
<parameter=another_param>multi-line
value here</parameter>
</function>
```

### Variant Format (also handle)

```xml
<invoke name="tool_name">
<param name="param_name">value</param>
</invoke>
```

### Parser Implementation

1. **Normalize** â€” Convert `<invoke name="X">` â†’ `<function=X>` and `<param name="Y">` â†’ `<parameter=Y>` using regex substitution
2. **Extract** â€” Use regex `<function=(\w+)>(.*?)</function>` with `re.DOTALL` to find all tool blocks
3. **Parse params** â€” Within each block, use regex `<parameter=(\w+)>(.*?)</parameter>` with `re.DOTALL`
4. **Return** â€” List of `{"toolName": str, "args": dict[str, str]}`

### Result Formatting

Tool results are wrapped in XML and appended to conversation as a `"user"` message:

```xml
<tool_result tool='frida_bypass_ssl_pinning'>
{"status": "ssl_pinning_bypassed", "methods": ["TrustManager", "OkHttp3", "WebView"]}
</tool_result>
```

Results over 10,000 characters are truncated: first 4,000 + `[truncated N chars]` + last 4,000.

---

## 5. Tool Execution Routing

### Local Execution (`sandbox_execution=False`)

1. Get function from `_tools_by_name`
2. Check if function signature includes `agent_state` parameter â€” if yes, inject it
3. Call the function (support both sync and async functions)
4. Return result

### Sandbox Execution (`sandbox_execution=True`)

1. Get `server_url` and `auth_token` from `agent_state.sandbox_info`
2. Send HTTP POST to `{server_url}/execute`:
   ```json
   {
     "agent_id": "abc12345",
     "tool_name": "terminal_execute",
     "kwargs": {"command": "nmap -sV target.com", "timeout": "60"}
   }
   ```
3. Include `Authorization: Bearer {token}` header
4. Timeout: configurable via `MAYA_SANDBOX_TIMEOUT` env var (default 120s + 30s buffer)
5. Parse response: `{"result": ..., "error": null}` or `{"result": null, "error": "..."}`

### Validation (runs before execution)

1. **Availability check**: Confirm tool name exists in `_tools_by_name`
2. **Argument check**: No unknown parameters, all required parameters present and non-empty
3. Validation errors are returned as formatted strings (not exceptions) so the LLM sees them as observations and can self-correct

---

## 6. Complete Tool Inventory

### Category: Frida Instrumentation (`frida_tool/`)

| Tool | Sandbox | Purpose |
|------|---------|---------|
| `frida_attach` | Yes | Attach to a running app process |
| `frida_spawn` | Yes | Spawn app with Frida from the start |
| `frida_run_script` | Yes | Inject and execute arbitrary Frida JS script |
| `frida_enumerate_classes` | Yes | List all loaded classes, optionally filtered |
| `frida_hook_method` | Yes | Hook a specific class.method to log args/return |
| `frida_bypass_ssl_pinning` | Yes | Universal SSL pinning bypass (TrustManager, OkHttp, WebView) |
| `frida_bypass_root_detection` | Yes | Bypass RootBeer, su checks, Build.TAGS |
| `frida_trace_crypto` | Yes | Hook Cipher, SecretKeySpec, MessageDigest to extract keys and plaintext |

#### Key Implementation Detail for Frida Tools

Each Frida tool should generate a self-contained JavaScript script string. The tool_server in the sandbox will:
1. Write the script to a temp file
2. Execute `frida -U -n <package> -l <script_path> --no-pause -q`
3. Capture stdout (which includes `send()` messages from the script)
4. Return the output

For `frida_run_script`, the agent provides the script directly â€” this is the most powerful tool because the LLM can write custom Frida scripts for novel situations.

### Category: MobSF Static Analysis (`mobsf_tool/`)

| Tool | Sandbox | Purpose |
|------|---------|---------|
| `mobsf_upload_scan` | Yes | Upload APK/IPA and trigger full static scan |
| `mobsf_get_results` | Yes | Retrieve scan results (permissions, secrets, manifest analysis, etc.) |
| `mobsf_get_source_code` | Yes | View decompiled source for a specific file |
| `mobsf_search_code` | Yes | Search through decompiled code |

#### Implementation Notes

MobSF runs as a separate container. Tools interact via the MobSF REST API (`/api/v1/upload`, `/api/v1/scan`, `/api/v1/report_json`). The MobSF API key should be configured via environment variable `MOBSF_API_KEY`.

### Category: Objection Runtime Exploration (`objection_tool/`)

| Tool | Sandbox | Purpose |
|------|---------|---------|
| `objection_explore` | Yes | Start exploration session, list available commands |
| `objection_run_command` | Yes | Execute a specific Objection command |
| `objection_dump_keychain` | Yes | Dump Keychain (iOS) or KeyStore (Android) entries |
| `objection_enum_storage` | Yes | Enumerate local storage: SharedPrefs, SQLite, files, cache |
| `objection_list_activities` | Yes | List activities, services, receivers, providers |

### Category: Reflutter â€” Flutter RE (`reflutter_tool/`)

| Tool | Sandbox | Purpose |
|------|---------|---------|
| `reflutter_analyze` | Yes | Detect Flutter, extract version, prepare for patching |
| `reflutter_patch_traffic` | Yes | Patch libflutter.so to route traffic through proxy |
| `reflutter_extract_dart_symbols` | Yes | Extract class/method names from Dart AOT snapshot |
| `flutter_frida_hooks` | Yes | Inject Flutter-specific Frida hooks (BoringSSL level, not Java) |

### Category: APK/IPA Reverse Engineering (`apk_tool/`)

| Tool | Sandbox | Purpose |
|------|---------|---------|
| `apktool_decompile` | Yes | Decompile APK to smali + resources |
| `jadx_decompile` | Yes | Decompile APK to Java source |
| `analyze_manifest` | Yes | Deep analysis of AndroidManifest.xml |
| `search_decompiled_code` | Yes | Grep through decompiled source |
| `ios_class_dump` | Yes | Extract ObjC headers from iOS binary |
| `extract_strings` | Yes | Extract readable strings from binary |

### Category: Traffic Interception (`proxy_tool/`)

| Tool | Sandbox | Purpose |
|------|---------|---------|
| `proxy_start_intercept` | Yes | Start mitmproxy (regular, transparent, or upstream mode) |
| `proxy_get_captured_traffic` | Yes | Retrieve flows, filtered by host/path/method |
| `proxy_replay_request` | Yes | Replay a captured request with modifications |
| `proxy_export_api_schema` | Yes | Export discovered endpoints as OpenAPI/HAR |
| `api_fuzz_endpoint` | Yes | Fuzz endpoint with SQLi, XSS, path traversal, SSRF payloads |

### Category: Device Bridge (`device_bridge/`)

| Tool | Sandbox | Purpose |
|------|---------|---------|
| `device_list` | Yes | List all connected Android/iOS devices |
| `device_install_app` | Yes | Install APK/IPA on device |
| `device_uninstall_app` | Yes | Remove app from device |
| `device_pull_file` | Yes | Pull file from device to sandbox |
| `device_push_file` | Yes | Push file from sandbox to device |
| `device_shell` | Yes | Execute shell command on device (as root) |
| `device_get_app_info` | Yes | Package info, permissions, signatures, data dir |
| `device_dump_app_data` | Yes | Extract all app data (SharedPrefs, DBs, files, cache) |
| `device_start_frida_server` | Yes | Ensure frida-server is running on device |
| `companion_app_command` | Yes | Send command to companion testing app via WebSocket |

### Category: Shell & Code Execution (`terminal/`)

| Tool | Sandbox | Purpose |
|------|---------|---------|
| `terminal_execute` | Yes | Execute shell command in sandbox |
| `python_execute` | Yes | Execute Python code in persistent IPython session |
| `file_read` | Yes | Read file contents |
| `file_write` | Yes | Write content to file |
| `semgrep_scan` | Yes | Run Semgrep static analysis on source code |
| `nuclei_scan` | Yes | Run Nuclei vulnerability scanner against URLs |

### Category: Agent Management (`agents_graph/`)

| Tool | Sandbox | Purpose |
|------|---------|---------|
| `create_agent` | **No (local)** | Spawn a sub-agent with task + skills |
| `view_agent_graph` | **No (local)** | View all agents, statuses, relationships |
| `send_message_to_agent` | **No (local)** | Inter-agent communication |
| `agent_finish` | **No (local)** | Mark agent done, report to parent |
| `finish_scan` | **No (local)** | Root-only: conclude entire scan |

### Category: Reporting & Context (`reporting/`)

| Tool | Sandbox | Purpose |
|------|---------|---------|
| `report_vulnerability` | **No (local)** | Report a finding with deduplication |
| `report_api_endpoint` | **No (local)** | Record discovered API endpoint |
| `add_note` | **No (local)** | Add working note to agent context |
| `update_todo` | **No (local)** | Manage testing task list (add/complete/list/remove) |
| `thinking` | **No (local)** | Record reasoning (no side effects, helps the LLM plan) |

---

## 7. Adding a New Tool â€” Checklist

1. **Create the function** in the appropriate module under `tools/<category>/`
2. **Decorate** with `@register_tool` (or `@register_tool(sandbox_execution=False)` for local)
3. **Include `agent_state: Optional[AgentState] = None`** parameter if the tool needs access to device info, findings, or notes
4. **Write the XML schema** file (or rely on auto-generation from the docstring/signature)
5. **Import the module** in `tools/__init__.py` so the decorator fires at startup
6. **If sandbox tool**: implement the handler in `tool_server.py`'s `_dispatch_tool` routing
7. **Test**: write a unit test that calls the tool directly and verifies output format

---

## 8. Tool Prompt Assembly

`get_tools_prompt()` groups all registered tools by module and wraps them in named XML blocks:

```xml
<frida_tool_tools>
  <tool name="frida_attach">...</tool>
  <tool name="frida_spawn">...</tool>
  ...
</frida_tool_tools>
<mobsf_tool_tools>
  <tool name="mobsf_upload_scan">...</tool>
  ...
</mobsf_tool_tools>
<agents_graph_tools>
  <tool name="create_agent">...</tool>
  ...
</agents_graph_tools>
```

This entire block is inserted into the system prompt via the Jinja2 template's `{{ tools_prompt }}` variable.
