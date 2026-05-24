import os
import signal
import subprocess
import threading
from pathlib import Path
from typing import Any, Dict, List

import config as config_module


def _log(message: str) -> None:
    config_module.append_app_log(message)


def _log_process_output(process: subprocess.Popen[str]) -> None:
    if process.stdout is None:
        return

    try:
        with process.stdout:
            for line in process.stdout:
                config_module.append_app_log(f"Proton: {line.rstrip()}", trim=False)
        config_module.append_app_log(f"Proton process exited with status {process.wait()}")
    finally:
        config_module.trim_app_log()


def _read_cmdline(pid: int) -> str:
    proc_cmd = Path(f"/proc/{pid}/cmdline")
    if not proc_cmd.exists():
        return ""
    try:
        data = proc_cmd.read_bytes()
        return data.replace(b"\x00", b" ").decode(errors="ignore").strip()
    except OSError:
        return ""


def _read_comm(pid: int) -> str:
    proc_comm = Path(f"/proc/{pid}/comm")
    if not proc_comm.exists():
        return ""
    try:
        return proc_comm.read_text(errors="ignore").strip()
    except OSError:
        return ""


def _list_linux_processes() -> List[Dict[str, Any]]:
    procs: List[Dict[str, Any]] = []
    proc_root = Path("/proc")
    if not proc_root.exists():
        return procs

    for child in proc_root.iterdir():
        if not child.name.isdigit():
            continue
        pid = int(child.name)
        cmdline = _read_cmdline(pid)
        comm = _read_comm(pid)
        if not cmdline and not comm:
            continue
        procs.append({"pid": pid, "comm": comm, "cmdline": cmdline})
    return procs


def _matches_process(proc: Dict[str, Any], keywords: List[str]) -> bool:
    cmdline = proc.get("cmdline", "").lower()
    comm = proc.get("comm", "").lower()
    for keyword in keywords:
        if keyword.lower() in cmdline or keyword.lower() in comm:
            return True
    return False


def _get_window_rows() -> List[Dict[str, Any]]:
    try:
        result = subprocess.run(
            ["wmctrl", "-lpG"],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return []

    if result.returncode != 0:
        return []

    windows: List[Dict[str, Any]] = []
    for line in result.stdout.splitlines():
        parts = line.split(None, 8)
        if len(parts) < 9:
            continue
        window_id, desktop, pid, x, y, width, height, host, title = parts
        try:
            windows.append(
                {
                    "window_id": window_id,
                    "desktop": int(desktop),
                    "pid": int(pid),
                    "x": int(x),
                    "y": int(y),
                    "width": int(width),
                    "height": int(height),
                    "host": host,
                    "title": title,
                }
            )
        except ValueError:
            continue
    return windows


def get_raid_windows() -> List[Dict[str, Any]]:
    windows: List[Dict[str, Any]] = []
    for window in _get_window_rows():
        title = window.get("title", "").lower()
        if "raid" in title and "shadow legends" in title:
            windows.append(window)
    return windows


def get_raid_processes() -> List[Dict[str, Any]]:
    windows_by_pid = {window["pid"]: window for window in get_raid_windows()}
    raid_procs = [proc for proc in _list_linux_processes() if _matches_process(proc, ["raid.exe"])]
    for proc in raid_procs:
        window = windows_by_pid.get(proc["pid"])
        if window is not None:
            proc["window"] = window
    return raid_procs


def get_plarium_processes() -> List[Dict[str, Any]]:
    procs: List[Dict[str, Any]] = []
    for proc in _list_linux_processes():
        comm = proc.get("comm", "").lower()
        cmdline = proc.get("cmdline", "").lower()
        if "raid.exe" in comm or "raid.exe" in cmdline:
            continue

        is_plarium_process = (
            comm.startswith("plarium")
            or "plariumplay.exe" in cmdline
            or "plariumplayclientservice.exe" in cmdline
        )
        if is_plarium_process:
            procs.append(proc)
    return procs


def kill_process(pid: int, sig: int = signal.SIGTERM) -> bool:
    try:
        os.kill(pid, sig)
        return True
    except OSError:
        return False


def launch_raid(game_exe_path: str, prefix_path: str) -> tuple[bool, str]:
    _log(f"New Raid process requested: game_exe_path={game_exe_path!r}, prefix_path={prefix_path!r}")
    path = Path(game_exe_path).expanduser()
    prefix = Path(prefix_path).expanduser()
    proton_bin = config_module._find_proton_bin()

    if proton_bin is None:
        _log("Launch failed: Proton is not installed")
        return False, "Proton is not installed. Please install Proton GE first."

    if not path.exists():
        _log(f"Launch failed: setup executable not found: {path}")
        return False, f"Setup executable not found: {path}"

    prefix.mkdir(parents=True, exist_ok=True)
    config_module.get_steam_dummy_path().mkdir(parents=True, exist_ok=True)

    # Look for an already-installed raid.exe
    installed_exe = _find_installed_executable(prefix)
    exe_to_run = installed_exe if installed_exe is not None else path

    if not exe_to_run.exists():
        _log(f"Launch failed: executable not found: {exe_to_run}")
        return False, f"Executable not found: {exe_to_run}"

    env = os.environ.copy()
    env["STEAM_COMPAT_DATA_PATH"] = str(prefix)
    env["STEAM_COMPAT_CLIENT_INSTALL_PATH"] = str(config_module.get_steam_dummy_path())
    env.setdefault("PROTON_LOG", "1")

    command = [str(proton_bin), "run", str(exe_to_run)]
    _log(f"Launching command: {command!r}")
    _log(f"Launch cwd: {exe_to_run.parent}")
    _log(f"STEAM_COMPAT_DATA_PATH={env['STEAM_COMPAT_DATA_PATH']}")
    _log(f"STEAM_COMPAT_CLIENT_INSTALL_PATH={env['STEAM_COMPAT_CLIENT_INSTALL_PATH']}")

    try:
        _log("Proton process output begins")
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
            cwd=exe_to_run.parent,
            close_fds=True,
            text=True,
            errors="replace",
            bufsize=1,
        )
        threading.Thread(target=_log_process_output, args=(process,), daemon=True).start()
        _log("Launch command started successfully")
        return True, ""
    except FileNotFoundError:
        _log("Launch failed: Proton binary not found")
        return False, "Proton binary not found"
    except OSError as exc:
        _log(f"Launch failed: {exc}")
        return False, str(exc)


def _find_installed_executable(prefix_path: Path) -> Path | None:
    drive_c = prefix_path / "pfx" / "drive_c"
    if not drive_c.exists():
        return None

    for path in drive_c.rglob("raid.exe"):
        if path.is_file():
            return path
    return None
