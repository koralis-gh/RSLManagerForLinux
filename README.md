# RSLManagerForLinux

RSLManagerForLinux is a lightweight Linux launcher and process manager for Raid: Shadow Legends. It uses Proton GE to install and launch the game, shows running Raid and Plarium launcher processes, and provides simple controls for starting and exiting processes.

## Prerequisites

You need Python, Tkinter, venv support, pip, make, and common desktop integration tools.

On Debian or Ubuntu:

```bash
sudo apt update
sudo apt install python3 python3-venv python3-tk python3-pip make desktop-file-utils gtk-update-icon-cache
```

If your distro package set does not include `gtk-update-icon-cache` by that name, install the GTK icon theme tools package for your distribution. The installer will continue if the icon cache tool is missing.

On Fedora:

```bash
sudo dnf install python3 python3-tkinter python3-pip make desktop-file-utils gtk-update-icon-cache
```

On Fedora, Python venv support is normally included with Python.

## Install

From the repo directory:

```bash
make install
make install-app
```

`make install` creates a local `.venv` inside this repo and installs Python requirements there. It does not install packages into your system Python.

`make install-app` installs:

- `~/.local/bin/RSLManagerForLinux`
- `~/.local/share/applications/RSLManagerForLinux.desktop`
- app icon files under `~/.local/share/icons` and `~/.local/share/pixmaps`

If you move the repo, run `make install-app` again from the new repo path. It will update the launcher and desktop file in place.

## Run

After `make install-app`, launch from your app menu by searching for:

```text
RSLManagerForLinux
```

Or run from a shell:

```bash
RSLManagerForLinux
```

If that command is not found, add `~/.local/bin` to your `PATH`.

You can also run from the repo:

```bash
make run
```

Logs from `make run` are written to:

```text
/tmp/RSLManagerForLinux.log
```

## Development Check

```bash
make check
```

This compiles the Python files and uses the local `.venv` Python if it exists.
