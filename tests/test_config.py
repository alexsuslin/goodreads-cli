from __future__ import annotations

from pathlib import Path

import pytest

from goodreads_cli.config import ConfigurationError, Settings


def clear_goodreads_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "GOODREADS_EMAIL",
        "GOODREADS_PASSWORD",
        "GOODREADS_CLI_EMAIL",
        "GOODREADS_CLI_PASSWORD",
        "GOODREADS_SESSION_FILE",
        "GOODREADS_CONFIG_FILE",
        "XDG_CONFIG_HOME",
        "HOME",
        "email",
        "password",
        "EMAIL",
        "PASSWORD",
    ):
        monkeypatch.delenv(key, raising=False)


def test_settings_accept_cli_env_aliases(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clear_goodreads_env(monkeypatch)
    workdir = tmp_path / "workspace"
    workdir.mkdir()
    monkeypatch.chdir(workdir)
    monkeypatch.setenv("GOODREADS_CLI_EMAIL", "cli@example.com")
    monkeypatch.setenv("GOODREADS_CLI_PASSWORD", "cli-secret")

    settings = Settings.from_env()

    assert settings.email == "cli@example.com"
    assert settings.password == "cli-secret"


def test_cwd_dotenv_overrides_xdg_dotenv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    clear_goodreads_env(monkeypatch)
    config_home = tmp_path / "config-home"
    xdg_dotenv = config_home / "goodreads-cli" / ".env"
    xdg_dotenv.parent.mkdir(parents=True)
    xdg_dotenv.write_text(
        "GOODREADS_EMAIL=xdg@example.com\nGOODREADS_PASSWORD=xdg-secret\n",
        encoding="utf-8",
    )

    workdir = tmp_path / "workspace"
    workdir.mkdir()
    (workdir / ".env").write_text(
        "GOODREADS_EMAIL=local@example.com\nGOODREADS_PASSWORD=local-secret\n",
        encoding="utf-8",
    )

    monkeypatch.chdir(workdir)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))

    settings = Settings.from_env()

    assert settings.email == "local@example.com"
    assert settings.password == "local-secret"


def test_settings_load_presets_from_toml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    clear_goodreads_env(monkeypatch)
    config_home = tmp_path / "config-home"
    config_file = config_home / "goodreads-cli" / "config.toml"
    config_file.parent.mkdir(parents=True)
    config_file.write_text(
        '[presets.sci-pop]\n'
        'tags = ["ru", "audio", "wishlist", "sci-pop", "to-read"]\n',
        encoding="utf-8",
    )
    dotenv = config_home / "goodreads-cli" / ".env"
    dotenv.write_text(
        "GOODREADS_EMAIL=reader@example.com\nGOODREADS_PASSWORD=secret\n",
        encoding="utf-8",
    )
    workdir = tmp_path / "workspace"
    workdir.mkdir()

    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))
    monkeypatch.chdir(workdir)

    settings = Settings.from_env()

    assert settings.presets["sci-pop"] == ["ru", "audio", "wishlist", "sci-pop", "to-read"]
    assert settings.config_file == config_file


def test_settings_respect_explicit_session_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    clear_goodreads_env(monkeypatch)
    session_file = tmp_path / "custom-session.json"
    monkeypatch.setenv("GOODREADS_SESSION_FILE", str(session_file))
    monkeypatch.setenv("GOODREADS_EMAIL", "reader@example.com")
    monkeypatch.setenv("GOODREADS_PASSWORD", "secret")

    settings = Settings.from_env()

    assert settings.session_file == session_file


def test_settings_raise_for_missing_credentials(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clear_goodreads_env(monkeypatch)
    workdir = tmp_path / "workspace"
    workdir.mkdir()
    monkeypatch.chdir(workdir)

    with pytest.raises(ConfigurationError, match="Missing required environment variables"):
        Settings.from_env()
