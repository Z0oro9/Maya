# Maya AI Agent â€” Skills, Runtime & Companion App

## 1. Skills System

### Purpose

Skills are the agent's domain knowledge. They are markdown files injected verbatim into the system prompt. Without skills, the agent knows it has Frida and mitmproxy but doesn't know HOW to use them for specific vulnerability classes. Skills encode the "how" â€” the specific techniques, scripts, commands, and patterns a human pentester would know.

### Directory Layout

```
maya/skills/
â”œâ”€â”€ __init__.py                  # Loading, validation, description generation
â”œâ”€â”€ vulnerabilities/
â”‚   â”œâ”€â”€ insecure_storage.md      # MASVS-STORAGE
â”‚   â”œâ”€â”€ insecure_crypto.md       # MASVS-CRYPTO
â”‚   â”œâ”€â”€ ssl_pinning_bypass.md    # MASVS-NETWORK (pinning)
â”‚   â”œâ”€â”€ api_security.md          # MASVS-NETWORK (API)
â”‚   â”œâ”€â”€ auth_bypass.md           # MASVS-AUTH
â”‚   â”œâ”€â”€ ipc_vulnerabilities.md   # MASVS-PLATFORM (intents, deeplinks, URL schemes)
â”‚   â”œâ”€â”€ webview_attacks.md       # MASVS-PLATFORM (WebView misconfig)
â”‚   â”œâ”€â”€ code_tampering.md        # MASVS-RESILIENCE (anti-debug, anti-tamper)
â”‚   â”œâ”€â”€ binary_protections.md    # MASVS-CODE (obfuscation, binary hardening)
â”‚   â””â”€â”€ data_leakage.md          # Logging, clipboard, backup, screenshots
â”œâ”€â”€ frameworks/
â”‚   â”œâ”€â”€ flutter_analysis.md      # Flutter/Dart-specific techniques
â”‚   â”œâ”€â”€ react_native_analysis.md # React Native (Hermes, JSC) techniques
â”‚   â”œâ”€â”€ xamarin_analysis.md      # Xamarin/.NET techniques
â”‚   â””â”€â”€ cordova_analysis.md      # Cordova/Ionic WebView-based apps
â”œâ”€â”€ platforms/
â”‚   â”œâ”€â”€ android_internals.md     # Android-specific: SELinux, Binder, Content Providers
â”‚   â””â”€â”€ ios_internals.md         # iOS-specific: Keychain, entitlements, App Transport Security
â”œâ”€â”€ scan_modes/                  # (excluded from create_agent listing)
â”‚   â”œâ”€â”€ quick.md                 # Quick scan methodology
â”‚   â”œâ”€â”€ standard.md              # Standard scan methodology
â”‚   â””â”€â”€ comprehensive.md         # Deep comprehensive methodology
â””â”€â”€ coordination/                # (excluded from create_agent listing)
    â””â”€â”€ root_strategy.md         # Root agent orchestration guidance
```

### Skill File Format

Every skill markdown file starts with YAML frontmatter:

```yaml
---
name: insecure_storage
description: "Detection and exploitation of insecure local data storage in mobile apps"
category: vulnerabilities
---
```

After the frontmatter delimiter, the rest is freeform markdown that covers:

1. **Discovery Techniques** â€” What to look for, what commands/tools to use, specific file paths and patterns per platform
2. **Exploitation Methodology** â€” Step-by-step exploitation, including Frida scripts, shell commands, and analysis procedures
3. **Severity Assessment** â€” How to rate findings for this vulnerability class
4. **Remediation** â€” What the developer should do to fix it

### Key Functions to Implement in `skills/__init__.py`

| Function | Behavior |
|----------|----------|
| `get_available_skills()` | Walk the skills directory, return `{category: [skill_name, ...]}`. Exclude `scan_modes/` and `coordination/` directories. |
| `get_all_skill_names()` | Flat set of all skill names across categories. |
| `validate_skill_names(names)` | Returns `(valid_list, invalid_list)`. |
| `load_skills(skill_names)` | Read each `.md` file, strip YAML frontmatter, return `{name: content}`. |
| `_find_skill_path(name)` | Search all category dirs for `name.md`. Support `category/name` explicit path. |
| `_strip_frontmatter(content)` | Remove `---` delimited YAML block from top of file. |
| `generate_skills_description()` | Format available skills with descriptions for the `create_agent` tool schema. |

### Skills You Should Create

For a minimum viable system, create these 6 skills:

1. **`insecure_storage`** â€” SharedPreferences/Keychain/SQLite inspection, file permission checks, backup extraction, Frida file-write hooks
2. **`ssl_pinning_bypass`** â€” Universal Frida bypass script, Objection method, Reflutter patching, iOS-specific bypass, verification procedure
3. **`api_security`** â€” Static URL discovery, dynamic traffic mapping, IDOR/auth-bypass/mass-assignment/injection testing methodology
4. **`auth_bypass`** â€” Biometric bypass, PIN bypass, JWT attacks, OAuth misconfig, session management testing
5. **`insecure_crypto`** â€” Weak algorithm detection, hardcoded key patterns, Frida crypto tracing, ECB/static-IV detection
6. **`flutter_analysis`** â€” Detection, libflutter.so patching, Dart symbol extraction, BoringSSL-level hooking

---

## 2. Docker Sandbox Runtime

### Container Image

Build a custom image based on Kali Linux with all security tools pre-installed. Store as `containers/Dockerfile.sandbox`.

#### What to Include in the Image

**Base**: `kalilinux/kali-rolling`

**System packages**: `python3`, `python3-pip`, `nodejs`, `npm`, `git`, `curl`, `wget`, `unzip`, `jq`, `sqlite3`, `openjdk-17-jdk`

**Security tools to install**:
- `apktool` â€” APK decompilation/recompilation
- `jadx` â€” APK â†’ Java source decompilation
- `frida-tools` â€” Frida CLI (pip install)
- `objection` â€” Objection CLI (pip install)
- `mitmproxy` â€” HTTP/HTTPS interception (pip install)
- `semgrep` â€” Static analysis (pip install)
- `nuclei` â€” Vulnerability scanner (go binary)
- `sqlmap` â€” SQL injection testing
- `class-dump` â€” iOS ObjC header extraction
- `reflutter` â€” Flutter RE tool (pip install)
- `blutter` â€” Dart AOT analyzer
- `aapt2` / `bundletool` â€” Android build tools
- `dex2jar` â€” DEX â†’ JAR conversion
- `jd-gui` â€” Java decompiler (optional, JAR form)
- `strings`, `file`, `binwalk` â€” Binary analysis basics
- `nmap`, `httpx`, `ffuf` â€” Network tools

**Python packages**: `frida-tools`, `objection`, `mitmproxy`, `semgrep`, `requests`, `lxml`, `pycryptodome`, `ipython`, `cryptography`, `httpx`, `websockets`

**Tool server**: The FastAPI tool_server code, started as the container entrypoint

#### Container Entrypoint Script

```bash
#!/bin/bash
# Start frida-server if device is connected
if adb devices 2>/dev/null | grep -q "device$"; then
    echo "Device detected, frida-server should be running on device"
fi

# Start the tool_server
python3 -m uvicorn maya.runtime.tool_server:app --host 0.0.0.0 --port 8000
```

### DockerRuntime Class

Manages the lifecycle of sandbox containers.

#### `create_sandbox(agent_id, auth_token, local_sources)` â†’ `SandboxInfo`

1. Build volume mounts for local source directories (read-only)
2. Run the container in detached mode with:
   - `SYS_PTRACE` capability (required for Frida to attach to processes)
   - `seccomp=unconfined` (required for ptrace syscalls)
   - Host network mode if `MAYA_HOST_NETWORK=true` (needed for device communication)
   - Random port mapping for the tool_server
   - Memory limit: 4GB, CPU quota: 2 CPUs
3. Wait for health check: poll `GET /health` on the mapped port every 2 seconds for up to 60 seconds
4. Register the agent: `POST /register_agent` with the agent_id
5. Return `SandboxInfo` with `workspace_id`, `server_url`, `auth_token`

#### `destroy_sandbox(agent_id)`

Stop container with 10-second timeout, remove from internal tracking.

#### `destroy_all()`

Tear down all containers (called at scan end).

### Tool Server (Inside Container)

FastAPI application that receives and executes tool requests.

#### Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Liveness check |
| `/register_agent` | POST | Register agent for session tracking |
| `/execute` | POST | Execute a tool: `{"agent_id", "tool_name", "kwargs"}` |

#### Dispatching

The tool server maintains a dispatch table mapping tool names to handler functions. Handlers fall into patterns:

1. **Terminal handlers** â€” Execute a shell command via `asyncio.create_subprocess_shell`, capture stdout/stderr, return with exit code
2. **Python handlers** â€” Execute Python code via `python3 -c` subprocess
3. **Frida handlers** â€” Write the Frida script to a temp file, execute `frida -U -n <pkg> -l <script_path>`, capture output
4. **Proxy handlers** â€” Start/stop mitmproxy, read flow files
5. **File handlers** â€” Read/write files in the workspace

Authentication: every request must include `Authorization: Bearer <token>` matching the `SANDBOX_AUTH_TOKEN` env var.

---

## 3. Companion Testing App

### Purpose

Some operations must run ON the device rather than over ADB/SSH. The companion app runs on the rooted/jailbroken test device and provides:

- WebSocket command receiver for real-time bidirectional control
- Target app installation and management
- Frida gadget injection into target apps
- Network traffic capture from the device side
- Filesystem inspection within app sandboxes
- Runtime hooking coordination
- Log collection (logcat/syslog)
- Exploit script execution
- Screenshot capture

### Architecture

```
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚  Maya Agent (Host)                â”‚
â”‚                                     â”‚
â”‚  companion_app_command tool          â”‚
â”‚     â†“ WebSocket                     â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚  Companion App (on Device)          â”‚
â”‚  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”   â”‚
â”‚  â”‚ WebSocket Server (:9999)     â”‚   â”‚
â”‚  â”‚   â†’ Command Router           â”‚   â”‚
â”‚  â”‚   â†’ Response Sender          â”‚   â”‚
â”‚  â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤   â”‚
â”‚  â”‚ Modules:                     â”‚   â”‚
â”‚  â”‚  â€¢ AppManager                â”‚   â”‚
â”‚  â”‚  â€¢ FridaGadgetInjector       â”‚   â”‚
â”‚  â”‚  â€¢ TrafficCapture            â”‚   â”‚
â”‚  â”‚  â€¢ FilesystemInspector       â”‚   â”‚
â”‚  â”‚  â€¢ LogCollector              â”‚   â”‚
â”‚  â”‚  â€¢ ExploitRunner             â”‚   â”‚
â”‚  â”‚  â€¢ ScreenshotCapture         â”‚   â”‚
â”‚  â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜   â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

### Android Companion (Kotlin)

**Target**: API 26+ (Android 8+), requires root

**Core components**:

1. **WebSocket Server** â€” Use Ktor or OkHttp WebSocket server on port 9999. Accept JSON commands, route to handlers, return JSON results.

2. **AppManager** â€” Install/uninstall APKs using `pm install` (root shell), list installed packages, get package info, clear app data.

3. **FridaGadgetInjector** â€” Copy `frida-gadget.so` into target app's lib directory (requires root), modify the app's smali to load the gadget on startup. Alternative: use `frida-server` which is already running.

4. **TrafficCapture** â€” Configure device proxy settings via `settings put global http_proxy`. For transparent capture: set iptables rules to redirect port 443 traffic through the proxy.

5. **FilesystemInspector** â€” With root access, read any file on the device. Focus on: `/data/data/<pkg>/`, `/data/data/<pkg>/shared_prefs/`, `/data/data/<pkg>/databases/`, Keystore entries.

6. **LogCollector** â€” Run `logcat -d -v threadtime *:V | grep <pkg>` to capture app logs. Look for sensitive data leakage.

7. **ExploitRunner** â€” Execute shell scripts or Frida scripts sent by the agent. Run with root privileges via `su -c`.

8. **ScreenshotCapture** â€” Use `screencap -p /sdcard/screenshot.png` and send back as base64.

### iOS Companion (Swift)

**Target**: iOS 14+, requires jailbreak

For iOS, the companion runs as a jailbreak tweak or a sideloaded app:

1. **WebSocket Server** â€” Use Starscream or a lightweight WS library on port 9999.
2. **AppManager** â€” Use `ideviceinstaller` or `dpkg` for jailbreak packages.
3. **KeychainDumper** â€” Use `keychain-dumper` binary or Security framework with entitlements.
4. **FilesystemInspector** â€” SSH-based or direct filesystem access with jailbreak.
5. **LogCollector** â€” Read `syslog` or use `os_log` streams.

### Command Protocol (JSON over WebSocket)

**Request format**:
```json
{
  "id": "cmd_12345",
  "command": "install_target",
  "params": {
    "apk_path": "/sdcard/target.apk"
  }
}
```

**Response format**:
```json
{
  "id": "cmd_12345",
  "status": "success",
  "data": {
    "package_name": "com.target.app",
    "version": "2.1.0",
    "installed": true
  }
}
```

**Available commands**:

| Command | Params | Returns |
|---------|--------|---------|
| `install_target` | `apk_path` or `ipa_path` | Package name, version, success status |
| `uninstall_target` | `package_name` | Success status |
| `hook_runtime` | `package_name`, `script` (Frida JS) | Hook output |
| `capture_traffic` | `action` (start/stop), `filter` | Captured flows |
| `ssl_unpin` | `package_name` | Bypass status |
| `collect_logs` | `package_name`, `duration_secs` | Log output |
| `inspect_filesystem` | `path`, `recursive` | File listing with sizes/permissions |
| `read_file` | `path` | File contents (base64 for binary) |
| `run_exploit` | `script_type` (shell/frida/python), `script_content` | Script output |
| `get_status` | â€” | Device info, connected packages, frida-server status |
| `screenshot` | â€” | Base64 PNG |
| `get_app_data` | `package_name` | SharedPrefs, databases list, files list |

---

## 4. Telemetry & Reporting

### Tracer

A central telemetry class that records everything during a scan for post-analysis and report generation.

**What it records**:
- Every LLM call: input messages (last 5), output, model, token usage
- Every tool execution: tool name, args, result summary, duration
- Every finding: the full Finding dict
- Every agent creation/completion event
- Timing: per-iteration, per-agent, total scan duration

**Output**: Save to `maya_runs/<run_name>/` directory:
- `trace.json` â€” Full trace log
- `findings.json` â€” All deduplicated findings
- `api_endpoints.json` â€” All discovered endpoints
- `report.md` â€” Human-readable markdown report
- `report.html` â€” Formatted HTML report with findings by severity

### Report Structure

```markdown
# Mobile Security Assessment Report

## Executive Summary
- Target: com.target.app v2.1.0
- Platform: Android 14 (rooted)
- Scan duration: 23 minutes
- Findings: 3 Critical, 5 High, 8 Medium, 12 Low, 4 Info

## Critical Findings
### [C-001] Hardcoded AES Encryption Key in BuildConfig
- **Category**: MASVS-CRYPTO
- **Description**: ...
- **Proof of Concept**: ...
- **Impact**: ...
- **Remediation**: ...

## High Findings
...

## API Endpoints Discovered
| Method | URL | Auth | Notes |
|--------|-----|------|-------|
| POST | /v2/auth/login | None | Returns JWT |
| GET | /v2/users/{id} | Bearer JWT | IDOR vulnerable |
...

## Agent Activity Summary
| Agent | Task | Iterations | Findings |
|-------|------|------------|----------|
| root_orchestrator | Coordinate assessment | 42 | 0 |
| static_analyzer | Static analysis of APK | 28 | 12 |
| dynamic_tester | Runtime instrumentation | 35 | 9 |
| api_discoverer | API mapping & testing | 22 | 11 |
```
