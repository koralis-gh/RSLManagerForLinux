import json
import os
import shutil
import tarfile
import urllib.request
from pathlib import Path
from typing import Any, Callable

APP_NAME = "RSLManagerForLinux"
DEFAULT_CONFIG = {
    "game_exe_path": "",
    "prefix_path": "~/.RSLManagerForLinux/prefixes/raid1",
}

PROTON_GE_URL = "https://github.com/GloriousEggroll/proton-ge-custom/releases/download/GE-Proton10-10/GE-Proton10-10.tar.gz"


def get_app_root() -> Path:
    return Path.home() / f".{APP_NAME}"


def get_proton_root() -> Path:
    return get_app_root() / "proton"


def get_prefix_root() -> Path:
    return get_app_root() / "prefixes"


def get_default_prefix() -> Path:
    return get_prefix_root() / "raid1"


def get_repo_root() -> Path:
    return Path(__file__).resolve().parent


def get_app_log_path() -> Path:
    return get_repo_root() / "logs" / f"{APP_NAME}.log"


def get_user_config_dir() -> Path:
    """Return the per-user app directory for Linux or Windows."""
    if os.name == "nt":
        appdata = os.getenv("APPDATA")
        if not appdata:
            raise EnvironmentError("APPDATA is not set on Windows")
        return Path(appdata) / APP_NAME

    home = Path.home()
    return home / f".{APP_NAME}"


def get_old_config_path() -> Path:
    return Path.home() / ".config" / APP_NAME / "config.json"


def migrate_config_file() -> None:
    new_path = get_config_path()
    old_path = get_old_config_path()
    if not new_path.exists() and old_path.exists():
        new_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(old_path, new_path)


def get_config_path() -> Path:
    """Return the full path to the JSON config file."""
    return get_user_config_dir() / "config.json"


def ensure_config_path() -> Path:
    """Ensure the config directory exists and return the config file path."""
    migrate_config_file()
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

    if "prefix_path" not in data and "wine_prefix" in data:
        data["prefix_path"] = data["wine_prefix"]

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

    game_exe_path = config.get("game_exe_path", "")
    if not isinstance(game_exe_path, str) or not game_exe_path.strip():
        messages.append("game_exe_path must be set")
    else:
        game_exe_expanded = Path(game_exe_path).expanduser()
        if not game_exe_expanded.exists():
            messages.append("game_exe_path does not exist yet; it will be used for the first launch")

    prefix_path = config.get("prefix_path", "")
    if not isinstance(prefix_path, str) or not prefix_path.strip():
        messages.append("prefix_path must be set")

    valid = len(messages) == 0 or all("does not exist yet" in msg for msg in messages)
    return valid, messages


# Proton management
def get_steam_dummy_path() -> Path:
    return get_app_root() / "steam-dummy"


def _find_proton_bin() -> Path | None:
    """Find the Proton binary under the configured proton root."""
    proton_root = get_proton_root()
    if not proton_root.exists():
        return None

    candidate = proton_root / "proton"
    if candidate.exists() and os.access(candidate, os.X_OK):
        return candidate

    for path in proton_root.rglob("proton"):
        if path.is_file() and os.access(path, os.X_OK):
            return path

    return None


def get_proton_install_status() -> dict[str, str | bool]:
    """Return the current Proton installation status and relevant paths."""
    proton_root = get_proton_root()
    tarball_path = get_app_root() / "GE-Proton10-10.tar.gz"
    proton_bin = _find_proton_bin()
    steam_dummy_path = get_steam_dummy_path()

    return {
        "proton_root": str(proton_root),
        "tarball_path": str(tarball_path),
        "tarball_exists": tarball_path.exists(),
        "proton_installed": proton_bin is not None,
        "proton_bin": str(proton_bin) if proton_bin else str(proton_root / "proton"),
        "steam_dummy_path": str(steam_dummy_path),
        "steam_dummy_exists": steam_dummy_path.exists(),
    }


def get_proton_install_message(prefix_path: str | None = None) -> str:
    status = get_proton_install_status()
    prefix_value = prefix_path or str(get_default_prefix())

    lines: list[str] = []
    lines.append("Proton GE install status:")
    lines.append("")

    lines.append(f"[{'x' if status['tarball_exists'] else ' '}] Proton tarball downloaded to {status['tarball_path']}")
    lines.append(f"[{'x' if status['proton_installed'] else ' '}] Proton binary found and executable at {status['proton_bin']}")
    lines.append(f"[{'x' if status['steam_dummy_exists'] else ' '}] Steam dummy path exists at {status['steam_dummy_path']}")

    lines.append("")
    lines.append("Next launch environment:")
    lines.append(f"  STEAM_COMPAT_DATA_PATH={prefix_value}")
    lines.append(f"  STEAM_COMPAT_CLIENT_INSTALL_PATH={status['steam_dummy_path']}")
    lines.append(f"  Proton binary: {status['proton_bin']}")

    if not status['proton_installed']:
        lines.append("")
        lines.append("Install progress:")
        lines.append(f" - Proton tarball {'exists' if status['tarball_exists'] else 'is missing'}")
        lines.append(f" - Extracted to {status['proton_root']} {'yes' if status['proton_installed'] else 'no'}")
        lines.append(f" - Steam dummy folder {'exists' if status['steam_dummy_exists'] else 'needs creation'}")

    return "\n".join(lines)


def check_proton_available() -> bool:
    """Check if Proton GE is installed and ready to be used for launches."""
    return _find_proton_bin() is not None


def _download_file(url: str, destination: Path, progress_callback: Callable[[int, int], None] | None = None) -> None:
    """Download a file from URL with optional progress reporting."""
    with urllib.request.urlopen(url) as response, destination.open("wb") as out_file:
        total = int(response.getheader("Content-Length", "0") or "0")
        downloaded = 0
        chunk_size = 8192

        while True:
            chunk = response.read(chunk_size)
            if not chunk:
                break
            out_file.write(chunk)
            downloaded += len(chunk)
            if progress_callback is not None:
                progress_callback(downloaded, total)

    if progress_callback is not None and total > 0:
        progress_callback(downloaded, total)


def _extract_tarball(tarball_path: Path, destination: Path) -> None:
    """Extract a tarball to a destination directory, stripping the top-level folder."""
    with tarfile.open(tarball_path, "r:gz") as archive:
        for member in archive.getmembers():
            original_name = member.name
            if original_name.startswith("./"):
                original_name = original_name[2:]
            if original_name.startswith("GE-Proton10-10/"):
                member.name = original_name[len("GE-Proton10-10/"):]
            else:
                member.name = original_name

            if not member.name:
                continue

            archive.extract(member, destination)


def install_proton(progress_callback: Callable[[int, int], None] | None = None) -> tuple[bool, str]:
    """Download and install Proton GE. Returns (success, message)."""
    proton_root = get_proton_root()
    app_root = get_app_root()
    proton_root.mkdir(parents=True, exist_ok=True)
    app_root.mkdir(parents=True, exist_ok=True)
    get_steam_dummy_path().mkdir(parents=True, exist_ok=True)

    try:
        tarball_path = app_root / "GE-Proton10-10.tar.gz"
        if tarball_path.exists() and tarball_path.is_file():
            if progress_callback is not None:
                file_size = tarball_path.stat().st_size
                progress_callback(file_size, file_size)
            _extract_tarball(tarball_path, proton_root)
        else:
            _download_file(PROTON_GE_URL, tarball_path, progress_callback=progress_callback)
            _extract_tarball(tarball_path, proton_root)

        proton_bin = _find_proton_bin()
        if proton_bin is None:
            return False, "Proton was downloaded but the binary could not be found."

        os.chmod(proton_bin, 0o755)
        return True, ""
    except Exception as exc:
        return False, str(exc)


def scan_existing_prefixes() -> list[str]:
    """Scan for existing Proton prefixes in ~/.RSLManagerForLinux/prefixes/."""
    prefixes_dir = get_prefix_root()
    candidates: list[str] = []
    if not prefixes_dir.exists():
        return candidates

    for child in prefixes_dir.iterdir():
        if not child.is_dir():
            continue
        if (child / "pfx" / "drive_c").exists():
            candidates.append(str(child))
    return candidates


if __name__ == "__main__":
    path = get_config_path()
    print(f"Config path: {path}")
    config = load_config()
    print(json.dumps(config, indent=2))
