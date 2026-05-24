# RSLManagerForLinux

Linux launcher and process manager for Raid: Shadow Legends. It installs Proton GE, installs the Windows .NET Desktop Runtime 8 into the Proton prefix, launches Plarium/Raid, and shows running Plarium and Raid processes.

## Prerequisites

You need Python, Tkinter, venv, pip, make, wmctrl, desktop integration tools, and 32-bit Wine/Proton runtime libraries.

Debian/Ubuntu:

```bash
sudo apt update
sudo apt install python3 python3-venv python3-tk python3-pip make wmctrl desktop-file-utils gtk-update-icon-cache
sudo dpkg --add-architecture i386
sudo apt update
sudo apt install libc6:i386 libstdc++6:i386 libgcc-s1:i386 libfreetype6:i386 libfontconfig1:i386 libx11-6:i386 libxext6:i386 libxrender1:i386 libxi6:i386 libxrandr2:i386 libxcursor1:i386 libxcomposite1:i386 libxdamage1:i386 libxfixes3:i386 libgl1:i386 libegl1:i386
```

Fedora:

```bash
sudo dnf install python3 python3-tkinter python3-pip make wmctrl desktop-file-utils gtk-update-icon-cache
sudo dnf install glibc.i686 libstdc++.i686 libgcc.i686 freetype.i686 fontconfig.i686 libX11.i686 libXext.i686 libXrender.i686 libXi.i686 libXrandr.i686 libXcursor.i686 libXcomposite.i686 libXdamage.i686 libXfixes.i686 mesa-libGL.i686 mesa-libEGL.i686
```

## Install

From the repo:

```bash
make install-app
```

This runs the full setup and installs the desktop/CLI launcher. It creates `.venv`, installs Python requirements, installs Proton GE under `~/.RSLManagerForLinux/proton`, installs Windows .NET Desktop Runtime 8 into the configured Proton prefix, and creates:

- `~/.local/bin/RSLManagerForLinux`
- `~/.local/share/applications/RSLManagerForLinux.desktop`

If you move the repo, rerun `make install-app` from the new location.

## Run

Open `RSLManagerForLinux` from your app menu, or run:

```bash
RSLManagerForLinux
```

From the repo you can also use:

```bash
make run
```

Logs are written to `logs/RSLManagerForLinux.log`.

## Diagnostics

```bash
make diagnose
```

This checks the venv, Tkinter, Proton GE, Windows .NET Desktop Runtime 8, local Raid data files, and required 32-bit packages. The app also has a `Diagnose` button.

To inspect only the local Raid account/session cache:

```bash
make raid-data
make raid-data-dump
```

## Useful Targets

```bash
make install              # full runtime setup without desktop app install
make install-app          # full setup plus desktop/CLI launcher
make install-proton       # reinstall/check Proton GE only
make install-windows-dotnet # reinstall/check Windows .NET runtime only
make raid-data            # inspect local Raid account/session cache
make raid-data-dump       # verbose local data dump for manual inspection
make uninstall-app        # remove desktop/CLI launcher only
make check                # compile Python files
```

## Project Files

- `gui.py` - CustomTkinter app
- `config.py` - config, paths, Proton/runtime status helpers
- `process.py` - process discovery and Proton launch
- `scripts/setup_runtime.py` - Proton and Windows .NET runtime setup
- `scripts/raid_data_diagnose.py` - read-only local Raid data diagnostics
- `scripts/RSLManagerForLinux.in` - installed launcher template
