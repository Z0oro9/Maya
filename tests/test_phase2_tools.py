from types import SimpleNamespace

from maya.tools.apk_tool import (
    analyze_manifest,
    apktool_decompile,
    extract_strings,
    ios_class_dump,
    jadx_decompile,
    search_decompiled_code,
)
from maya.tools.device_bridge import device_list, device_shell
from maya.tools.frida_tool import frida_run_script


def _fake_completed(stdout: str = "ok", stderr: str = "", code: int = 0):
    return SimpleNamespace(stdout=stdout, stderr=stderr, returncode=code)


def test_device_shell_and_list(monkeypatch) -> None:
    def fake_run(cmd, text, capture_output, timeout):
        assert cmd[0] == "adb"
        return _fake_completed(stdout="device-output")

    monkeypatch.setattr("maya.tools.device_bridge.subprocess.run", fake_run)
    assert device_list()["stdout"] == "device-output"
    assert device_shell("id")["stdout"] == "device-output"


def test_apk_tools(monkeypatch, tmp_path) -> None:
    def fake_run(cmd, text, capture_output, timeout):
        assert cmd[0] in {"apktool", "jadx", "rg", "class-dump", "strings"}
        return _fake_completed(stdout="match")

    monkeypatch.setattr("maya.tools.apk_tool.subprocess.run", fake_run)
    out = apktool_decompile("sample.apk", str(tmp_path / "out"))
    assert out["exit_code"] == 0

    jadx_out = jadx_decompile("sample.apk", str(tmp_path / "jadx"))
    assert jadx_out["exit_code"] == 0

    search = search_decompiled_code(str(tmp_path), "token")
    assert search["stdout"] == "match"

    headers = ios_class_dump("app.bin", str(tmp_path / "headers"))
    assert headers["exit_code"] == 0

    strings_out = extract_strings("app.bin")
    assert strings_out["stdout"] == "match"


def test_analyze_manifest(tmp_path) -> None:
    manifest = tmp_path / "AndroidManifest.xml"
    manifest.write_text(
        """
        <manifest xmlns:android="http://schemas.android.com/apk/res/android" package="com.example.app">
          <uses-permission android:name="android.permission.INTERNET" />
          <application>
            <activity android:name=".MainActivity" android:exported="true" />
            <service android:name=".SyncService" android:exported="false" />
          </application>
        </manifest>
        """.strip(),
        encoding="utf-8",
    )

    result = analyze_manifest(str(manifest))
    assert result["package"] == "com.example.app"
    assert "android.permission.INTERNET" in result["permissions"]
    assert result["components"]["activity"][0]["name"] == ".MainActivity"


def test_frida_tools(monkeypatch) -> None:
    def fake_run(cmd, text, capture_output, timeout):
        assert cmd[0] == "frida"
        return _fake_completed(stdout="frida-ok")

    monkeypatch.setattr("maya.tools.frida_tool.subprocess.run", fake_run)

    run_result = frida_run_script("com.test.app", "send('x');")
    assert run_result["stdout"] == "frida-ok"
