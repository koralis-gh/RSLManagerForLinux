#!/usr/bin/env python3
import argparse
import binascii
import json
import re
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config as config_module


RAID_LOCALLOW_RELATIVE = Path("pfx/drive_c/users/steamuser/AppData/LocalLow/Plarium/Raid_ Shadow Legends")
PLARIUMPLAY_LOCAL_RELATIVE = Path("pfx/drive_c/users/steamuser/AppData/Local/PlariumPlay")


def _format_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{size} B"
        value /= 1024
    return f"{size} B"


def _format_mtime(path: Path) -> str:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
    except OSError:
        return "unknown"


def _load_json(value: str) -> Any | None:
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return None


def _walk_json(value: Any) -> list[Any]:
    found = [value]
    if isinstance(value, dict):
        for child in value.values():
            found.extend(_walk_json(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(_walk_json(child))
    return found


def _extract_user(value: Any) -> tuple[str, str] | None:
    for node in _walk_json(value):
        if not isinstance(node, dict):
            continue
        user_id = node.get("i")
        player_id = node.get("m")
        if isinstance(user_id, str) and user_id.startswith("um") and player_id is not None:
            return user_id, str(player_id)
    return None


def _shorten(value: str, max_chars: int) -> str:
    if len(value) <= max_chars:
        return value
    return value[:max_chars] + f"... [truncated {len(value) - max_chars} chars]"


def _redact_sensitive_text(value: str) -> str:
    redacted = value
    redacted = re.sub(r'("(?:encrypted_key|access_token|refresh_token|id_token|auth_token|password|secret)"\s*:\s*")[^"]+(")', r"\1<redacted>\2", redacted, flags=re.IGNORECASE)
    redacted = re.sub(r"((?:access_token|refresh_token|id_token|auth_token|password|secret)=)[^&\s]+", r"\1<redacted>", redacted, flags=re.IGNORECASE)
    return redacted


def _format_cell(value: Any, max_chars: int) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bytes):
        return f"0x{binascii.hexlify(value[: max_chars // 2]).decode('ascii')}"
    text = str(value)
    parsed = _load_json(text)
    if parsed is not None:
        text = json.dumps(parsed, indent=2, sort_keys=True)
    text = _redact_sensitive_text(text)
    return _shorten(text, max_chars)


def _extract_first_string(value: Any, keys: set[str]) -> str | None:
    for node in _walk_json(value):
        if not isinstance(node, dict):
            continue
        for key in keys:
            item = node.get(key)
            if isinstance(item, str) and item.strip():
                return item
    return None


def _extract_event_name(value: Any) -> str:
    name = _extract_first_string(
        value,
        {
            "event",
            "eventName",
            "EventName",
            "name",
            "Name",
            "n",
        },
    )
    return name or "unknown"


def _read_sqlite_counts(connection: sqlite3.Connection) -> dict[str, int]:
    counts: dict[str, int] = {}
    for table in _get_table_names(connection):
        try:
            row = connection.execute(f"select count(*) from {_quote_identifier(table)}").fetchone()
            counts[table] = int(row[0]) if row else 0
        except sqlite3.Error:
            counts[table] = -1
    return counts


def _quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _get_table_names(connection: sqlite3.Connection) -> list[str]:
    rows = connection.execute(
        "select name from sqlite_master where type='table' order by name"
    ).fetchall()
    return [str(row[0]) for row in rows]


def _dump_raid_db_inventory(connection: sqlite3.Connection) -> list[str]:
    lines: list[str] = ["", "raidV2.db table inventory:"]
    for table in _get_table_names(connection):
        quoted_table = _quote_identifier(table)
        count_row = connection.execute(f"select count(*) from {quoted_table}").fetchone()
        count = int(count_row[0]) if count_row else 0
        columns = connection.execute(f"pragma table_info({quoted_table})").fetchall()

        lines.append(f"{table}: {count} row(s)")
        if not columns:
            lines.append("  columns: none")
            continue

        for _cid, name, column_type, notnull, default_value, primary_key in columns:
            constraints: list[str] = []
            if primary_key:
                constraints.append("primary key")
            if notnull:
                constraints.append("not null")
            if default_value is not None:
                constraints.append(f"default {default_value}")
            detail = f"{name} {column_type}".strip()
            if constraints:
                detail = f"{detail} ({', '.join(constraints)})"
            lines.append(f"  - {detail}")

    return lines


def _dump_raid_db_rows(connection: sqlite3.Connection, event_limit: int, max_value_chars: int) -> list[str]:
    lines: list[str] = ["", "raidV2.db row dump:"]
    for table in _get_table_names(connection):
        quoted_table = _quote_identifier(table)
        count_row = connection.execute(f"select count(*) from {quoted_table}").fetchone()
        count = int(count_row[0]) if count_row else 0
        lines.append("")
        if table == "Events" and count > event_limit:
            lines.append(f"{table}: {count} row(s), showing newest {event_limit}")
            rows = connection.execute(f"select * from {quoted_table} order by Id desc limit ?", (event_limit,)).fetchall()
        else:
            lines.append(f"{table}: {count} row(s)")
            rows = connection.execute(f"select * from {quoted_table}").fetchall()

        columns = [description[0] for description in connection.execute(f"select * from {quoted_table} limit 0").description]
        for row_index, row in enumerate(rows, start=1):
            lines.append(f"{table} row {row_index}:")
            for column, value in zip(columns, row):
                formatted = _format_cell(value, max_value_chars)
                lines.append(f"  {column}: {formatted}")

    return lines


def _diagnose_raid_db(db_path: Path, limit: int, dump_db: bool, dump_rows: bool, max_value_chars: int) -> list[str]:
    lines: list[str] = []
    lines.append("Raid account/session data:")
    if not db_path.exists():
        lines.append(f"raidV2.db: missing ({db_path})")
        return lines

    lines.append(f"raidV2.db: ok ({_format_size(db_path.stat().st_size)}, modified {_format_mtime(db_path)})")
    try:
        connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        lines.append(f"Unable to open raidV2.db read-only: {exc}")
        return lines

    try:
        counts = _read_sqlite_counts(connection)
        lines.append(
            "Tables: "
            + ", ".join(f"{table}={count if count >= 0 else 'unreadable'}" for table, count in counts.items())
        )

        if "Dictionary" in counts:
            dictionary_rows = connection.execute("select Key, Value from Dictionary order by Key").fetchall()
            for key, value in dictionary_rows:
                parsed = _load_json(value)
                if key == "UserId" and isinstance(parsed, dict):
                    user_id = parsed.get("i", "unknown")
                    player_id = parsed.get("m", "unknown")
                    lines.append(f"Dictionary UserId: {user_id} | {player_id}")
                else:
                    lines.append(f"Dictionary {key}: {len(value)} chars")

        event_count = counts.get("Events", 0)
        if event_count <= 0:
            lines.append("Events: none queued right now")
            if dump_db:
                lines.extend(_dump_raid_db_inventory(connection))
            if dump_rows:
                lines.extend(_dump_raid_db_rows(connection, limit, max_value_chars))
            return lines

        grouped: dict[tuple[str, str, str], Counter[str]] = defaultdict(Counter)
        unreadable = 0
        rows = connection.execute(
            "select Id, Body from Events order by Id desc limit ?",
            (limit,),
        ).fetchall()
        for _row_id, body in rows:
            parsed = _load_json(body)
            if parsed is None:
                unreadable += 1
                continue

            user = _extract_user(parsed) or ("unknown", "unknown")
            session_id = _extract_first_string(parsed, {"ClientSessionId", "clientSessionId", "sessionId", "SessionId"}) or "unknown-session"
            grouped[(user[0], user[1], session_id)][_extract_event_name(parsed)] += 1

        lines.append(f"Recent Events sampled: {len(rows)}")
        if unreadable:
            lines.append(f"Unreadable JSON event bodies: {unreadable}")

        for (user_id, player_id, session_id), event_counts in sorted(grouped.items()):
            top_events = ", ".join(f"{name}={count}" for name, count in event_counts.most_common(5))
            lines.append(f"Session {user_id} | {player_id} | {session_id}: {top_events}")

        if dump_db:
            lines.extend(_dump_raid_db_inventory(connection))
        if dump_rows:
            lines.extend(_dump_raid_db_rows(connection, limit, max_value_chars))
    except sqlite3.Error as exc:
        lines.append(f"Unable to inspect raidV2.db: {exc}")
    finally:
        connection.close()

    return lines


def _preview_file(path: Path, max_bytes: int) -> list[str]:
    lines: list[str] = []
    if not path.exists() or not path.is_file():
        return lines

    try:
        data = path.read_bytes()[:max_bytes]
    except OSError as exc:
        return [f"{path.name}: unable to read preview: {exc}"]

    try:
        text = data.decode("utf-8")
        if all(char.isprintable() or char in "\r\n\t" for char in text):
            text = _redact_sensitive_text(text)
            lines.append(f"{path.name} text preview:")
            lines.extend(f"  {line}" for line in text.splitlines()[:20])
            return lines
    except UnicodeDecodeError:
        pass

    hex_preview = binascii.hexlify(data).decode("ascii")
    grouped = " ".join(hex_preview[index : index + 2] for index in range(0, len(hex_preview), 2))
    lines.append(f"{path.name} hex preview ({len(data)} byte(s)): {grouped}")
    return lines


def _dump_file_inventory(root: Path, max_files: int = 120) -> list[str]:
    lines: list[str] = []
    if not root.exists():
        return lines

    files = [path for path in root.rglob("*") if path.is_file()]
    files.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    lines.append("")
    lines.append(f"Recent files under {root}:")
    for path in files[:max_files]:
        stat = path.stat()
        relative = path.relative_to(root)
        lines.append(f"{_format_mtime(path)} {_format_size(stat.st_size):>9} {relative}")
    if len(files) > max_files:
        lines.append(f"... {len(files) - max_files} more file(s)")
    return lines


def _diagnose_data_files(prefix: Path, dump_files: bool) -> list[str]:
    raid_dir = prefix / RAID_LOCALLOW_RELATIVE
    plarium_dir = prefix / PLARIUMPLAY_LOCAL_RELATIVE
    lines: list[str] = []

    lines.append("")
    lines.append("Raid data folders:")
    lines.append(f"LocalLow: {'ok' if raid_dir.exists() else 'missing'} ({raid_dir})")
    if raid_dir.exists():
        battle_results = raid_dir / "battle-results" / "battleResults"
        static_data = raid_dir / "static-data"
        texture_dir = raid_dir / "LoadedTextures"
        lines.append(f"battle-results: {'ok' if battle_results.exists() else 'missing'}")
        if battle_results.exists():
            lines.append(f"battle-results size: {_format_size(battle_results.stat().st_size)}")

        if static_data.exists():
            static_files = [path for path in static_data.rglob("*") if path.is_file()]
            total_size = sum(path.stat().st_size for path in static_files)
            versions = ", ".join(sorted(path.name for path in static_data.iterdir() if path.is_dir())[:5])
            lines.append(f"static-data: {len(static_files)} file(s), {_format_size(total_size)}, versions: {versions or 'none'}")
        else:
            lines.append("static-data: missing")

        if texture_dir.exists():
            texture_count = sum(1 for path in texture_dir.iterdir() if path.is_file())
            lines.append(f"LoadedTextures: {texture_count} cached texture file(s)")
        else:
            lines.append("LoadedTextures: missing")

        if dump_files:
            lines.append("")
            lines.append("Small file previews:")
            for preview_path in (
                battle_results,
                raid_dir / "dynamic-data" / "DeeplinkCache",
                raid_dir / "workers-serialization" / "serialization",
                raid_dir / "Vuplex.WebView" / "chromium-cache" / "LocalPrefs.json",
                *sorted((raid_dir / "Unity").glob("*/Analytics/config"))[:3],
            ):
                lines.extend(_preview_file(preview_path, 512))
            lines.extend(_dump_file_inventory(raid_dir))

    lines.append(f"PlariumPlay: {'ok' if plarium_dir.exists() else 'missing'} ({plarium_dir})")
    if plarium_dir.exists():
        game_storage = plarium_dir / "gamestorage.gsfn"
        logs_dir = plarium_dir / "logs"
        build_dir = plarium_dir / "StandAloneApps" / "raid-shadow-legends" / "build"
        raid_exe = build_dir / "Raid.exe"
        lines.append(f"installed Raid build: {'ok' if raid_exe.exists() else 'missing'} ({raid_exe})")
        if game_storage.exists():
            parsed = _load_json(game_storage.read_text(encoding="utf-8", errors="replace"))
            source = parsed.get("source") if isinstance(parsed, dict) else None
            lines.append(f"gamestorage.gsfn: ok{f' ({source})' if source else ''}")
        else:
            lines.append("gamestorage.gsfn: missing")

        if logs_dir.exists():
            log_files = [path for path in logs_dir.iterdir() if path.is_file()]
            lines.append(f"logs: {len(log_files)} file(s)")
            if dump_files:
                lines.extend(_dump_file_inventory(logs_dir, max_files=40))
        else:
            lines.append("logs: missing")

    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only Raid local data diagnostics")
    parser.add_argument("--prefix", default=None, help="Proton prefix to inspect")
    parser.add_argument("--limit", type=int, default=50, help="Recent Events rows to sample")
    parser.add_argument("--dump-db", action="store_true", help="Dump raidV2.db table columns and row counts")
    parser.add_argument("--dump-rows", action="store_true", help="Dump raidV2.db table rows")
    parser.add_argument("--dump-files", action="store_true", help="Show small file previews and recent file inventory")
    parser.add_argument("--max-value-chars", type=int, default=4000, help="Max characters per dumped DB value")
    args = parser.parse_args()

    if args.prefix:
        prefix = Path(args.prefix).expanduser()
    else:
        cfg = config_module.load_config()
        prefix = Path(cfg.get("prefix_path") or config_module.DEFAULT_CONFIG["prefix_path"]).expanduser()

    db_path = prefix / RAID_LOCALLOW_RELATIVE / "raidV2.db"
    lines = [
        "Raid local data diagnostics",
        f"Prefix: {prefix}",
        "",
        *_diagnose_raid_db(db_path, max(args.limit, 1), args.dump_db, args.dump_rows, max(args.max_value_chars, 100)),
        *_diagnose_data_files(prefix, args.dump_files),
    ]
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
