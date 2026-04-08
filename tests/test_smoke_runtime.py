from pathlib import Path

from maya.runtime.docker_runtime import DockerRuntime
from maya.telemetry.tracer import Tracer


def test_smoke_runtime_dryrun_and_tracer(tmp_path: Path) -> None:
    runtime = DockerRuntime(image="missing-image")
    info = runtime.create_sandbox(agent_id="agent1", auth_token="token", local_sources=[])
    assert info.agent_id == "agent1"
    assert info.server_url == "" or info.server_url.startswith("http")

    tracer = Tracer(run_dir=tmp_path / "run")
    tracer.log("smoke", {"ok": True})
    tracer.record_finding({"title": "x", "severity": "low", "category": "test", "description": "d"})
    tracer.record_api_endpoint({"method": "GET", "url": "https://example.com"})
    tracer.persist()

    assert (tmp_path / "run" / "trace.json").exists()
    assert (tmp_path / "run" / "report.md").exists()
