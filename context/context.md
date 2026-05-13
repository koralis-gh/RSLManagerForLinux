# RSLManagerForLinux

## Project Purpose

Build a lightweight launcher and process manager for **Raid Shadow Legends** on Linux. The app should make it easy to run multiple game instances, track running sessions, and manage per-instance status from a modern GUI.

## Design Direction

The UI is based on the mockup image in `context/image.png` and will use a polished dark theme with rounded panels.

Three main pages:

1. Setup / Config page
2. Dashboard / empty state page
3. Active process list page

Common top UI elements:
- Header title: `RSLManagerForLinux`
- Top-right buttons: `Promo Code Chooser` https://raid-promo-link-finder.vercel.app/, `Champion Info` https://rsl-x.vercel.app/tools/champions-index
- Bottom action: `New Raid Process` button to start plarium.exe
- Visible `Browse config` button on all pages that opens the config.json in vs code or text editor

## Page behavior and triggers

### 1. Setup / Config page

When to show:
- config file is missing or required setup values are incomplete
- Wine is not detected on the system (test: `wine --version`)
- `game_exe_path` is missing or points to a file that does not exist
- `wine_prefix` is missing or invalid

Content:
- explanation text for required setup
- raw editable config JSON shown in a scrollable box for quick manual fixes
- file browser control to locate `plarium.exe`
- suggestion text when `plarium.exe` is not found, e.g. "It may be in Downloads or the Plarium Play installer folder"
- text input or file browser for Wine prefix location (default: `~/.wine`)
- `Scan for existing RSLManagerForLinux prefixes` button to detect valid Wine prefixes automatically
- `Create Config` button to generate config and write to `~/.config/RSLManagerForLinux/config.json`
- `Get Plarium` button with link to download Plarium Play: https://plarium.com/en/plarium-play/
- `Get Wine` button when Wine is not available
  - show install instructions with option to run install commands automatically
- `Browse config` button to open the JSON file in a text editor

Exact UI state behavior:
- Wine missing: show setup page with Wine install info and install helper actions
- `plarium.exe` not found: show setup page with locate button and a downloads hint
- invalid `wine_prefix`: show setup page with prefix scan button and validation error
- config valid if both `game_exe_path` and `wine_prefix` are set and pass basic validation
- config can be edited while running, but only in response to explicit user actions such as browsing for a new file or editing the JSON

Action flow:
- on app open, validate config and run `wine --version`
- if config is valid and Wine works, move directly to the dashboard/process view
- if config is invalid or Wine fails, show the setup page with the raw JSON and helper actions
- once both fields are filled and Wine is confirmed available, move to the dashboard/process view

### 2. Dashboard / Active process page

When to show:
- config exists and required values are valid
- the app is running normally

Content:
- message: `No Raid processes currently running` when no `raid.exe` processes are present
- large `New Raid Process` button/icon
- one card per running `raid.exe` process
- each card shows:
  - process label: `Raid Process 1`, `Raid Process 2`, etc.
  - status icon (green = running, red = stopped)
  - process ID
  - `Exit` button to terminate that `raid.exe`
- an additional `Kill plarium.exe` button outside the cards to terminate the launcher process if needed
- `Browse config` button remains available
- top-right helper buttons remain available

Action flow:
- clicking `New Raid Process` attempts to start `plarium.exe` using the configured Wine prefix
- if a `plarium.exe` process exists, kill it before launching a new one
- existing `raid.exe` processes remain untouched when starting a new session
- if launch fails, keep the process page visible and show a launch failure message with the option to kill `plarium.exe`
- if no `raid.exe` processes are present, show the empty state message but remain on the same page

Refresh behavior:
- refresh process state every 1 second by default
- use a millisecond-configurable interval so the refresh rate can be tuned to reduce CPU load

Notes:
- dashboard and active list are technically the same page; the UI should adapt in place rather than using entirely separate windows
- promo buttons are external links opened in the OS default browser
- process cards should remain minimal: label, status, PID, and exit button
- consider adding a future visual hint for which window belongs to which `raid.exe` if multiple processes are present

## Feature priorities

- Detect Wine availability on the system instead of requiring a hard-coded Wine path
- If Wine is missing, provide a `Get Wine` helper with:
  - command line install instructions
  - an optional web page with install guidance
  - a direct action button that runs install commands when safe
- Persist configuration in JSON under the user config directory
- Use a single GUI entry point with flow control based on config and runtime state
- Track `plarium.exe` and `raid.exe` processes separately
- Use multiple `raid.exe` PIDs as the basis for cards on the active process page
- Display instance state, PID, and simple controls for each running process

## Launch workflow

The first launch uses the path chosen in setup and the configured Wine prefix:

```bash
#!/bin/bash
export WINEPREFIX=~/.wine/RSLHelperForLinux
wine "path/to/plarium.exe"
```

After Plarium Play is installed in that prefix, the saved config path should point to the installed executable:

```bash
#!/bin/bash
export WINEPREFIX=~/.wine/RSLHelperForLinux
wine "$WINEPREFIX/drive_c/Program Files/PlariumPlay/PlariumPlay.exe"
```

The config file should therefore store:
- `game_exe_path` — the chosen executable path for Plarium Play
- `wine_prefix` — the Wine prefix to use for launching and persistence

## Persistence strategy

- Store a single minimal JSON config file in the per-user config directory
- On Linux, default to `~/.config/RSLManagerForLinux/config.json`
- Honor `XDG_CONFIG_HOME` when set
- Config is user-editable and contains only the two essential paths
- No per-account data in config; running processes are discovered live

## Config shape

Minimal config structure:

```json
{
  "game_exe_path": "/path/to/plarium.exe",
  "wine_prefix": "~/.wine/RSLHelperForLinux"
}
```

That's it. Just the two paths needed to launch and manage Wine instances.

## Project structure

- `config.py` — config persistence and validation
- `gui.py` — CustomTkinter GUI and page management
- `process.py` — process launch, detection, and termination logic
- `context/context.md` — project plan and requirements
- `context/image.png` — current UI mockup
- `requirements.txt` - any packages for the scripts
- `Makefile` - shortcuts to install requirements.txt, launch the app or install it as a local package

## Notes

- Remove explicit Wine/Proton path entry from the setup flow.
- Check that Wine exists in the system path and prompt the user only if it is missing.
- Keep the `Browse config` action available on every page for quick manual edits.
- Use the same `wine_prefix` across launches; the app only needs to ensure any existing `plarium.exe` process is closed before starting it again.
- The UI should be driven by page state: setup → dashboard → active list, based on config validity and process state.
