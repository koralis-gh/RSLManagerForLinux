APP_ID := RSLManagerForLinux
WM_CLASS := Rslmanagerforlinux
APP_DIR := $(CURDIR)
VENV_DIR := $(APP_DIR)/.venv
PYTHON := $(VENV_DIR)/bin/python
PIP := $(VENV_DIR)/bin/pip
LOG_DIR := $(APP_DIR)/logs
LOG_FILE := $(LOG_DIR)/$(APP_ID).log
BIN_DIR := $(HOME)/.local/bin
PROFILE_FILE := $(HOME)/.profile
ICON_DIR := $(HOME)/.local/share/icons/hicolor/256x256/apps
PIXMAP_DIR := $(HOME)/.local/share/pixmaps
DESKTOP_DIR := $(HOME)/.local/share/applications
BIN_FILE := $(BIN_DIR)/$(APP_ID)
DESKTOP_FILE := $(DESKTOP_DIR)/$(APP_ID).desktop
ICON_FILE := $(ICON_DIR)/$(APP_ID).png
PIXMAP_FILE := $(PIXMAP_DIR)/$(APP_ID).png

check-prereqs:
	@set -e; \
	missing=""; \
	if command -v apt >/dev/null 2>&1; then pm="apt"; elif command -v dnf >/dev/null 2>&1; then pm="dnf"; else pm=""; fi; \
	if ! command -v python3 >/dev/null 2>&1; then missing="$$missing python3"; fi; \
	PYVER=""; \
	if command -v python3 >/dev/null 2>&1; then PYVER=$$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")'); fi; \
	if command -v python3 >/dev/null 2>&1 && ! python3 -c 'import tkinter' >/dev/null 2>&1; then missing="$$missing tkinter"; fi; \
	if ! command -v wmctrl >/dev/null 2>&1; then missing="$$missing wmctrl"; fi; \
	if [ ! -e /lib/ld-linux.so.2 ] && [ ! -e /lib32/ld-linux.so.2 ] && [ ! -e /lib/i386-linux-gnu/ld-linux.so.2 ]; then missing="$$missing 32-bit-runtime"; fi; \
	if command -v python3 >/dev/null 2>&1; then \
		TMPDIR=$$(mktemp -d); \
		if ! python3 -m venv "$$TMPDIR/venv" >/dev/null 2>&1; then missing="$$missing venv"; fi; \
		rm -rf "$$TMPDIR"; \
	fi; \
	if [ -n "$$missing" ]; then \
		echo "Missing system dependencies:$$missing"; \
		if [ "$$pm" = "apt" ]; then \
			pkgs="python3 python3-venv python3-tk python3-pip make wmctrl desktop-file-utils gtk-update-icon-cache"; \
			i386_pkgs="libc6:i386 libstdc++6:i386 libgcc-s1:i386"; \
			echo "This can be installed with:"; \
			echo "  sudo dpkg --add-architecture i386"; \
			echo "  sudo apt update"; \
			echo "  sudo apt install $$pkgs $$i386_pkgs"; \
			printf "Run these apt commands now? [y/N] "; \
			read answer; \
			case "$$answer" in [Yy]*) sudo dpkg --add-architecture i386; sudo apt update; sudo apt install $$pkgs $$i386_pkgs ;; *) exit 1 ;; esac; \
		elif [ "$$pm" = "dnf" ]; then \
			pkgs="python3 python3-tkinter python3-pip make wmctrl desktop-file-utils gtk-update-icon-cache glibc.i686 libstdc++.i686 libgcc.i686"; \
			echo "This can be installed with:"; \
			echo "  sudo dnf install $$pkgs"; \
			printf "Run this dnf command now? [y/N] "; \
			read answer; \
			case "$$answer" in [Yy]*) sudo dnf install $$pkgs ;; *) exit 1 ;; esac; \
		else \
			echo "Unable to detect apt or dnf. Please install the missing dependencies manually."; \
			exit 1; \
		fi; \
	fi; \
	if ! command -v python3 >/dev/null 2>&1; then echo "python3 is still missing."; exit 1; fi; \
	if ! python3 -c 'import tkinter' >/dev/null 2>&1; then echo "tkinter is still missing."; exit 1; fi; \
	if ! command -v wmctrl >/dev/null 2>&1; then echo "wmctrl is still missing."; exit 1; fi; \
	if [ ! -e /lib/ld-linux.so.2 ] && [ ! -e /lib32/ld-linux.so.2 ] && [ ! -e /lib/i386-linux-gnu/ld-linux.so.2 ]; then echo "32-bit Linux loader is still missing."; exit 1; fi; \
	TMPDIR=$$(mktemp -d); \
	if ! python3 -m venv "$$TMPDIR/venv" >/dev/null 2>&1; then rm -rf "$$TMPDIR"; echo "venv support is still missing."; exit 1; fi; \
	rm -rf "$$TMPDIR"

install: check-prereqs
	python3 -m venv "$(VENV_DIR)"
	"$(PIP)" install --upgrade pip
	"$(PIP)" install -r requirements.txt

install-app:
	mkdir -p "$(BIN_DIR)" "$(ICON_DIR)" "$(PIXMAP_DIR)" "$(DESKTOP_DIR)"
	cp img/rsl-icon.png "$(ICON_FILE)"
	cp img/rsl-icon.png "$(PIXMAP_FILE)"
	printf "%s\n" "#!/bin/sh" "APP_DIR=\"$(APP_DIR)\"" "PYTHON=\"$(PYTHON)\"" "LOG_DIR=\"$(LOG_DIR)\"" "LOG_FILE=\"$(LOG_FILE)\"" "PID_FILE=\"$(LOG_DIR)/$(APP_ID).pid\"" "WM_CLASS=\"$(WM_CLASS)\"" "APP_TITLE=\"$(APP_ID)\"" "mkdir -p \"$$LOG_DIR\"" "log() { printf '%s %s\n' \"\$$(date '+%Y-%m-%d %H:%M:%S')\" \"$$*\" >> \"$$LOG_FILE\"; }" "focus_existing() {" "  if wmctrl -xa \"$$WM_CLASS\" >> \"$$LOG_FILE\" 2>&1 || wmctrl -a \"$$APP_TITLE\" >> \"$$LOG_FILE\" 2>&1; then" "    log \"Focused existing app window\"" "    return 0" "  fi" "  log \"Failed to focus existing app window with wmctrl\"" "  return 1" "}" "log \"Launch requested: $$0 $$*\"" "existing_pid=\"\"" "if [ -r \"$$PID_FILE\" ]; then" "  existing_pid=\$$(cat \"$$PID_FILE\")" "  if ! kill -0 \"$$existing_pid\" >/dev/null 2>&1; then" "    log \"Removing stale PID file for PID $$existing_pid\"" "    rm -f \"$$PID_FILE\"" "    existing_pid=\"\"" "  fi" "fi" "if [ -z \"$$existing_pid\" ]; then" "  existing_pid=\$$(pgrep -f \"python.*gui.py\" | grep -v \"^$$$$\" | head -n 1 || true)" "fi" "if [ -n \"$$existing_pid\" ]; then" "  log \"Existing app process detected: PID $$existing_pid\"" "  focus_existing" "  exit 0" "fi" "cd \"$$APP_DIR\" || { log \"Failed to cd into $$APP_DIR\"; exit 1; }" "echo \"$$$$\" > \"$$PID_FILE\"" "trap 'rm -f \"$$PID_FILE\"' EXIT INT TERM" "log \"Starting app with $$PYTHON\"" "\"$$PYTHON\" gui.py \"$$@\" >> \"$$LOG_FILE\" 2>&1" "status=$$?" "log \"App exited with status $$status\"" "exit \"$$status\"" > "$(BIN_FILE)"
	chmod +x "$(BIN_FILE)"
	printf "%s\n" "[Desktop Entry]" "Type=Application" "Name=RSLManagerForLinux" "Comment=Raid Shadow Legends launcher and process manager for Linux" "Exec=$(BIN_FILE)" "Icon=$(PIXMAP_FILE)" "Terminal=false" "Categories=Game;Utility;" "StartupWMClass=$(WM_CLASS)" > "$(DESKTOP_FILE)"
	chmod +x "$(DESKTOP_FILE)"
	update-desktop-database "$(DESKTOP_DIR)" >/dev/null 2>&1 || true
	gtk-update-icon-cache "$(HOME)/.local/share/icons/hicolor" >/dev/null 2>&1 || true
	touch "$(PROFILE_FILE)"
	@grep -qxF 'export PATH="$$HOME/.local/bin:$$PATH"' "$(PROFILE_FILE)" || printf "%s\n" "" "# Added by RSLManagerForLinux installer" 'export PATH="$$HOME/.local/bin:$$PATH"' >> "$(PROFILE_FILE)"
	@case ":$$PATH:" in *:$(BIN_DIR):*) ;; *) echo "Added $(BIN_DIR) to $(PROFILE_FILE). Run '. $(PROFILE_FILE)' or open a new login session to use $(APP_ID) from this shell."; ;; esac

run:
	@mkdir -p "$(LOG_DIR)"
	@if [ -x "$(BIN_FILE)" ]; then setsid "$(BIN_FILE)" >/tmp/RSLManagerForLinux.log 2>&1 & elif [ -x "$(PYTHON)" ]; then setsid "$(PYTHON)" gui.py >> "$(LOG_FILE)" 2>&1 & else setsid python3 gui.py >> "$(LOG_FILE)" 2>&1 & fi
	@echo "RSLManagerForLinux started in the background. Log: $(LOG_FILE)"

check:
	@if [ -x "$(PYTHON)" ]; then "$(PYTHON)" -m py_compile config.py process.py gui.py; else python3 -m py_compile config.py process.py gui.py; fi
