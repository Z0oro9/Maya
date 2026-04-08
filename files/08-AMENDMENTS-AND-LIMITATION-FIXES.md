# Maya AI Agent â€” Design Amendments & Limitation Fixes

This document supersedes the relevant sections in documents 01â€“07 where conflicts exist.

---

## 1. Dynamic Skills & Vulnerability Files as External Inputs

### Problem with Previous Design

The earlier design hardcoded skills inside `maya/skills/` as part of the project source. This means adding new vulnerability knowledge or updating attack techniques requires modifying the codebase and redeploying.

### New Design: External Skill Loading

Skills and vulnerability knowledge files are **external inputs**, loaded at runtime from configurable paths. Users, red teams, and security researchers can author, share, and swap skill packs without touching any agent code.

### Skill Resolution Order (highest priority first)

1. **CLI-provided skill directory**: `--skills-dir /path/to/custom/skills/`
2. **Environment variable**: `MAYA_SKILLS_DIR=/path/to/skills`
3. **User home directory**: `~/.maya/skills/`
4. **Project defaults**: `maya/skills/` (shipped with the project as fallback)

The skill loader merges all paths. If the same skill name appears in multiple locations, the highest-priority path wins. This allows users to override built-in skills with customized versions.

### How to Implement the Loader

```
SKILL_SEARCH_PATHS = [
    cli_arg_skills_dir,                    # --skills-dir
    os.environ.get("MAYA_SKILLS_DIR"),   # env var
    Path.home() / ".maya" / "skills",    # user home
    Path(__file__).parent / "skills",      # project defaults
]

def get_available_skills() -> dict[str, list[str]]:
    merged = {}
    # Process in REVERSE priority (so higher priority overwrites)
    for base_path in reversed(SKILL_SEARCH_PATHS):
        if not base_path or not Path(base_path).exists():
            continue
        for category_dir in Path(base_path).iterdir():
            if not category_dir.is_dir() or category_dir.name.startswith("_"):
                continue
            for md_file in category_dir.glob("*.md"):
                # Higher priority path overwrites lower
                merged.setdefault(category_dir.name, {})[md_file.stem] = md_file
    # Convert to {category: [names]}
    return {cat: sorted(files.keys()) for cat, files in merged.items()}
```

### Skill Packs

A "skill pack" is a directory of markdown files that can be distributed as a zip/tar:

```
my-skill-pack/
â”œâ”€â”€ vulnerabilities/
â”‚   â”œâ”€â”€ graphql_injection.md
â”‚   â”œâ”€â”€ race_condition_mobile.md
â”‚   â””â”€â”€ deeplink_hijacking.md
â”œâ”€â”€ frameworks/
â”‚   â””â”€â”€ kotlin_multiplatform.md
â””â”€â”€ custom/
    â””â”€â”€ company_specific_api_patterns.md
```

Users install a pack by extracting it to `~/.maya/skills/` or pointing `--skills-dir` at it.

### Dynamic Skill Hot-Reload

During a long scan, the root agent can reload skills without restarting. Implement a `reload_skills` tool:

| Tool | Sandbox | Purpose |
|------|---------|---------|
| `reload_skills` | No (local) | Rescan skill directories, refresh available skills list |
| `list_available_skills` | No (local) | Show all loaded skills with source paths and descriptions |
| `inject_skill` | No (local) | Dynamically inject a skill into a running agent's context |

When `inject_skill` is called, the skill content is appended to the agent's conversation as a user message wrapped in `<dynamic_skill>` tags, rather than modifying the system prompt (which would break conversation continuity).

### Vulnerability Knowledge Base Files

In addition to skills (which are methodology-focused), maintain a separate vulnerability knowledge base:

```
~/.maya/vulndb/
â”œâ”€â”€ cve/
â”‚   â”œâ”€â”€ CVE-2024-XXXXX.md     # Specific CVEs relevant to mobile
â”‚   â””â”€â”€ CVE-2025-YYYYY.md
â”œâ”€â”€ owasp/
â”‚   â”œâ”€â”€ MASVS-STORAGE.md       # OWASP MASVS category guides
â”‚   â”œâ”€â”€ MASVS-CRYPTO.md
â”‚   â””â”€â”€ MASVS-AUTH.md
â””â”€â”€ custom/
    â””â”€â”€ internal_api_vulns.md   # Org-specific knowledge
```

Vuln DB files are loaded differently from skills â€” they are searched on demand when the agent encounters a relevant finding, rather than injected wholesale into the prompt. When the agent calls a `lookup_vulnerability_knowledge` tool with a category or CVE ID, the relevant file is loaded and returned as a tool result.

| Tool | Sandbox | Purpose |
|------|---------|---------|
| `lookup_vulnerability_knowledge` | No (local) | Search vuln DB by CVE, MASVS category, or keyword |
| `search_skills` | No (local) | Full-text search across all loaded skills |

---

## 2. Caido Instead of mitmproxy

### Why Caido

Caido is the same proxy that Strix uses internally. It is a Rust-based security proxy with several advantages over mitmproxy for our use case:

- **Headless mode with REST API** â€” Caido runs as a self-contained CLI binary with a full API accessible via a JS/TS SDK or raw GraphQL. Agents can programmatically create projects, set scopes, replay requests, search traffic, and export findings.
- **HTTPQL** â€” A purpose-built query language for filtering HTTP traffic (`req.method.eq:"POST" AND req.path.cont:"/api/"`) â€” much more powerful than mitmproxy's filter syntax for agent consumption.
- **Invisible proxying** â€” Can intercept traffic without configuring proxy settings on the device (useful for apps that ignore system proxy).
- **DNS overrides** â€” Redirect specific domains to different IPs without modifying the device's hosts file.
- **WebSocket support** â€” Captures and manipulates WebSocket traffic natively, which mitmproxy handles but less elegantly.
- **Plugin ecosystem** â€” 42+ community plugins including SQLi testing, GraphQL analysis, and sensitive file detection.
- **Caido Skills (MCP-like)** â€” Official SDK for AI agent integration, meaning the agent can programmatically drive all Caido features.
- **Built-in AI assistant** â€” Already has LLM integration for security analysis.
- **Project isolation** â€” Each scan gets its own project with separate traffic, findings, and configuration.

### Caido Architecture in Maya

```
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚  Docker Sandbox Container               â”‚
â”‚                                         â”‚
â”‚  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”   â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”  â”‚
â”‚  â”‚ Caido CLI    â”‚   â”‚ tool_server    â”‚  â”‚
â”‚  â”‚ (headless)   â”‚   â”‚ (FastAPI)      â”‚  â”‚
â”‚  â”‚ :8080        â”‚â—„â”€â”€â”‚                â”‚  â”‚
â”‚  â”‚              â”‚   â”‚  Proxy tools   â”‚  â”‚
â”‚  â”‚ REST/GraphQL â”‚   â”‚  use Caido SDK â”‚  â”‚
â”‚  â”‚ API          â”‚   â”‚                â”‚  â”‚
â”‚  â””â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”˜   â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜  â”‚
â”‚         â”‚                               â”‚
â”‚    Traffic flows                        â”‚
â”‚         â”‚                               â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚         â–¼                               â”‚
â”‚    Device traffic (via ADB proxy        â”‚
â”‚    settings or iptables redirect)       â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

### Caido Tool Replacements

Replace all `proxy_*` tools with Caido-native equivalents:

| Old Tool (mitmproxy) | New Tool (Caido) | How It Works |
|----------------------|------------------|--------------|
| `proxy_start_intercept` | `caido_start` | Launch Caido CLI in headless mode: `caido-cli --listen 0.0.0.0:8080 --no-open --allow-guests`. Create a project via SDK. |
| `proxy_get_captured_traffic` | `caido_search_traffic` | Use HTTPQL via the SDK: `client.httpHistory.search('req.host.cont:"api.target.com"')`. Returns structured request/response data. |
| `proxy_replay_request` | `caido_replay_request` | Use Replay API: `client.replay.send(requestId, {modifications})`. Supports header/body modification. |
| `proxy_export_api_schema` | `caido_export_sitemap` | Export the sitemap tree via SDK. Also use the Automate API to generate endpoint lists. |
| `api_fuzz_endpoint` | `caido_automate_fuzz` | Use Caido's Automate feature via SDK: create payload placeholders and run fuzz sessions programmatically. |
| â€” (new) | `caido_create_finding` | Use Caido's Findings API to create entries with markdown descriptions, linked to specific requests. |
| â€” (new) | `caido_set_scope` | Define in-scope targets via SDK, so Caido only captures relevant traffic. |
| â€” (new) | `caido_get_websocket_traffic` | Search and inspect WebSocket messages via SDK. |

### Caido Setup in the Sandbox Container

Add to the Dockerfile:

```
# Download Caido CLI binary
RUN curl -sL https://caido.download/releases/latest \
    | jq -r '.links[] | select(.os=="linux" and .arch=="x86_64" and .kind=="cli") | .link' \
    | xargs curl -sLo /tmp/caido.tar.gz \
    && tar -xzf /tmp/caido.tar.gz -C /usr/local/bin/ \
    && rm /tmp/caido.tar.gz

# Install Caido JS SDK for programmatic access
RUN npm install -g @caido/sdk
```

### Caido Authentication

In headless guest mode (`--allow-guests`), no authentication is needed for local access within the container. For programmatic access, generate a Personal Access Token (PAT) and pass it to the SDK client.

---

## 3. Docker â†” External Mobile Device: Solving the Isolation Problem

### The Core Problem

Docker containers are isolated from host hardware. The sandbox container needs to:
1. Send ADB commands to a USB-connected Android device
2. Send SSH/idevice commands to a USB-connected iOS device
3. Receive Frida traffic from the device (Frida uses TCP over USB)
4. Route device HTTP traffic through Caido running in the container
5. Send WebSocket commands to the companion app running on the device

The container has **no direct USB access**. This is the biggest architectural challenge.

### Solution: The Hybrid Bridge Architecture

Do NOT try to pass USB into Docker. Instead, use a **split architecture** where ADB/idevice services run on the host, and the container communicates with them over TCP.

```
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚  HOST MACHINE                                          â”‚
â”‚                                                        â”‚
â”‚  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”                                      â”‚
â”‚  â”‚ ADB Server   â”‚  â† adb start-server (runs on host)  â”‚
â”‚  â”‚ Port 5037    â”‚  â† Manages USB device connections    â”‚
â”‚  â””â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”˜                                      â”‚
â”‚         â”‚ TCP                                          â”‚
â”‚  â”Œâ”€â”€â”€â”€â”€â”€â”¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”   â”‚
â”‚  â”‚      â–¼  DOCKER CONTAINER (sandbox)              â”‚   â”‚
â”‚  â”‚  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”                               â”‚   â”‚
â”‚  â”‚  â”‚ ADB Client   â”‚  â† connects to host:5037      â”‚   â”‚
â”‚  â”‚  â”‚ (no server)  â”‚  â† ANDROID_ADB_SERVER_ADDRESS â”‚   â”‚
â”‚  â”‚  â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜     = host.docker.internal     â”‚   â”‚
â”‚  â”‚                                                  â”‚   â”‚
â”‚  â”‚  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”                               â”‚   â”‚
â”‚  â”‚  â”‚ Frida client â”‚  â† frida -H host:27042        â”‚   â”‚
â”‚  â”‚  â”‚ (TCP mode)   â”‚  â† or frida -U via adb fwd   â”‚   â”‚
â”‚  â”‚  â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜                               â”‚   â”‚
â”‚  â”‚                                                  â”‚   â”‚
â”‚  â”‚  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”         â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”      â”‚   â”‚
â”‚  â”‚  â”‚ Caido        â”‚ â—„â”€trafficâ”€ â”‚ Device     â”‚      â”‚   â”‚
â”‚  â”‚  â”‚ :8080        â”‚  (via adb â”‚ proxy       â”‚      â”‚   â”‚
â”‚  â”‚  â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜  reverse) â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜     â”‚   â”‚
â”‚  â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜   â”‚
â”‚         â”‚                                              â”‚
â”‚     USB â”‚                                              â”‚
â”‚  â”Œâ”€â”€â”€â”€â”€â”€â”´â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”                                   â”‚
â”‚  â”‚ MOBILE DEVICE   â”‚                                   â”‚
â”‚  â”‚ frida-server    â”‚  â† port 27042                     â”‚
â”‚  â”‚ companion app   â”‚  â† port 9999                      â”‚
â”‚  â”‚ target app      â”‚                                   â”‚
â”‚  â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜                                   â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

### Implementation Steps

#### Step 1: ADB Server Stays on Host

The ADB **server** runs on the host machine (not in Docker). The Docker container runs ADB **client** commands that connect to the host's server over TCP.

Inside the container, set:
```bash
export ADB_SERVER_SOCKET=tcp:host.docker.internal:5037
# or for Linux hosts without host.docker.internal:
export ADB_SERVER_SOCKET=tcp:172.17.0.1:5037
```

Now `adb devices` inside the container lists the host's USB-connected devices.

#### Step 2: ADB Port Forwarding for Frida

On the **host**, set up port forwards so the container can reach frida-server and the companion app on the device:

```bash
# Forward frida-server (device port 27042 â†’ host port 27042)
adb forward tcp:27042 tcp:27042

# Forward companion app WebSocket (device port 9999 â†’ host port 9999)
adb forward tcp:9999 tcp:9999
```

Inside the container, Frida connects via:
```bash
frida -H host.docker.internal:27042 -n com.target.app
```

And the companion app is reachable at:
```
ws://host.docker.internal:9999/command
```

#### Step 3: Caido Traffic Interception

Option A â€” **ADB reverse proxy** (recommended):
```bash
# On host: Make device route traffic through container's Caido
# Container Caido listens on port 8080
# Map container port 8080 to host port 8080 via Docker port mapping
adb reverse tcp:8080 tcp:8080
# Then on device: set proxy to 127.0.0.1:8080
adb shell settings put global http_proxy 127.0.0.1:8080
```

Option B â€” **Transparent interception via iptables** on rooted device:
```bash
adb shell su -c 'iptables -t nat -A OUTPUT -p tcp --dport 443 -j DNAT --to-destination <host-ip>:8080'
```

#### Step 4: iOS Device Handling

For jailbroken iOS devices connected via USB:

```bash
# On host: start usbmuxd (handles USB multiplexing for iOS)
# iproxy forwards device SSH port to host
iproxy 2222 22 &  # SSH via localhost:2222
iproxy 27042 27042 &  # frida-server
iproxy 9999 9999 &  # companion app
```

Container connects to `host.docker.internal:2222` for SSH, `host.docker.internal:27042` for Frida, etc.

#### Step 5: WiFi-Connected Devices (alternative to USB)

If the device is on the same network as the host:

```bash
# Android: enable WiFi ADB
adb tcpip 5555
adb connect <device-ip>:5555
```

Container uses `--network=host` mode and connects directly to `<device-ip>`:
```bash
frida -H <device-ip>:27042 -n com.target.app
```

This is simpler than USB but requires the device and host to be on the same network.

### DockerRuntime Updates

The `create_sandbox()` method needs to:

1. **Before creating container**: Set up host-side port forwards:
   ```
   adb forward tcp:27042 tcp:27042  # frida
   adb forward tcp:9999 tcp:9999    # companion app
   adb reverse tcp:8080 tcp:8080    # caido proxy
   ```

2. **Container creation flags**:
   ```python
   container = client.containers.run(
       image=CONTAINER_IMAGE,
       environment={
           "ADB_SERVER_SOCKET": f"tcp:{host_gateway}:5037",
           "FRIDA_HOST": f"{host_gateway}:27042",
           "COMPANION_HOST": f"{host_gateway}:9999",
       },
       extra_hosts={"host.docker.internal": "host-gateway"},
       # Map Caido port so device reverse proxy works
       ports={"8080/tcp": 8080, "8000/tcp": None},
       cap_add=["SYS_PTRACE"],
       security_opt=["seccomp=unconfined"],
   )
   ```

3. **Device tool updates**: All `device_*` and `frida_*` tools must use:
   - `ADB_SERVER_SOCKET` env var for ADB commands (client talks to host server)
   - `frida -H $FRIDA_HOST` instead of `frida -U` (TCP instead of USB)
   - `ws://$COMPANION_HOST/command` for companion app WebSocket

### Host Setup Script

Provide a `scripts/setup-host.sh` that users run before starting a scan:

```bash
#!/bin/bash
# Run on the HOST machine before starting Maya

echo "[*] Starting ADB server..."
adb start-server

echo "[*] Checking device connection..."
adb devices -l

echo "[*] Setting up port forwards..."
adb forward tcp:27042 tcp:27042  # frida-server
adb forward tcp:9999 tcp:9999    # companion app

echo "[*] Starting frida-server on device..."
adb shell "su -c '/data/local/tmp/frida-server -D &'"

echo "[*] Setting up reverse proxy for Caido..."
adb reverse tcp:8080 tcp:8080

echo "[*] Host ready. Start Maya scan."
```

---

## 4. Limitations in the Current Design & Fixes

### Limitation 1: Tools Return JSON Descriptions, Not Actual Results

**Problem**: In the Phase 2 implementation, most tools return a JSON dict describing what command *should* be run, but don't actually execute anything. For example, `frida_bypass_ssl_pinning` returns a JSON with a `frida_script` field but doesn't run it. The agent would then need to take that script and call `terminal_execute` to actually run Frida â€” a two-step process that wastes iterations and confuses the LLM.

**Fix**: Every sandbox tool must actually execute its operation inside the `tool_server` and return real results. The tool function on the host side is just a serialization layer; the actual work happens in the container's dispatcher.

**Implementation pattern**:

The host-side tool function generates the command/script and sends it to the sandbox. The sandbox's `tool_server._dispatch_tool()` method receives the command and executes it. The host-side tool should NOT return a "hint" or "next_steps" â€” it should return the actual stdout/stderr of the executed operation.

For Frida tools specifically:
1. Host tool generates the JavaScript + package name
2. Sends to sandbox as: `{"tool_name": "frida_bypass_ssl_pinning", "kwargs": {"package_name": "com.target", "script": "<generated JS>"}}`
3. Sandbox writes script to `/tmp/frida_<id>.js`, executes `frida -H $FRIDA_HOST -n com.target -l /tmp/frida_<id>.js --no-pause -q`, returns real output
4. Host returns the real Frida output to the agent conversation

### Limitation 2: No Frida Session Persistence

**Problem**: Each Frida tool call spawns a new Frida process. This means SSL pinning bypass is lost when the next Frida tool runs, because the first process is killed.

**Fix**: Implement a `FridaSessionManager` inside the tool_server that maintains a persistent Frida session per package per agent.

**Design**:
- When `frida_attach` or `frida_spawn` is called, start a Frida process and keep it alive
- Subsequent `frida_run_script`, `frida_hook_method`, etc. inject into the EXISTING session
- The session stays alive across tool calls until `frida_detach` is explicitly called or the agent finishes
- Use Frida's Python bindings (`frida.get_device().attach(pid)`) instead of CLI for session management

The `_agent_sessions` dict in tool_server tracks:
```python
_agent_sessions[agent_id] = {
    "frida": {
        "device": frida.get_remote_device(),  # via TCP to host
        "session": session_object,             # persistent attach
        "scripts": [],                         # loaded scripts
        "pid": target_pid,
    },
    "caido": {
        "client": CaidoSDKClient,
        "project_id": "...",
    }
}
```

### Limitation 3: No Context Continuity Across Sub-Agents

**Problem**: When the root agent spawns a static analyzer and a dynamic tester, each starts with a blank conversation. The dynamic agent doesn't know what the static agent found (API URLs, hardcoded keys, interesting classes). Findings are only shared when `agent_finish` reports back to the parent, which is too late â€” the sub-agents need real-time context sharing.

**Fix**: Implement a **shared context store** that all agents in a scan can read/write.

**Design**:
```
SharedContext (per scan, not per agent):
â”œâ”€â”€ discovered_urls: list[str]         # API URLs found in code
â”œâ”€â”€ discovered_endpoints: list[dict]   # Full endpoint details
â”œâ”€â”€ interesting_classes: list[str]     # Classes worth hooking
â”œâ”€â”€ extracted_secrets: list[dict]      # Keys, tokens, credentials
â”œâ”€â”€ bypasses_active: dict              # {"ssl_pinning": True, "root_detection": True}
â”œâ”€â”€ decompiled_paths: dict             # {"apktool": "/path", "jadx": "/path"}
â”œâ”€â”€ app_metadata: dict                 # Package name, version, permissions, components
â””â”€â”€ notes: list[dict]                  # Timestamped notes from any agent
```

Tools to expose:
| Tool | Purpose |
|------|---------|
| `shared_context_write` | Write a key-value to the shared store |
| `shared_context_read` | Read a specific key or all keys from the store |

When the static agent finds API URLs, it calls:
```xml
<function=shared_context_write>
<parameter=key>discovered_urls</parameter>
<parameter=value>["https://api.target.com/v2/auth", "https://api.target.com/v2/users"]</parameter>
</function>
```

When the dynamic agent starts, its system prompt includes: "Before starting dynamic testing, read the shared context to check what other agents have discovered." The agent then calls `shared_context_read` and gets all cross-agent knowledge.

### Limitation 4: No Scan Resumption

**Problem**: If a scan crashes or is interrupted (device disconnect, LLM rate limit exhaustion, user Ctrl+C), all progress is lost. Long scans (30+ minutes) are especially vulnerable.

**Fix**: Implement checkpoint-based state persistence.

**Design**:
- After every N iterations (configurable, default 5), serialize the entire `AgentState` to disk:
  `maya_runs/<run_name>/checkpoints/<agent_id>_iter_<N>.json`
- Include: conversation history, findings, api_endpoints, todo_items, notes, tool_call_count
- On startup with `--resume <run_name>`, load the latest checkpoint for each agent and continue from where they left off
- The `AgentGraph` topology is also checkpointed so sub-agent relationships are restored

### Limitation 5: No Rate Limiting on Tool Calls

**Problem**: The agent can fire tools extremely rapidly, especially in loops (e.g., fuzzing 100 API endpoints). This can:
- Overwhelm frida-server on the device
- Trigger rate limiting on the target app's API
- Exhaust LLM API credits with rapid iterations

**Fix**: Implement a `RequestQueue` (similar to Strix's `request_queue.py`) with configurable throttling:

```
tool_rate_limits = {
    "frida_*": {"max_per_minute": 30, "cooldown_seconds": 2},
    "caido_*": {"max_per_minute": 60, "cooldown_seconds": 0.5},
    "api_fuzz_*": {"max_per_minute": 10, "cooldown_seconds": 5},
    "llm_call": {"max_per_minute": 20, "cooldown_seconds": 3},
}
```

The executor checks the rate limit before executing each tool and delays if necessary.

### Limitation 6: No iOS Parity

**Problem**: The current design is heavily Android-biased. iOS tools are mentioned but not fully designed. Many tools assume ADB commands that have no iOS equivalent.

**Fix**: Every device-interacting tool must have platform-aware logic:

```python
@register_tool
async def device_dump_app_data(package_name, agent_state):
    platform = agent_state.device_platform
    
    if platform == "android":
        # adb shell su -c 'cp -r /data/data/<pkg>/ ...'
        ...
    elif platform == "ios":
        # ssh root@device 'tar -czf /tmp/dump.tar.gz /var/mobile/Containers/...'
        ...
```

Additionally, create iOS-specific tools that have no Android equivalent:

| iOS-Only Tool | Purpose |
|---------------|---------|
| `ios_decrypt_binary` | Decrypt App Store binaries using Clutch or flexdecrypt |
| `ios_dump_keychain` | Dump Keychain items with keychain-dumper |
| `ios_check_ats` | Analyze App Transport Security exceptions in Info.plist |
| `ios_inspect_entitlements` | Extract and analyze entitlements |
| `ios_check_pasteboard` | Monitor UIPasteboard for sensitive data exposure |
| `ios_url_scheme_fuzz` | Fuzz registered URL schemes for injection |

### Limitation 7: System Prompt Is Monolithic

**Problem**: The system prompt template is a single massive Jinja2 file. As skills and tools grow, the prompt will exceed context windows. Even now, injecting 3-4 skills plus all tool schemas can consume 15K+ tokens of system prompt.

**Fix**: Implement **tiered prompt loading**:

**Tier 1 â€” Always loaded** (core identity, methodology overview, tool invocation format, agent graph rules, finding format):
~3,000 tokens

**Tier 2 â€” Loaded based on agent role** (tool schemas only for tools the agent needs):
- Static agent: only APK, MobSF, terminal, reporting tool schemas
- Dynamic agent: only Frida, Objection, device bridge, reporting tool schemas  
- API agent: only Caido, terminal, Frida (for SSL bypass), reporting tool schemas
~2,000â€“4,000 tokens per role

**Tier 3 â€” Skills injected based on assignment**:
~1,000â€“3,000 tokens per skill

This keeps total system prompt under 10K tokens for any single agent, leaving room for conversation history.

Implementation: add a `role` field to `MayaAgent` constructor (`"root"`, `"static"`, `"dynamic"`, `"api"`, `"exploit"`). The `build_system_prompt()` method uses this role to filter which tool schemas are included.

### Limitation 8: No Validation That Tools Actually Produced Useful Output

**Problem**: The agent calls `frida_bypass_ssl_pinning` and gets back a success message, but the SSL bypass might not have actually worked. The agent proceeds to intercept traffic and gets nothing â€” then loops trying different approaches without understanding the root cause.

**Fix**: Implement **verification tools** that validate the output of key operations:

| Verification Tool | Validates | How |
|-------------------|-----------|-----|
| `verify_ssl_bypass` | SSL pinning is actually bypassed | Make a test HTTPS request through Caido and check if it's captured. If not, bypass failed. |
| `verify_frida_attached` | Frida is connected to the target | Call `frida.get_device().enumerate_processes()` and check target PID exists. |
| `verify_device_connected` | Device is reachable | Run `adb devices` and parse output. |
| `verify_proxy_active` | Caido is receiving traffic | Check Caido's HTTP history count via SDK. |

Teach the agent in the system prompt: "After critical setup operations (SSL bypass, Frida attach, proxy start), always run the corresponding verification tool before proceeding."

### Limitation 9: Memory Compressor Loses Findings

**Problem**: When the conversation gets compressed (summarized to fit context window), specific findings details, Frida script outputs, and tool results may be lost in the summary.

**Fix**: Before compression, extract all structured data (findings, API endpoints, active bypasses) and store them separately. After compression, re-inject them as a structured context block:

```
<preserved_context>
  <findings_so_far>
    [list of all findings reported]
  </findings_so_far>
  <api_endpoints>
    [list of all discovered endpoints]
  </api_endpoints>
  <active_state>
    ssl_bypass: active
    frida_session: attached to com.target.app
    caido_project: scan_12345
  </active_state>
</preserved_context>
```

This ensures critical state survives compression.

### Limitation 10: Companion App Is a Single Point of Failure

**Problem**: If the companion app crashes on the device, all device-side capabilities are lost.

**Fix**: Design the system so the companion app is OPTIONAL, not required:

- **Without companion app**: All operations work through ADB shell commands + Frida + Caido. This covers 90% of testing scenarios.
- **With companion app**: Enhanced capabilities â€” faster file inspection, real-time log streaming, coordinated exploit execution, screenshot capture.

The agent should detect whether the companion app is available (via `companion_app_command(command="get_status")`) and adapt its strategy accordingly. If unavailable, fall back to ADB/Frida alternatives for each operation.
