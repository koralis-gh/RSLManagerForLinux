import json
import os
from pathlib import Path
from typing import Any

APP_NAME = "RSLManagerForLinux"
DEFAULT_CONFIG = {
    "game_exe_path": "",
    "wine_prefix": "~/.wine/RSLHelperForLinux",
}


def get_user_config_dir() -> Path:
    """Return a per-user config directory for the current platform."""
    if os.name == "nt":
        appdata = os.getenv("APPDATA")
        if not appdata:
            raise EnvironmentError("APPDATA is not set on Windows")
        return Path(appdata) / APP_NAME

    xdg_config_home = os.getenv("XDG_CONFIG_HOME")
    if xdg_config_home:
        return Path(xdg_config_home) / APP_NAME

    home = Path.home()
    return home / ".config" / APP_NAME


def get_config_path() -> Path:
    """Return the full path to the JSON config file."""
    return get_user_config_dir() / "config.json"


def ensure_config_path() -> Path:
    """Ensure the config directory exists and return the config file path."""
    config_dir = get_user_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "config.json"


def load_config() -> dict[str, Any]:
    """Load config from JSON, creating a default file if needed."""
    config_path = ensure_config_path()
    if not config_path.exists():
        save_config(DEFAULT_CONFIG)
        return dict(DEFAULT_CONFIG)

    try:
        with config_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (json.JSONDecodeError, OSError) as exc:
        raise ValueError(f"Unable to read config file: {config_path}") from exc

    if not isinstance(data, dict):
        raise ValueError(f"Config file {config_path} does not contain a JSON object. Delete the config file and restart the program.")

    merged = dict(DEFAULT_CONFIG)
    merged.update(data)
    return merged


def save_config(config: dict[str, Any]) -> None:
    """Write config data to the JSON file."""
    config_path = ensure_config_path()
    with config_path.open("w", encoding="utf-8") as handle:
        json.dump(config, handle, indent=2)
        handle.write("\n")


def validate_config(config: dict[str, Any]) -> tuple[bool, list[str]]:
    """Validate the minimal config fields and return a tuple of (valid, messages)."""
    messages: list[str] = []
    required_fields = ["game_exe_path", "wine_prefix"]

    for field in required_fields:
        value = config.get(field, "")
        if not isinstance(value, str) or not value.strip():
            messages.append(f"{field} must be set")

    game_exe_path = Path(config.get("game_exe_path", "")).expanduser()
    if game_exe_path and not game_exe_path.exists():
        messages.append("game_exe_path does not exist yet; it will be used for the first launch")

    wine_prefix = Path(config.get("wine_prefix", "")).expanduser()
    if wine_prefix and wine_prefix.exists() and not (wine_prefix / "drive_c").exists():
        messages.append("wine_prefix does not appear to be a valid Wine prefix")

    valid = len(messages) == 0
    return valid, messages


if __name__ == "__main__":
    path = get_config_path()
    print(f"Config path: {path}")
    config = load_config()
    print(json.dumps(config, indent=2))
