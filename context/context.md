# RSLManagerForLinux

## Project Purpose

Build a lightweight launcher and process manager for **Raid Shadow Legends** on Linux using **Proton GE**. The app makes it easy to run multiple game instances, track running sessions, and manage per-instance status from a modern GUI.

The UI uses customtkinter with a polished dark theme and two main states:
1. **Setup page** — config entry, executable selection, Proton installation
2. **Process page** — dashboard showing running Raid processes with launch/kill controls

## Architecture

### Module Responsibilities

#### `config.py` — System Setup & Infrastructure
- **Purpose**: Configuration I/O, Proton GE installation, Wine prefix management
- **Key Functions**:
  - `load_config()`, `save_config()`, `validate_config()` — config file I/O
  - `check_proton_available()` — verify Proton GE is installed and working
  - `install_proton(progress_callback)` — download and extract Proton GE 10-10
  - `scan_existing_prefixes()` — discover existing Proton prefixes
  - `_find_proton_bin()` — locate Proton binary at `~/.RSLManagerForLinux/proton/GE-Proton10-10/proton`
  - Path helpers: `get_app_root()`, `get_proton_root()`, `get_prefix_root()`, `get_default_prefix()`

#### `process.py` — Process Lifecycle
- **Purpose**: Process tracking, launching, and termination
- **Key Functions**:
  - `get_raid_processes()` — find running `raid.exe` instances via `/proc` filesystem
  - `launch_raid(game_exe_path, prefix_path)` — start game via Proton
  - `kill_process(pid, signal)` — terminate a process by PID
  - `_find_installed_executable(prefix_path)` — locate `raid.exe` in a prefix

#### `gui.py` — User Interface
- **Purpose**: User interaction, forms, process dashboard
- **Key Components**:
  - Setup frame: game executable browser, prefix selector, Proton install button
  - Process frame: running process list, launch/kill controls, config editor
  - Progress dialog: background Proton download with KiB/total display
  - Action delegates: all infrastructure calls go to `config_module`; all process calls go to `process_module`

### Storage Layout

```
~/.RSLManagerForLinux/
├── config.json                    # User config (game_exe_path, prefix_path)
├── GE-Proton10-10.tar.gz          # Proton GE archive (reused if present)
├── proton/
│   └── GE-Proton10-10/
│       ├── proton                 # Proton executable
│       └── ...
└── prefixes/
    └── raid1/
        └── pfx/
            └── drive_c/           # Windows C: drive for the prefix
                ├── Program Files/
                │   └── Plarium/
                │       └── RaidShadowLegends.exe
                └── ...
```

### Config Schema

```json
{
  "game_exe_path": "/path/to/RaidSetup.exe",
  "prefix_path": "~/.RSLManagerForLinux/prefixes/raid1"
}
```

## Workflows

### Setup Workflow
1. User opens app with missing/invalid config
2. Setup page shows config form with game executable browser
3. User browses to `RaidSetup.exe` (from Downloads or previous install)
4. User selects or creates Proton prefix (default: `~/.RSLManagerForLinux/prefixes/raid1`)
5. Config is saved to `~/.RSLManagerForLinux/config.json`
6. Proton GE is auto-installed if not present (shows progress dialog)
7. App transitions to process page

### Launch Workflow
1. Config is valid and Proton is available
2. User clicks "New Raid Process"
3. `process.launch_raid()` is called with config paths
4. `config._find_proton_bin()` locates Proton binary
5. If prefix is new, `RaidSetup.exe` runs to install the game
6. If prefix exists, installed `raid.exe` is launched directly
7. Environment: `STEAM_COMPAT_DATA_PATH` set to prefix root

### Monitoring Workflow
1. GUI polls `process.get_raid_processes()` every 1 second
2. If PID list changes, UI rebuilds process cards
3. If PID list unchanged, refresh cycle repeats without UI update
4. User can click kill button to terminate a process

## Design Principles

- **Separation of Concerns**: Each module has a single responsibility
  - Config/setup → `config.py`
  - Process operations → `process.py`
  - UI/UX → `gui.py`
- **Lazy Proton Installation**: Proton auto-installs on first launch if needed
- **Smart Prefix Reuse**: Installed games run directly; setup exe only runs first time
- **Minimal Config**: Only two paths stored; proton_root and other dirs derived
- **Live Process Detection**: Uses `/proc` filesystem, no config-based tracking
- **Change Detection**: UI only rebuilds on actual process list changes (no flashing)
- **Tarball Reuse**: Downloaded Proton archive is retained for reinstallation without re-download

## Project Files

- `config.py` — Configuration and Proton installation logic
- `gui.py` — CustomTkinter GUI with setup/process pages
- `process.py` — Process detection and launching via Proton
- `context/context.md` — This document
- `context/image.png` — UI mockup
- `requirements.txt` — Python dependencies
- `Makefile` — Build shortcuts
