"""Configuration loading for Goodreads CLI."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


class ConfigurationError(ValueError):
    """Raised when required settings are missing."""


@dataclass(slots=True)
class Settings:
    email: str
    password: str
    session_file: Path
    config_file: Path | None
    presets: dict[str, list[str]] = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> "Settings":
        dotenv_values = _load_dotenv_values()
        email = _first_value(
            "GOODREADS_EMAIL",
            dotenv_values,
            aliases=("GOODREADS_CLI_EMAIL", "email", "EMAIL"),
        )
        password = _first_value(
            "GOODREADS_PASSWORD",
            dotenv_values,
            aliases=("GOODREADS_CLI_PASSWORD", "password", "PASSWORD"),
        )
        if not email or not password:
            raise ConfigurationError(
                "Missing required environment variables: GOODREADS_EMAIL, GOODREADS_PASSWORD"
            )

        config_file = _preset_config_path()
        presets = _load_presets(config_file) if config_file else {}
        return cls(
            email=email,
            password=password,
            session_file=_session_file_path(),
            config_file=config_file,
            presets=presets,
        )


def _load_dotenv_values() -> dict[str, str]:
    values: dict[str, str] = {}
    for path in _dotenv_paths():
        values.update(_load_dotenv(path))
    return values


def _dotenv_paths() -> list[Path]:
    return [*_xdg_candidates(".env"), Path.cwd() / ".env"]


def _preset_config_path() -> Path | None:
    explicit = os.getenv("GOODREADS_CONFIG_FILE", "").strip()
    candidates = [Path(explicit)] if explicit else [Path.cwd() / "goodreads.toml", *_xdg_candidates("config.toml")]
    for path in candidates:
        if path.exists():
            return path
    return None


def _session_file_path() -> Path:
    explicit = os.getenv("GOODREADS_SESSION_FILE", "").strip()
    if explicit:
        return Path(explicit)
    return _xdg_candidates("session.json")[0]


def _xdg_candidates(filename: str) -> list[Path]:
    candidates: list[Path] = []
    config_home = os.getenv("XDG_CONFIG_HOME", "").strip()
    if config_home:
        candidates.append(Path(config_home) / "goodreads-cli" / filename)
    candidates.append(_home_config_dir() / filename)
    return candidates


def _home_config_dir() -> Path:
    home = os.getenv("HOME", "").strip()
    return (Path(home) if home else Path.home()) / ".config" / "goodreads-cli"


def _load_presets(path: Path) -> dict[str, list[str]]:
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    presets: dict[str, list[str]] = {}
    for name, payload in raw.get("presets", {}).items():
        tags = payload.get("tags", [])
        presets[name] = [str(tag).strip() for tag in tags if str(tag).strip()]
    return presets


def _first_value(primary: str, dotenv_values: dict[str, str], aliases: tuple[str, ...] = ()) -> str:
    for key in (primary, *aliases):
        env_value = os.getenv(key)
        if env_value and env_value.strip():
            return env_value.strip()
        file_value = dotenv_values.get(key)
        if file_value and file_value.strip():
            return file_value.strip()
    return ""


def _load_dotenv(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("\"'")
    return values
