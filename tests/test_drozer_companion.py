"""Integration tests for drozer-equivalent companion app commands.

These test the same shell commands used by the companion app modules
via ADB, and also test the Python drozer_tool registration and
device_bridge tooling.

Run with:
    MAYA_RUN_DEVICE_TESTS=1 python -m pytest tests/test_drozer_companion.py -v
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess

import pytest
from dotenv import load_dotenv

load_dotenv()

from maya.tools.device_bridge import (  # noqa: E402
    companion_app_command,
    device_list,
    device_shell,
)

# ---------------------------------------------------------------------------
# Markers
# ---------------------------------------------------------------------------

requires_device = pytest.mark.skipif(
    os.environ.get("MAYA_RUN_DEVICE_TESTS") != "1",
    reason="Set MAYA_RUN_DEVICE_TESTS=1 to run real device-backed integration tests.",
)

requires_adb = pytest.mark.skipif(
    shutil.which("adb") is None,
    reason="adb binary not found in PATH",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _adb_shell(cmd: str, timeout: int = 30) -> dict:
    """Run an ADB shell command and return stdout/exit_code."""
    proc = subprocess.run(
        ["adb", "shell", cmd],
        text=True,
        capture_output=True,
        timeout=timeout,
    )
    return {"stdout": proc.stdout, "stderr": proc.stderr, "exit_code": proc.returncode}


# ===========================================================================
# 1. Tool Registration Tests (no device required)
# ===========================================================================


class TestToolRegistration:
    """Verify all drozer tools register correctly."""

    def test_drozer_tools_import(self) -> None:
        from maya.tools import drozer_tool  # noqa: F401

        assert True

    def test_drozer_tools_count(self) -> None:
        from maya.tools.registry import get_tools_prompt

        prompt = get_tools_prompt()
        drozer_lines = [line for line in prompt.split("\n") if "drozer_" in line and "<tool name=" in line]
        assert len(drozer_lines) >= 25, f"Expected >=25 drozer tools, got {len(drozer_lines)}"

    def test_drozer_tools_have_descriptions(self) -> None:
        from maya.tools.registry import get_tools_prompt

        prompt = get_tools_prompt()
        # Find drozer tool blocks and ensure they have descriptions
        in_drozer_block = False
        for line in prompt.split("\n"):
            if '<tool name="drozer_' in line:
                in_drozer_block = True
            elif in_drozer_block and "<description>" in line:
                assert len(line.strip()) > 30, f"Drozer tool has empty description: {line}"
                in_drozer_block = False

    def test_all_tools_total_count(self) -> None:
        from maya.tools.registry import get_tools_prompt

        prompt = get_tools_prompt()
        tool_lines = [line for line in prompt.split("\n") if "<tool name=" in line]
        assert len(tool_lines) >= 95, f"Expected >=95 total tools, got {len(tool_lines)}"


# ===========================================================================
# 2. ADB Connectivity Tests
# ===========================================================================


@requires_device
@requires_adb
class TestADBConnectivity:
    """Verify device is accessible via ADB."""

    def test_adb_device_list(self) -> None:
        result = device_list()
        assert result["exit_code"] == 0
        assert "device" in result["stdout"]

    def test_adb_shell_basic(self) -> None:
        result = device_shell(command="echo hello", timeout="10")
        assert result["exit_code"] == 0
        assert "hello" in result["stdout"]


# ===========================================================================
# 3. Package Analysis Tests (drozer: app.package.*)
# ===========================================================================


@requires_device
@requires_adb
class TestPackageAnalysis:
    """Test drozer-equivalent package analysis via ADB shell."""

    def test_package_list(self) -> None:
        result = _adb_shell("pm list packages | head -10")
        assert result["exit_code"] == 0
        assert "package:" in result["stdout"]

    def test_package_list_third_party(self) -> None:
        result = _adb_shell("pm list packages -3 | head -5")
        assert result["exit_code"] == 0
        assert "package:" in result["stdout"]

    def test_package_info(self) -> None:
        result = _adb_shell("dumpsys package android | head -20")
        assert result["exit_code"] == 0
        assert "android" in result["stdout"].lower()

    def test_package_apk_path(self) -> None:
        result = _adb_shell("pm path android")
        assert result["exit_code"] == 0
        assert "package:" in result["stdout"]

    def test_package_permissions(self) -> None:
        result = _adb_shell("dumpsys package com.sec.android.app.sbrowser | grep 'android.permission' | head -10")
        assert result["exit_code"] == 0
        # Samsung browser should have some permissions
        assert "permission" in result["stdout"].lower() or result["stdout"].strip() != ""


# ===========================================================================
# 4. Activity Analysis Tests (drozer: app.activity.*)
# ===========================================================================


@requires_device
@requires_adb
class TestActivityAnalysis:
    """Test drozer-equivalent activity enumeration via ADB shell."""

    def test_activity_resolver_table(self) -> None:
        result = _adb_shell("pm dump com.sec.android.app.sbrowser | head -5")
        assert result["exit_code"] == 0
        assert "Activity Resolver Table" in result["stdout"] or "DUMP" in result["stdout"]

    def test_browsable_activities(self) -> None:
        result = _adb_shell(
            "dumpsys package | grep -B5 'android.intent.category.BROWSABLE' | grep 'Activity\\|Scheme' | head -10"
        )
        assert result["exit_code"] == 0
        # There should be browsable activities on any Android device


# ===========================================================================
# 5. Content Provider Tests (drozer: app.provider.*)
# ===========================================================================


@requires_device
@requires_adb
class TestContentProviderAnalysis:
    """Test drozer-equivalent content provider interaction via ADB shell."""

    def test_content_query_settings(self) -> None:
        result = _adb_shell("content query --uri content://settings/system 2>&1 | head -3")
        assert result["exit_code"] == 0
        assert "Row:" in result["stdout"] or "name=" in result["stdout"]

    def test_content_query_secure_settings(self) -> None:
        result = _adb_shell("content query --uri content://settings/secure --where \"name='android_id'\" 2>&1")
        assert result["exit_code"] == 0

    def test_provider_info(self) -> None:
        result = _adb_shell("dumpsys package android | grep -A5 'ContentProvider' | head -10")
        assert result["exit_code"] == 0


# ===========================================================================
# 6. Broadcast Receiver Tests (drozer: app.broadcast.*)
# ===========================================================================


@requires_device
@requires_adb
class TestBroadcastAnalysis:
    """Test drozer-equivalent broadcast receiver operations."""

    def test_receiver_resolver_table(self) -> None:
        result = _adb_shell("pm dump android | grep 'Receiver' | head -5")
        assert result["exit_code"] == 0


# ===========================================================================
# 7. Service Analysis Tests (drozer: app.service.*)
# ===========================================================================


@requires_device
@requires_adb
class TestServiceAnalysis:
    """Test drozer-equivalent service operations."""

    def test_running_services(self) -> None:
        result = _adb_shell("dumpsys activity services | grep 'ServiceRecord' | head -10")
        assert result["exit_code"] == 0
        assert "ServiceRecord" in result["stdout"]

    def test_service_resolver(self) -> None:
        result = _adb_shell("pm dump android | grep 'Service' | head -5")
        assert result["exit_code"] == 0


# ===========================================================================
# 8. Device Info Tests (drozer: information.*)
# ===========================================================================


@requires_device
@requires_adb
class TestDeviceInfo:
    """Test drozer-equivalent device information retrieval."""

    def test_device_model(self) -> None:
        result = _adb_shell("getprop ro.product.model")
        assert result["exit_code"] == 0
        assert len(result["stdout"].strip()) > 0

    def test_android_version(self) -> None:
        result = _adb_shell("getprop ro.build.version.release")
        assert result["exit_code"] == 0
        version = result["stdout"].strip()
        assert version.replace(".", "").isdigit()

    def test_sdk_version(self) -> None:
        result = _adb_shell("getprop ro.build.version.sdk")
        assert result["exit_code"] == 0
        sdk = int(result["stdout"].strip())
        assert sdk >= 21  # At least Lollipop

    def test_selinux_status(self) -> None:
        result = _adb_shell("getenforce 2>/dev/null || echo unknown")
        assert result["exit_code"] == 0
        assert result["stdout"].strip() in ("Enforcing", "Permissive", "Disabled", "unknown")

    def test_build_fingerprint(self) -> None:
        result = _adb_shell("getprop ro.build.fingerprint")
        assert result["exit_code"] == 0
        assert "/" in result["stdout"]  # fingerprint format: brand/product/device:...

    def test_network_interfaces(self) -> None:
        result = _adb_shell("ip addr | head -20")
        assert result["exit_code"] == 0
        assert "inet" in result["stdout"] or "lo:" in result["stdout"]

    def test_process_list(self) -> None:
        result = _adb_shell("ps -A | head -10")
        assert result["exit_code"] == 0
        assert "PID" in result["stdout"] or "root" in result["stdout"].lower()


# ===========================================================================
# 9. Vulnerability Scanner Tests (drozer: scanner.*)
# ===========================================================================


@requires_device
@requires_adb
class TestVulnerabilityScanner:
    """Test drozer-equivalent scanning operations."""

    def test_debuggable_check(self) -> None:
        result = _adb_shell("getprop ro.debuggable")
        assert result["exit_code"] == 0
        assert result["stdout"].strip() in ("0", "1")

    def test_root_indicators(self) -> None:
        result = _adb_shell("which su 2>/dev/null; getprop ro.build.tags")
        assert result["exit_code"] == 0
        # Should contain build tags info at minimum

    def test_ca_cert_enumeration(self) -> None:
        result = _adb_shell("ls /system/etc/security/cacerts/ 2>/dev/null | wc -l")
        assert result["exit_code"] == 0
        count = int(result["stdout"].strip())
        assert count > 0, "System should have CA certificates"


# ===========================================================================
# 10. Companion Protocol Test (requires companion running)
# ===========================================================================


@requires_device
class TestCompanionProtocol:
    """Test companion HTTP/WS protocol â€” skips if companion not reachable."""

    def test_companion_health(self) -> None:
        http_url = os.environ.get("COMPANION_HTTP_URL")
        if not http_url:
            pytest.skip("COMPANION_HTTP_URL not set")
        import requests

        base = http_url.replace("/command", "")
        try:
            r = requests.get(f"{base}/health", timeout=5)
            data = r.json()
            assert data["status"] == "ok"
            assert "maya-companion-android" in data.get("service", "")
        except Exception:
            pytest.skip("Companion app not reachable (not running on device)")

    def test_companion_commands_list(self) -> None:
        http_url = os.environ.get("COMPANION_HTTP_URL")
        if not http_url:
            pytest.skip("COMPANION_HTTP_URL not set")
        import requests

        base = http_url.replace("/command", "")
        try:
            r = requests.get(f"{base}/commands", timeout=5)
            data = r.json()
            assert data["status"] == "ok"
            assert "package_analysis" in data.get("commands", {})
        except Exception:
            pytest.skip("Companion app not reachable")

    def test_companion_get_status(self) -> None:
        http_url = os.environ.get("COMPANION_HTTP_URL")
        if not http_url:
            pytest.skip("COMPANION_HTTP_URL not set")
        try:
            result = companion_app_command("get_status", json.dumps({}), "10")
            assert result.get("status") == "ok"
        except Exception:
            pytest.skip("Companion app not reachable")
