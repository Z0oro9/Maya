from pathlib import Path

from click.testing import CliRunner

from maya.main import cli


def test_smoke_cli_run(tmp_path: Path) -> None:
    runner = CliRunner()
    out_dir = tmp_path / "run1"
    result = runner.invoke(
        cli,
        [
            "--target",
            "com.test.smoke",
            "--task",
            "smoke",
            "--model",
            "mock/local",
            "--output-dir",
            str(out_dir),
            "--skills",
            "ssl_pinning_bypass",
        ],
    )
    assert result.exit_code == 0
    assert "Status:" in (result.output or "")
    assert (out_dir / "report.md").exists()


def test_cli_list_skills_mode() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["--list-skills"])
    assert result.exit_code == 0
    assert "Available skills:" in result.output
