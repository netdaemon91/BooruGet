from __future__ import annotations

import configparser
import json
import os
import sys
from pathlib import Path

from .models import Credentials


DEFAULT_CONFIG = "booruget.ini"
APP_NAME = "BooruGet"


def user_config_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config"))
    return base / APP_NAME


def user_config_path() -> Path:
    return user_config_dir() / DEFAULT_CONFIG


def settings_path() -> Path:
    return user_config_dir() / "settings.json"


def resolve_config_path(path: str | Path = DEFAULT_CONFIG) -> Path:
    path = Path(path).expanduser()
    if str(path) != DEFAULT_CONFIG:
        return path
    legacy = Path.cwd() / DEFAULT_CONFIG
    if legacy.exists():
        return legacy
    return user_config_path()


def load_credentials(path: str | Path = DEFAULT_CONFIG) -> Credentials:
    cfg = configparser.ConfigParser()
    resolved = resolve_config_path(path)
    if resolved.exists():
        cfg.read(resolved, encoding="utf-8")
    return Credentials(
        danbooru_username=cfg.get("danbooru", "username", fallback="").strip(),
        danbooru_api_key=cfg.get("danbooru", "api_key", fallback="").strip(),
        gelbooru_user_id=cfg.get("gelbooru", "user_id", fallback="").strip(),
        gelbooru_api_key=cfg.get("gelbooru", "api_key", fallback="").strip(),
    )


def save_credentials(credentials: Credentials, path: str | Path = DEFAULT_CONFIG) -> Path:
    resolved = resolve_config_path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    cfg = configparser.ConfigParser()
    cfg["danbooru"] = {
        "username": credentials.danbooru_username,
        "api_key": credentials.danbooru_api_key,
    }
    cfg["gelbooru"] = {
        "user_id": credentials.gelbooru_user_id,
        "api_key": credentials.gelbooru_api_key,
    }
    with resolved.open("w", encoding="utf-8") as handle:
        cfg.write(handle)
    return resolved


def load_gui_settings() -> dict:
    path = settings_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def save_gui_settings(settings: dict) -> Path:
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)
    return path


def default_gui_download_dir() -> Path:
    downloads = Path.home() / "Downloads"
    if downloads.exists():
        return downloads / APP_NAME
    return Path.cwd() / "downloads"
