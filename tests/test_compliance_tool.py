from __future__ import annotations

from types import SimpleNamespace

from maya.tools.compliance_tool import (
    _COMPLIANCE_SCRIPTS,
    list_compliance_checks,
    run_compliance_check,
    run_compliance_scan,
)


def _fake_completed(stdout: str = "ok", stderr: str = "", code: int = 0):
    return SimpleNamespace(stdout=stdout, stderr=stderr, returncode=code)


# ---------------------------------------------------------------------------
# list_compliance_checks
# ---------------------------------------------------------------------------


def test_list_compliance_checks_returns_all() -> None:
    result = list_compliance_checks()
    assert result["status"] == "ok"
    assert result["total_checks"] == len(_COMPLIANCE_SCRIPTS)
    assert "device_integrity" in result["categories"]
    assert "encryption" in result["categories"]
    for check_id in _COMPLIANCE_SCRIPTS:
        assert check_id in result["checks"]


# ---------------------------------------------------------------------------
# run_compliance_check — single check
# ---------------------------------------------------------------------------


def test_run_compliance_check_unknown() -> None:
    result = run_compliance_check(package_name="com.test", check_name="nonexistent")
    assert "error" in result
    assert "Unknown check" in result["error"]


def test_run_compliance_check_success(monkeypatch) -> None:
    monkeypatch.setattr(
        "maya.tools.compliance_tool.subprocess.run",
        lambda cmd, text, capture_output, timeout: _fake_completed(
            stdout='[{"type":"secure_boot_check","status":"ok"}]'
        ),
    )
    result = run_compliance_check(package_name="com.test", check_name="secure_boot")
    assert result["status"] == "ok"
    assert result["check"] == "secure_boot"
    assert result["category"] == "device_integrity"
    assert result["exit_code"] == 0


def test_run_compliance_check_script_missing(monkeypatch, tmp_path) -> None:
    # Point to a non-existent script path
    original = _COMPLIANCE_SCRIPTS["secure_boot"]["script"]
    monkeypatch.setitem(_COMPLIANCE_SCRIPTS["secure_boot"], "script", tmp_path / "nonexistent.js")
    result = run_compliance_check(package_name="com.test", check_name="secure_boot")
    assert "error" in result
    monkeypatch.setitem(_COMPLIANCE_SCRIPTS["secure_boot"], "script", original)


# ---------------------------------------------------------------------------
# run_compliance_scan — full and selective
# ---------------------------------------------------------------------------


def test_run_compliance_scan_invalid_category() -> None:
    result = run_compliance_scan(package_name="com.test", test_cases="invalid_category")
    assert "error" in result


def test_run_compliance_scan_all(monkeypatch) -> None:
    monkeypatch.setattr(
        "maya.tools.compliance_tool.subprocess.run",
        lambda cmd, text, capture_output, timeout: _fake_completed(stdout="ok"),
    )
    result = run_compliance_scan(package_name="com.test", test_cases="all")
    assert result["status"] == "ok"
    assert result["total_tests"] == len(_COMPLIANCE_SCRIPTS)
    assert result["executed"] + result["execution_failed"] + result["errors"] == result["total_tests"]
    assert "summary" in result


def test_run_compliance_scan_category(monkeypatch) -> None:
    monkeypatch.setattr(
        "maya.tools.compliance_tool.subprocess.run",
        lambda cmd, text, capture_output, timeout: _fake_completed(stdout="ok"),
    )
    result = run_compliance_scan(package_name="com.test", test_cases="device_integrity")
    assert result["status"] == "ok"
    assert result["total_tests"] == 3  # secure_boot, emulator_detection, root_detection


def test_run_compliance_scan_individual(monkeypatch) -> None:
    monkeypatch.setattr(
        "maya.tools.compliance_tool.subprocess.run",
        lambda cmd, text, capture_output, timeout: _fake_completed(stdout="ok"),
    )
    result = run_compliance_scan(package_name="com.test", test_cases="secure_boot,ssl_pinning")
    assert result["status"] == "ok"
    assert result["total_tests"] == 2


def test_run_compliance_scan_timeout(monkeypatch) -> None:
    import subprocess as sp

    def _timeout_run(cmd, text, capture_output, timeout):
        raise sp.TimeoutExpired(cmd, timeout)

    monkeypatch.setattr("maya.tools.compliance_tool.subprocess.run", _timeout_run)
    result = run_compliance_scan(package_name="com.test", test_cases="secure_boot", timeout="5")
    assert result["status"] == "ok"
    assert result["errors"] == 1


# ---------------------------------------------------------------------------
# Script file existence
# ---------------------------------------------------------------------------


def test_all_compliance_scripts_exist() -> None:
    """Verify all referenced Frida scripts actually exist on disk."""
    for test_id, spec in _COMPLIANCE_SCRIPTS.items():
        script_path = spec["script"]
        assert script_path.exists(), f"Missing script for '{test_id}': {script_path}"
