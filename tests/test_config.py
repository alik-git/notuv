"""Tests for notuv config parsing."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from notuv.config import NotuvError, load_config

if TYPE_CHECKING:
    from pathlib import Path


def write_config(root: Path, text: str) -> None:
    """Write a notuv config for a test repo."""
    (root / "notuv.toml").write_text(text, encoding="utf-8")


def write_named_config(root: Path, name: str, text: str) -> None:
    """Write a named notuv config for a test workset."""
    (root / name).write_text(text, encoding="utf-8")


def test_load_minimal_config(tmp_path: Path) -> None:
    """Load the smallest supported config."""
    write_config(
        tmp_path,
        """
        [python]
        base_conda_env = "example"

        [editables]
        packages = ["."]
        """,
    )

    config = load_config(tmp_path)

    assert config.project_root == tmp_path
    assert config.entry_config_path == tmp_path / "notuv.toml"
    assert config.config_path == tmp_path / "notuv.toml"
    assert config.config_root == tmp_path
    assert config.env_root == tmp_path
    assert config.command_cwd == tmp_path
    assert config.config_kind == "repo"
    assert config.uses_shared_venv is False
    assert config.base_conda_env == "example"
    assert config.venv == tmp_path / ".venv"
    assert config.editable_packages == (tmp_path,)
    assert config.install_editable_deps is False


def test_editables_can_point_to_sibling_worktrees(tmp_path: Path) -> None:
    """Allow editable packages outside the owning git root."""
    write_config(
        tmp_path,
        """
        [python]
        base_conda_env = "example"

        [editables]
        packages = ["../sibling"]
        """,
    )

    config = load_config(tmp_path)

    assert config.editable_packages == ((tmp_path / "../sibling").resolve(),)


def test_editables_can_use_absolute_paths(tmp_path: Path) -> None:
    """Allow editable packages to point at canonical checkouts."""
    package = tmp_path / "repos" / "package"
    write_config(
        tmp_path,
        f"""
        [python]
        base_conda_env = "example"

        [editables]
        packages = [{str(package)!r}]
        """,
    )

    config = load_config(tmp_path)

    assert config.editable_packages == (package,)


def test_editables_can_use_tilde_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Allow editable packages to use user-home anchored paths."""
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    write_config(
        tmp_path,
        """
        [python]
        base_conda_env = "example"

        [editables]
        packages = ["~/repos/package"]
        """,
    )

    config = load_config(tmp_path)

    assert config.editable_packages == (home / "repos" / "package",)


def test_venv_must_stay_inside_git_root(tmp_path: Path) -> None:
    """Reject venv paths outside the current git root."""
    write_config(
        tmp_path,
        """
        [python]
        base_conda_env = "example"
        venv = "../outside"
        """,
    )

    with pytest.raises(NotuvError, match="python.venv must stay inside"):
        load_config(tmp_path)


def test_absolute_venv_can_point_inside_repo_root(tmp_path: Path) -> None:
    """Allow absolute venv paths if they stay inside the env root."""
    venv = tmp_path / ".notuv" / "repo" / ".venv"
    write_config(
        tmp_path,
        f"""
        [python]
        base_conda_env = "example"
        venv = {str(venv)!r}
        """,
    )

    config = load_config(tmp_path)

    assert config.venv == venv


def test_pointer_config_loads_stack_config(tmp_path: Path) -> None:
    """Load an explicit stack config from a repo-local pointer config."""
    workset = tmp_path / "worksets" / "dev-1"
    repo = workset / "minerva_lab"
    repo.mkdir(parents=True)
    write_config(
        repo,
        """
        [notuv]
        extends = "../notuv.mlab.toml"
        """,
    )
    write_named_config(
        workset,
        "notuv.mlab.toml",
        """
        [notuv]
        kind = "stack"

        [python]
        base_conda_env = "mlab_shared"
        venv = ".notuv/mlab/.venv"

        [editables]
        packages = ["minerva_lab/source/minerva_lab"]
        """,
    )

    config = load_config(repo)

    assert config.project_root == repo
    assert config.entry_config_path == repo / "notuv.toml"
    assert config.config_path == workset / "notuv.mlab.toml"
    assert config.config_root == workset
    assert config.env_root == workset
    assert config.command_cwd == repo
    assert config.config_kind == "stack"
    assert config.uses_shared_venv is True
    assert config.base_conda_env == "mlab_shared"
    assert config.venv == workset / ".notuv" / "mlab" / ".venv"
    assert config.editable_packages == (repo / "source" / "minerva_lab",)


def test_stack_config_allows_absolute_venv_inside_stack_root(tmp_path: Path) -> None:
    """Allow absolute stack venv paths only inside the stack config root."""
    workset = tmp_path / "worksets" / "dev-1"
    repo = workset / "minerva_lab"
    repo.mkdir(parents=True)
    venv = workset / ".notuv" / "mlab" / ".venv"
    write_config(
        repo,
        """
        [notuv]
        extends = "../notuv.mlab.toml"
        """,
    )
    write_named_config(
        workset,
        "notuv.mlab.toml",
        f"""
        [notuv]
        kind = "stack"

        [python]
        base_conda_env = "mlab_shared"
        venv = {str(venv)!r}
        """,
    )

    config = load_config(repo)

    assert config.venv == venv


def test_stack_config_rejects_absolute_venv_outside_stack_root(
    tmp_path: Path,
) -> None:
    """Reject stack venv paths that escape the stack config root."""
    workset = tmp_path / "worksets" / "dev-1"
    repo = workset / "minerva_lab"
    repo.mkdir(parents=True)
    write_config(
        repo,
        """
        [notuv]
        extends = "../notuv.mlab.toml"
        """,
    )
    write_named_config(
        workset,
        "notuv.mlab.toml",
        f"""
        [notuv]
        kind = "stack"

        [python]
        base_conda_env = "mlab_shared"
        venv = {str(tmp_path / "outside" / ".venv")!r}
        """,
    )

    with pytest.raises(NotuvError, match="python.venv must stay inside"):
        load_config(repo)


def test_pointer_config_rejects_extra_sections(tmp_path: Path) -> None:
    """Keep repo-local pointer configs pointer-only in v1."""
    workset = tmp_path / "worksets" / "dev-1"
    repo = workset / "minerva_lab"
    repo.mkdir(parents=True)
    write_config(
        repo,
        """
        [notuv]
        extends = "../notuv.mlab.toml"

        [python]
        base_conda_env = "example"
        """,
    )

    with pytest.raises(NotuvError, match="unsupported keys: python"):
        load_config(repo)


def test_pointer_config_requires_stack_kind(tmp_path: Path) -> None:
    """Require explicit stack configs for repo-local extends."""
    workset = tmp_path / "worksets" / "dev-1"
    repo = workset / "minerva_lab"
    repo.mkdir(parents=True)
    write_config(
        repo,
        """
        [notuv]
        extends = "../notuv.mlab.toml"
        """,
    )
    write_named_config(
        workset,
        "notuv.mlab.toml",
        """
        [notuv]
        kind = "repo"

        [python]
        base_conda_env = "example"
        """,
    )

    with pytest.raises(NotuvError, match='kind must be "stack"'):
        load_config(repo)


def test_pointer_config_rejects_chained_extends(tmp_path: Path) -> None:
    """Reject chained extends so config behavior stays explicit."""
    workset = tmp_path / "worksets" / "dev-1"
    repo = workset / "minerva_lab"
    repo.mkdir(parents=True)
    write_config(
        repo,
        """
        [notuv]
        extends = "../notuv.mlab.toml"
        """,
    )
    write_named_config(
        workset,
        "notuv.mlab.toml",
        """
        [notuv]
        kind = "stack"
        extends = "./other.toml"

        [python]
        base_conda_env = "example"
        """,
    )

    with pytest.raises(NotuvError, match="unsupported keys: extends"):
        load_config(repo)


def test_pointer_config_reports_missing_target(tmp_path: Path) -> None:
    """Fail clearly when an explicit extends target is missing."""
    repo = tmp_path / "repo"
    repo.mkdir()
    write_config(
        repo,
        """
        [notuv]
        extends = "../missing.toml"
        """,
    )

    with pytest.raises(NotuvError, match="target does not exist"):
        load_config(repo)


def test_missing_config_has_clear_error(tmp_path: Path) -> None:
    """Explain how to create the required config."""
    with pytest.raises(NotuvError, match="missing notuv.toml"):
        load_config(tmp_path)
