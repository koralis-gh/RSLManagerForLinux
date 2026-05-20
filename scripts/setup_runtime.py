#!/usr/bin/env python3
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config as config_module


def _log(message: str) -> None:
    config_module.append_app_log(message)
    print(message)


def _proton_progress(downloaded: int, total: int) -> None:
    if total > 0:
        percent = int(downloaded * 100 / total)
        print(f"\rProton GE download/extract progress: {percent}%", end="", flush=True)


def install_proton() -> int:
    status = config_module.get_proton_install_status()
    if status["proton_installed"] and status["steam_dummy_exists"]:
        print(f"Proton GE already installed at {status['proton_bin']}")
        return 0

    success, message = config_module.install_proton(progress_callback=_proton_progress)
    print()
    if not success:
        print(f"Proton GE install failed: {message}")
        return 1

    status = config_module.get_proton_install_status()
    print(f"Proton GE installed at {status['proton_bin']}")
    return 0


def check_proton() -> int:
    status = config_module.get_proton_install_status()
    if status["proton_installed"]:
        print(f"Proton GE: ok ({status['proton_bin']})")
        return 0
    print(f"Proton GE: missing ({status['proton_bin']})")
    return 1


def _download_file(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    _log(f"Downloading Windows .NET Desktop Runtime 8 x64 to {destination}")
    with urllib.request.urlopen(url) as response, destination.open("wb") as output:
        total = int(response.getheader("Content-Length", "0") or "0")
        downloaded = 0
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            output.write(chunk)
            downloaded += len(chunk)
            if total:
                percent = int(downloaded * 100 / total)
                print(f"\rDownloaded {percent}%", end="", flush=True)
        if total:
            print()


def _configured_prefix() -> Path:
    cfg = config_module.load_config()
    prefix_value = cfg.get("prefix_path") or config_module.DEFAULT_CONFIG["prefix_path"]
    return Path(prefix_value).expanduser()


def check_windows_dotnet() -> int:
    prefix = _configured_prefix()
    if config_module.check_windows_dotnet_available(prefix):
        print(f"Windows .NET Desktop Runtime 8 in prefix: ok ({prefix})")
        return 0
    print(f"Windows .NET Desktop Runtime 8 in prefix: missing ({prefix})")
    return 1


def install_windows_dotnet() -> int:
    prefix = _configured_prefix()
    proton_bin = config_module._find_proton_bin()
    if proton_bin is None:
        _log("Windows .NET install failed: Proton is not installed")
        return 1

    prefix.mkdir(parents=True, exist_ok=True)
    config_module.get_steam_dummy_path().mkdir(parents=True, exist_ok=True)

    if config_module.check_windows_dotnet_available(prefix):
        _log(f"Windows .NET Desktop Runtime 8 already appears installed in {prefix}")
        return 0

    installer = config_module.get_app_root() / "downloads" / config_module.WINDOWS_DOTNET_INSTALLER_NAME
    if not installer.exists():
        _download_file(config_module.WINDOWS_DOTNET_DESKTOP_RUNTIME_URL, installer)
    else:
        _log(f"Using cached Windows .NET Desktop Runtime installer at {installer}")

    env = os.environ.copy()
    env["STEAM_COMPAT_DATA_PATH"] = str(prefix)
    env["STEAM_COMPAT_CLIENT_INSTALL_PATH"] = str(config_module.get_steam_dummy_path())

    command = [str(proton_bin), "run", str(installer), "/install", "/quiet", "/norestart"]
    _log(f"Installing Windows .NET Desktop Runtime 8 into prefix {prefix}")
    _log(f"Launching command: {command!r}")

    process = subprocess.Popen(
        command,
        cwd=installer.parent,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        errors="replace",
    )
    assert process.stdout is not None
    for line in process.stdout:
        config_module.append_app_log(f"Windows .NET installer: {line.rstrip()}", trim=False)
    status = process.wait()
    config_module.trim_app_log()

    if status != 0:
        _log(f"Windows .NET install failed with status {status}")
        return status

    if not config_module.check_windows_dotnet_available(prefix):
        _log("Windows .NET installer exited successfully, but .NET 8 was not found in the prefix yet")
        return 1

    _log("Windows .NET Desktop Runtime 8 installed successfully")
    return 0


def install_all() -> int:
    proton_status = install_proton()
    if proton_status != 0:
        return proton_status
    return install_windows_dotnet()


def diagnose() -> int:
    proton_status = check_proton()
    dotnet_status = check_windows_dotnet()
    return 0 if proton_status == 0 and dotnet_status == 0 else 1


def main() -> int:
    command = sys.argv[1] if len(sys.argv) > 1 else "install"
    if command == "install":
        return install_all()
    if command == "install-proton":
        return install_proton()
    if command == "install-windows-dotnet":
        return install_windows_dotnet()
    if command == "diagnose":
        return diagnose()

    print("Usage: setup_runtime.py [install|install-proton|install-windows-dotnet|diagnose]")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
