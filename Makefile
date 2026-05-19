APP_ID := RSLManagerForLinux
WM_CLASS := Rslmanagerforlinux
APP_DIR := $(CURDIR)
VENV_DIR := $(APP_DIR)/.venv
PYTHON := $(VENV_DIR)/bin/python
PIP := $(VENV_DIR)/bin/pip
BIN_DIR := $(HOME)/.local/bin
ICON_DIR := $(HOME)/.local/share/icons/hicolor/256x256/apps
PIXMAP_DIR := $(HOME)/.local/share/pixmaps
DESKTOP_DIR := $(HOME)/.local/share/applications
BIN_FILE := $(BIN_DIR)/$(APP_ID)
DESKTOP_FILE := $(DESKTOP_DIR)/$(APP_ID).desktop
ICON_FILE := $(ICON_DIR)/$(APP_ID).png
PIXMAP_FILE := $(PIXMAP_DIR)/$(APP_ID).png

install:
	python3 -m venv "$(VENV_DIR)"
	"$(PIP)" install --upgrade pip
	"$(PIP)" install -r requirements.txt

install-app:
	mkdir -p "$(BIN_DIR)" "$(ICON_DIR)" "$(PIXMAP_DIR)" "$(DESKTOP_DIR)"
	cp img/rsl-icon.png "$(ICON_FILE)"
	cp img/rsl-icon.png "$(PIXMAP_FILE)"
	printf "%s\n" "#!/bin/sh" "cd \"$(APP_DIR)\" || exit 1" "exec \"$(PYTHON)\" gui.py \"$$@\"" > "$(BIN_FILE)"
	chmod +x "$(BIN_FILE)"
	printf "%s\n" "[Desktop Entry]" "Type=Application" "Name=RSLManagerForLinux" "Comment=Raid Shadow Legends launcher and process manager for Linux" "Exec=$(BIN_FILE)" "Icon=$(PIXMAP_FILE)" "Terminal=false" "Categories=Game;Utility;" "StartupWMClass=$(WM_CLASS)" > "$(DESKTOP_FILE)"
	chmod +x "$(DESKTOP_FILE)"
	update-desktop-database "$(DESKTOP_DIR)" >/dev/null 2>&1 || true
	gtk-update-icon-cache "$(HOME)/.local/share/icons/hicolor" >/dev/null 2>&1 || true
	@case ":$$PATH:" in *:$(BIN_DIR):*) ;; *) echo "Note: add $(BIN_DIR) to PATH to run $(APP_ID) from your shell."; ;; esac

run:
	@if [ -x "$(BIN_FILE)" ]; then setsid "$(BIN_FILE)" >/tmp/RSLManagerForLinux.log 2>&1 & elif [ -x "$(PYTHON)" ]; then setsid "$(PYTHON)" gui.py >/tmp/RSLManagerForLinux.log 2>&1 & else setsid python3 gui.py >/tmp/RSLManagerForLinux.log 2>&1 & fi
	@echo "RSLManagerForLinux started in the background. Log: /tmp/RSLManagerForLinux.log"

check:
	@if [ -x "$(PYTHON)" ]; then "$(PYTHON)" -m py_compile config.py process.py gui.py; else python3 -m py_compile config.py process.py gui.py; fi
