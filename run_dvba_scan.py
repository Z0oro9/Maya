"""Launch Maya agent to scan DVBA with Docker sandbox enforcement."""

import os
import sys

# Load .env
from pathlib import Path

env_file = Path(__file__).parent / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip('"')
            os.environ[key] = val

# Map MODEL -> MAYA_LLM (config.py reads MAYA_LLM)
if os.environ.get("MODEL") and not os.environ.get("MAYA_LLM"):
    os.environ["MAYA_LLM"] = os.environ["MODEL"]

from maya.main import cli  # noqa: E402

sys.argv = [
    "maya",
    "--task",
    (
        "Perform a comprehensive security assessment of the Damn Vulnerable Bank App "
        "(com.app.damnvulnerablebank). "
        "The APK file is available inside the sandbox at /workspace/MOBSEC/dvba_v1.1.0.apk. "
        "The app is already installed on the connected Android device RFCNC0SEQEM. "
        "All tool executions (apktool, jadx, terminal_execute, adb, frida, etc.) run inside a "
        "Docker sandbox container. Use /workspace/MOBSEC/ as the base path for files. "
        "Steps: "
        "1) Decompile the APK with apktool and jadx. "
        "2) Analyze AndroidManifest.xml for exported components, permissions, backup flag, debuggable flag. "
        "3) Search decompiled code for insecure storage, hardcoded secrets, WebView misconfig, SQL injection. "
        "4) Use ADB device commands to enumerate the app attack surface on the live device. "
        "5) Check for tapjacking, content provider injection, network security config, certificate pinning. "
        "6) Record each finding with report_vulnerability (title, severity, category, description, evidence). "
        "7) Finish with finish_scan including full summary."
    ),
    "--target",
    "/workspace/MOBSEC/dvba_v1.1.0.apk",
    "--target",
    "com.app.damnvulnerablebank",
    "--device",
    "RFCNC0SEQEM",
    "--platform",
    "android",
    "--scan-mode",
    "comprehensive",
    "--output-dir",
    "maya_runs/dvba_docker_scan",
    "-n",
]

cli()
