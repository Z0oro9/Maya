"""Live integration test: companion server running on device via app_process.

Requires:
  - Companion server running on device (port 9999)
  - ADB port forwarding: adb forward tcp:9999 tcp:9999
  - MAYA_RUN_DEVICE_TESTS=1

Run:
    MAYA_RUN_DEVICE_TESTS=1 python -m pytest tests/test_companion_live.py -v
"""

from __future__ import annotations

import os

import pytest
import requests

BASE = os.environ.get("COMPANION_HTTP_URL", "http://127.0.0.1:9999/command").replace("/command", "")
CMD = f"{BASE}/command"
TIMEOUT = 60

skip_no_device = pytest.mark.skipif(
    os.environ.get("MAYA_RUN_DEVICE_TESTS") != "1",
    reason="MAYA_RUN_DEVICE_TESTS not set",
)


@pytest.fixture(autouse=True)
def _require_companion():
    """Skip test at runtime if companion is not reachable."""
    try:
        r = requests.get(f"{BASE}/health", timeout=5)
        if r.status_code != 200:
            pytest.skip("Companion server not responding with 200")
    except Exception:
        pytest.skip("Companion server not reachable at port 9999")


def cmd(command: str, params: dict | None = None) -> dict:
    r = requests.post(CMD, json={"id": "test", "command": command, "params": params or {}}, timeout=TIMEOUT)
    return r.json()


@skip_no_device
class TestCompanionHealth:
    def test_health(self) -> None:
        r = requests.get(f"{BASE}/health", timeout=5)
        d = r.json()
        assert d["status"] == "ok"
        assert d["service"] == "maya-companion-android"
        assert d["version"] == "2.0.0"

    def test_get_status(self) -> None:
        d = cmd("get_status")
        assert d["status"] == "success"
        assert d["data"]["platform"] == "android"


@skip_no_device
class TestDeviceInfo:
    def test_device_info(self) -> None:
        d = cmd("device_info")
        assert d["status"] == "success"
        assert d["data"]["model"] != ""
        assert d["data"]["android_version"] != ""
        assert int(d["data"]["sdk_version"]) >= 21

    def test_root_check(self) -> None:
        d = cmd("root_check")
        assert d["status"] == "success"
        assert "su_binary" in d["data"]

    def test_network_info(self) -> None:
        d = cmd("network_info")
        assert d["status"] == "success"

    def test_process_list(self) -> None:
        d = cmd("ps")
        assert d["status"] == "success"


@skip_no_device
class TestPackageAnalysis:
    def test_package_list(self) -> None:
        d = cmd("package_list", {"flags": "-3"})
        assert d["status"] == "success"
        assert int(d["data"]["count"]) > 0

    def test_package_info(self) -> None:
        d = cmd("package_info", {"package": "android"})
        assert d["status"] == "success"
        assert "apk_path" in d["data"]
        assert d["data"]["apk_path"] != ""

    def test_attack_surface(self) -> None:
        d = cmd("attack_surface", {"package": "com.sec.android.app.sbrowser"})
        assert d["status"] == "success"
        assert "exported_activities" in d["data"]
        assert "is_debuggable" in d["data"]

    def test_package_permissions(self) -> None:
        d = cmd("app_permissions", {"package": "com.sec.android.app.sbrowser"})
        assert d["status"] == "success"

    def test_package_missing_param(self) -> None:
        d = cmd("package_info", {})
        assert d["status"] == "error"
        assert "missing" in (d.get("error") or "").lower()


@skip_no_device
class TestActivityInspector:
    def test_activity_browsable(self) -> None:
        d = cmd("activity_browsable", {"package": "com.sec.android.app.sbrowser"})
        assert d["status"] == "success"

    def test_activity_info(self) -> None:
        d = cmd("activity_info", {"package": "com.sec.android.app.sbrowser"})
        assert d["status"] == "success"


@skip_no_device
class TestContentProvider:
    def test_provider_query_settings(self) -> None:
        d = cmd("provider_query", {"uri": "content://settings/system"})
        assert d["status"] == "success"
        assert "rows" in d["data"] or "result" in d["data"] or "stdout" in d["data"]


@skip_no_device
class TestVulnerabilityScanner:
    def test_scan_debuggable(self) -> None:
        d = cmd("scan_debuggable")
        assert d["status"] == "success"

    def test_scan_full(self) -> None:
        d = cmd("scan_full", {"package": "com.sec.android.app.sbrowser"})
        assert d["status"] == "success"


@skip_no_device
class TestShellExecution:
    def test_run_shell(self) -> None:
        d = cmd("run_shell", {"command": "echo hello_mobsec"})
        assert d["status"] == "success"
        assert "hello_mobsec" in d["data"].get("stdout", "")

    def test_collect_logs(self) -> None:
        d = cmd("collect_logs", {"lines": "5"})
        # May fail without root; just verify we get a response
        assert d["status"] in ("success", "error")
