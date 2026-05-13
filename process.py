import os
import signal
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Tuple


def check_wine_available() -> bool:
    try:
        result = subprocess.run(
            ["wine", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.SubprocessError):
        return False


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


def get_plarium_processes() -> List[Dict[str, Any]]:
    return [proc for proc in _list_linux_processes() if _matches_process(proc, ["plarium.exe", "plariumplay.exe"])]


def get_raid_processes() -> List[Dict[str, Any]]:
    return [proc for proc in _list_linux_processes() if _matches_process(proc, ["raid.exe"])]


def kill_process(pid: int, sig: int = signal.SIGTERM) -> bool:
    try:
        os.kill(pid, sig)
        return True
    except OSError:
        return False


def launch_plarium(game_exe_path: str, wine_prefix: str) -> Tuple[bool, str]:
    path = Path(game_exe_path).expanduser()
    wine_prefix_path = Path(wine_prefix).expanduser()
    if not path.exists():
        return False, f"Game executable not found: {path}"

    env = os.environ.copy()
    env["WINEPREFIX"] = str(wine_prefix_path)
    try:
        subprocess.Popen(
            ["wine", str(path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
        )
        return True, ""
    except FileNotFoundError:
        return False, "wine executable not found on PATH"
    except OSError as exc:
        return False, str(exc)


def scan_existing_prefixes() -> List[str]:
    home = Path.home()
    candidates: List[str] = []
    search_paths = [home / ".wine", home / ".local" / "share" / "wineprefixes"]
    for root in search_paths:
        if not root.exists():
            continue
        for child in root.iterdir():
            if not child.is_dir():
                continue
            prefix_candidate = child
            if (prefix_candidate / "drive_c" / "Program Files" / "PlariumPlay" / "PlariumPlay.exe").exists():
                candidates.append(str(prefix_candidate))
            elif prefix_candidate.name.lower().startswith("rsl"):
                candidates.append(str(prefix_candidate))
    return candidates
