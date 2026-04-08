from pathlib import Path

from maya.skills import (
    generate_skills_description,
    get_available_skills,
    get_skill_frontmatter,
    list_available_skills_with_sources,
    load_skills,
    resolve_skill_dependencies,
    set_cli_skills_dir,
)


def _write_skill(base: Path, category: str, name: str, body: str) -> None:
    cat = base / category
    cat.mkdir(parents=True, exist_ok=True)
    (cat / f"{name}.md").write_text(body, encoding="utf-8")


def test_skills_precedence_cli_over_env_over_home(monkeypatch, tmp_path: Path) -> None:
    cli_dir = tmp_path / "cli_skills"
    env_dir = tmp_path / "env_skills"
    home_dir = tmp_path / "home" / ".maya" / "skills"

    _write_skill(env_dir, "custom", "dup", "---\nname: dup\n---\nfrom-env")
    _write_skill(home_dir, "custom", "dup", "---\nname: dup\n---\nfrom-home")
    _write_skill(cli_dir, "custom", "dup", "---\nname: dup\n---\nfrom-cli")

    monkeypatch.setenv("MAYA_SKILLS_DIR", str(env_dir))
    monkeypatch.setattr("maya.skills.Path.home", classmethod(lambda cls: tmp_path / "home"))

    set_cli_skills_dir(str(cli_dir))
    available = get_available_skills()
    assert "custom" in available
    assert "dup" in available["custom"]

    loaded = load_skills(["dup"])
    assert loaded["dup"].strip() == "from-cli"

    set_cli_skills_dir(None)


def test_generate_skills_description_uses_frontmatter(monkeypatch, tmp_path: Path) -> None:
    cli_dir = tmp_path / "cli_skills"
    _write_skill(
        cli_dir,
        "custom",
        "frontmatter_demo",
        "---\nname: frontmatter_demo\ndescription: loaded from metadata\n---\nbody",
    )

    set_cli_skills_dir(str(cli_dir))
    monkeypatch.delenv("MAYA_SKILLS_DIR", raising=False)
    monkeypatch.setattr("maya.skills.Path.home", classmethod(lambda cls: tmp_path / "home"))

    description = generate_skills_description()
    assert "custom/frontmatter_demo: loaded from metadata" in description

    set_cli_skills_dir(None)


def test_hidden_skill_categories_are_not_listed(monkeypatch, tmp_path: Path) -> None:
    cli_dir = tmp_path / "cli_skills"
    _write_skill(cli_dir, "scan_modes", "quick", "---\nname: quick\ndescription: hidden\n---\nbody")
    _write_skill(cli_dir, "coordination", "root_strategy", "---\nname: root_strategy\ndescription: hidden\n---\nbody")
    _write_skill(cli_dir, "visible", "demo", "---\nname: demo\ndescription: visible\n---\nbody")

    set_cli_skills_dir(str(cli_dir))
    monkeypatch.delenv("MAYA_SKILLS_DIR", raising=False)
    monkeypatch.setattr("maya.skills.Path.home", classmethod(lambda cls: tmp_path / "home"))

    available = get_available_skills()
    listed = list_available_skills_with_sources()

    assert "visible" in available
    assert "scan_modes" not in available
    assert "coordination" not in available
    assert all(entry["category"] not in {"scan_modes", "coordination"} for entry in listed)

    set_cli_skills_dir(None)


def test_resolve_skill_dependencies_recursive(monkeypatch, tmp_path: Path) -> None:
    cli_dir = tmp_path / "cli_skills"
    _write_skill(
        cli_dir,
        "tools",
        "dep_c",
        "---\nname: dep_c\ndescription: leaf\n---\nleaf",
    )
    _write_skill(
        cli_dir,
        "tools",
        "dep_b",
        "---\nname: dep_b\ndescription: mid\nrequires:\n  - dep_c\n---\nmid",
    )
    _write_skill(
        cli_dir,
        "vulnerabilities",
        "dep_a",
        "---\nname: dep_a\ndescription: root\nrequires:\n  - dep_b\n---\nroot",
    )

    set_cli_skills_dir(str(cli_dir))
    monkeypatch.delenv("MAYA_SKILLS_DIR", raising=False)
    monkeypatch.setattr("maya.skills.Path.home", classmethod(lambda cls: tmp_path / "home"))

    resolved = resolve_skill_dependencies(["dep_a"])
    assert resolved == ["dep_c", "dep_b", "dep_a"]

    loaded = load_skills(["dep_a"])
    assert list(loaded.keys()) == ["dep_c", "dep_b", "dep_a"]

    meta = get_skill_frontmatter("dep_a")
    assert meta.get("name") == "dep_a"

    set_cli_skills_dir(None)
