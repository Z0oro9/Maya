import json
import os
import shutil
import subprocess

import pytest

from maya.tools.device_bridge import companion_app_command, device_list

requires_device = pytest.mark.skipif(
    os.environ.get("MAYA_RUN_DEVICE_TESTS") != "1",
    reason="Set MAYA_RUN_DEVICE_TESTS=1 to run real device-backed integration tests.",
)


@requires_device
@pytest.mark.integration
def test_integration_adb_list_real_device() -> None:
    if shutil.which("adb") is None:
        pytest.skip("adb binary not found")

    result = device_list()
    assert result["exit_code"] == 0
    assert "List of devices attached" in result["stdout"]


@requires_device
@pytest.mark.integration
def test_integration_companion_protocol_real() -> None:
    ws_url = os.environ.get("COMPANION_WS_URL")
    http_url = os.environ.get("COMPANION_HTTP_URL")
    if not ws_url and not http_url:
        pytest.skip("Set COMPANION_WS_URL or COMPANION_HTTP_URL for companion protocol integration")

    result = companion_app_command("get_status", json.dumps({}), "10")
    assert result["status"] == "ok"


@requires_device
@pytest.mark.integration
def test_integration_frida_connectivity_real() -> None:
    if shutil.which("frida-ps") is None:
        pytest.skip("frida-ps binary not found")

    host = os.environ.get("FRIDA_HOST")
    cmd = ["frida-ps", "-H", host] if host else ["frida-ps", "-U"]
    proc = subprocess.run(cmd, text=True, capture_output=True, timeout=20)
    assert proc.returncode == 0
