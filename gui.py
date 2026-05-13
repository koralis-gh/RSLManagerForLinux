import json
import os
import subprocess
import webbrowser
from pathlib import Path
from typing import Any, Dict, List

import customtkinter as ctk
from tkinter import filedialog, messagebox

import config as config_module
import process as process_module

REFRESH_MS_DEFAULT = 1000
PROMO_CODE_URL = "https://raid-promo-link-finder.vercel.app/"
CHAMPION_INFO_URL = "https://rsl-x.vercel.app/tools/champions-index"
PLARIUM_URL = "https://plarium.com/en/plarium-play/"
WINE_HELP_URL = "https://wiki.winehq.org/Download"


class RSLManagerApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("RSLManagerForLinux")
        self.geometry("900x700")
        self.minsize(840, 620)

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.config_data: Dict[str, Any] = {}
        self.config_messages: List[str] = []
        self.wine_available = False
        self.refresh_interval_ms = REFRESH_MS_DEFAULT
        self.process_refresh_job = None

        self._create_widgets()
        self._load_config()
        self._refresh_state()

    def _create_widgets(self) -> None:
        # Configure main layout grid
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Header frame and title area
        self.header_frame = ctk.CTkFrame(self, fg_color="#1a1a1a")
        self.header_frame.grid(row=0, column=0, sticky="nsew", padx=16, pady=(16, 8))
        self.header_frame.grid_columnconfigure(1, weight=1)

        self.title_label = ctk.CTkLabel(self.header_frame, text="RSLManagerForLinux", font=ctk.CTkFont(size=24, weight="bold"))
        self.title_label.grid(row=0, column=0, sticky="w", padx=(12, 0), pady=12)

        # Promo and helper buttons
        self.button_frame = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        self.button_frame.grid(row=0, column=1, sticky="e", padx=(0, 12), pady=12)

        self.promo_button = ctk.CTkButton(self.button_frame, text="Promo Code Chooser", command=lambda: webbrowser.open(PROMO_CODE_URL), width=170)
        self.promo_button.grid(row=0, column=0, padx=4)
        self.champion_button = ctk.CTkButton(self.button_frame, text="Champion Info", command=lambda: webbrowser.open(CHAMPION_INFO_URL), width=140)
        self.champion_button.grid(row=0, column=1, padx=4)

        # Main content area containing setup and process pages
        self.content_frame = ctk.CTkFrame(self, fg_color="#111111")
        self.content_frame.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 16))
        self.content_frame.grid_columnconfigure(0, weight=1)
        self.content_frame.grid_rowconfigure(0, weight=1)

        self.setup_frame = ctk.CTkFrame(self.content_frame, fg_color="#161616")
        self.process_frame = ctk.CTkFrame(self.content_frame, fg_color="#161616")

        # Create the setup and process GUI pages
        self._create_setup_frame()
        self._create_process_frame()

    def _create_setup_frame(self) -> None:
        self.setup_frame.grid(row=0, column=0, sticky="nsew")
        self.setup_frame.grid_columnconfigure(0, weight=1)
        self.setup_frame.grid_rowconfigure(0, weight=1)

        # Setup page container and title
        self.setup_scroll = ctk.CTkScrollableFrame(self.setup_frame, fg_color="#1a1a1a")
        self.setup_scroll.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        self.setup_scroll.grid_columnconfigure(0, weight=1)
        self.setup_scroll.grid_rowconfigure(8, weight=1)

        title = ctk.CTkLabel(self.setup_scroll, text="Setup / Config", font=ctk.CTkFont(size=20, weight="bold"))
        title.grid(row=0, column=0, sticky="w", pady=(0, 12))

        self.setup_info_label = ctk.CTkLabel(self.setup_scroll, text="Please provide the Plarium executable and Wine prefix.", wraplength=760, justify="left")
        self.setup_info_label.grid(row=1, column=0, sticky="w", pady=(0, 16))

        # Plarium executable selection
        self.game_path_entry = ctk.CTkEntry(self.setup_scroll, placeholder_text="Path to plarium.exe")
        self.game_path_entry.grid(row=2, column=0, sticky="ew", pady=(0, 6))
        self.choose_game_button = ctk.CTkButton(self.setup_scroll, text="Browse plarium.exe", command=self._browse_game_exe)
        self.choose_game_button.grid(row=3, column=0, sticky="w", pady=(0, 12))

        # Wine prefix selection
        self.prefix_entry = ctk.CTkEntry(self.setup_scroll, placeholder_text="Wine prefix path")
        self.prefix_entry.grid(row=4, column=0, sticky="ew", pady=(0, 6))
        self.choose_prefix_button = ctk.CTkButton(self.setup_scroll, text="Browse wine prefix", command=self._browse_wine_prefix)
        self.choose_prefix_button.grid(row=5, column=0, sticky="w", pady=(0, 12))

        # Prefix scanning helper
        self.scan_prefix_button = ctk.CTkButton(self.setup_scroll, text="Scan for existing RSLManagerForLinux prefixes", command=self._scan_prefixes)
        self.scan_prefix_button.grid(row=6, column=0, sticky="w", pady=(0, 12))

        # Raw JSON config editor
        self.raw_config_label = ctk.CTkLabel(self.setup_scroll, text="Raw config JSON", font=ctk.CTkFont(size=16, weight="bold"))
        self.raw_config_label.grid(row=7, column=0, sticky="w", pady=(12, 6))

        self.raw_config_box = ctk.CTkTextbox(self.setup_scroll, width=760, height=120)
        self.raw_config_box.grid(row=8, column=0, sticky="nsew", pady=(0, 12))

        self.apply_json_button = ctk.CTkButton(self.setup_scroll, text="Apply JSON", command=self._apply_json)
        self.apply_json_button.grid(row=9, column=0, sticky="w", pady=(0, 12))

        # Main setup action buttons
        button_row = ctk.CTkFrame(self.setup_scroll, fg_color="transparent")
        button_row.grid(row=10, column=0, sticky="ew", pady=(0, 12))
        button_row.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self.create_config_button = ctk.CTkButton(button_row, text="Create Config", command=self._save_config)
        self.create_config_button.grid(row=0, column=0, padx=4, pady=4, sticky="ew")
        self.get_plarium_button = ctk.CTkButton(button_row, text="Get Plarium", command=lambda: webbrowser.open(PLARIUM_URL))
        self.get_plarium_button.grid(row=0, column=1, padx=4, pady=4, sticky="ew")
        self.get_wine_button = ctk.CTkButton(button_row, text="Get Wine", command=lambda: webbrowser.open(WINE_HELP_URL))
        self.get_wine_button.grid(row=0, column=2, padx=4, pady=4, sticky="ew")
        self.open_config_button = ctk.CTkButton(button_row, text="Browse config", command=self._open_config_file)
        self.open_config_button.grid(row=0, column=3, padx=4, pady=4, sticky="ew")

        # Setup status and validation messages
        self.setup_status_label = ctk.CTkLabel(self.setup_scroll, text="", wraplength=760, justify="left")
        self.setup_status_label.grid(row=11, column=0, sticky="w", pady=(8, 0))

    def _create_process_frame(self) -> None:
        self.process_frame.grid(row=0, column=0, sticky="nsew")
        self.process_frame.grid_columnconfigure(0, weight=1)
        self.process_frame.grid_rowconfigure(0, weight=1)
        self.process_frame.grid_rowconfigure(2, weight=1)
        self.process_frame.grid_rowconfigure(3, weight=1)

        # Process page header and status message
        header_label = ctk.CTkLabel(self.process_frame, text="Raid process dashboard", font=ctk.CTkFont(size=20, weight="bold"))
        header_label.grid(row=0, column=0, sticky="w", padx=20, pady=(20, 8))

        self.process_status_label = ctk.CTkLabel(self.process_frame, text="", wraplength=760, justify="left")
        self.process_status_label.grid(row=1, column=0, sticky="w", padx=20, pady=(0, 12))

        # Process page action buttons
        action_row = ctk.CTkFrame(self.process_frame, fg_color="transparent")
        action_row.grid(row=2, column=0, sticky="ew", padx=20)
        action_row.grid_columnconfigure((0, 1, 2), weight=1)

        self.new_raid_button = ctk.CTkButton(action_row, text="New Raid Process", command=self._start_new_process)
        self.new_raid_button.grid(row=0, column=0, padx=4, pady=4, sticky="ew")
        self.kill_plarium_button = ctk.CTkButton(action_row, text="Kill plarium.exe", command=self._kill_plarium)
        self.kill_plarium_button.grid(row=0, column=1, padx=4, pady=4, sticky="ew")
        self.open_config_button_2 = ctk.CTkButton(action_row, text="Browse config", command=self._open_config_file)
        self.open_config_button_2.grid(row=0, column=2, padx=4, pady=4, sticky="ew")

        self.raid_cards_frame = ctk.CTkScrollableFrame(self.process_frame, fg_color="#1a1a1a")
        self.raid_cards_frame.grid(row=3, column=0, sticky="nsew", padx=20, pady=(12, 20))
        self.raid_cards_frame.grid_columnconfigure(0, weight=1)

    # Config load and population methods
    def _load_config(self) -> None:
        try:
            self.config_data = config_module.load_config()
        except ValueError as exc:
            self.config_data = dict(config_module.DEFAULT_CONFIG)
            messagebox.showerror("Config Error", str(exc))

        self._populate_setup_fields()

    # Setup form population helpers
    def _populate_setup_fields(self) -> None:
        self.game_path_entry.delete(0, "end")
        self.game_path_entry.insert(0, str(self.config_data.get("game_exe_path", "")))

        self.prefix_entry.delete(0, "end")
        self.prefix_entry.insert(0, str(self.config_data.get("wine_prefix", "")))

        self._refresh_config_text()

    def _refresh_config_text(self) -> None:
        self.raw_config_box.delete("1.0", "end")
        self.raw_config_box.insert("1.0", json.dumps(self.config_data, indent=2))

    # File browser helpers
    def _browse_game_exe(self) -> None:
        selected = filedialog.askopenfilename(title="Select plarium.exe")
        if selected:
            self.game_path_entry.delete(0, "end")
            self.game_path_entry.insert(0, selected)
            self._update_config_from_fields()

    def _browse_wine_prefix(self) -> None:
        selected = filedialog.askdirectory(title="Select Wine prefix")
        if selected:
            self.prefix_entry.delete(0, "end")
            self.prefix_entry.insert(0, selected)
            self._update_config_from_fields()

    # JSON config editing helpers
    def _apply_json(self) -> None:
        raw = self.raw_config_box.get("1.0", "end").strip()
        try:
            new_config = json.loads(raw)
            if not isinstance(new_config, dict):
                raise ValueError("Config must be a JSON object")
            self.config_data = new_config
            self._populate_setup_fields()
            self._save_config_data()
            self._refresh_state()
        except json.JSONDecodeError as exc:
            messagebox.showerror("JSON Error", f"Unable to parse JSON: {exc}")
        except ValueError as exc:
            messagebox.showerror("Config Error", str(exc))

    # Config persistence helpers
    def _save_config_data(self) -> None:
        try:
            config_module.save_config(self.config_data)
        except OSError as exc:
            messagebox.showerror("Save Error", f"Unable to write config: {exc}")

    def _save_config(self) -> None:
        self._update_config_from_fields()
        self._save_config_data()
        self._refresh_state()
        messagebox.showinfo("Config Saved", "Config has been saved.")

    def _update_config_from_fields(self) -> None:
        self.config_data["game_exe_path"] = self.game_path_entry.get().strip()
        self.config_data["wine_prefix"] = self.prefix_entry.get().strip()
        self._refresh_config_text()

    # Wine prefix scanning helpers
    def _scan_prefixes(self) -> None:
        candidates = process_module.scan_existing_prefixes()
        if not candidates:
            messagebox.showinfo("Prefix Scan", "No existing RSLManagerForLinux prefixes were found.")
            return

        if len(candidates) == 1:
            chosen = candidates[0]
        else:
            dialog_text = "\n".join(f"{i + 1}. {path}" for i, path in enumerate(candidates))
            messagebox.showinfo("Prefix candidates", dialog_text)
            chosen = candidates[0]

        self.prefix_entry.delete(0, "end")
        self.prefix_entry.insert(0, chosen)
        self._update_config_from_fields()
        self._refresh_state()

    # External config file helpers
    def _open_config_file(self) -> None:
        config_path = config_module.get_config_path()
        try:
            if os.name == "nt":
                os.startfile(config_path)
            else:
                subprocess.Popen(["xdg-open", str(config_path)])
        except OSError:
            messagebox.showerror("Open Error", f"Unable to open config file: {config_path}")

    # App state refresh helpers
    def _refresh_state(self) -> None:
        self.wine_available = process_module.check_wine_available()
        valid, messages = config_module.validate_config(self.config_data)
        self.config_messages = messages
        if not self.wine_available:
            self._show_setup_frame("Wine not detected. Please install Wine or fix your PATH.")
            return

        if not valid:
            self._show_setup_frame("Config must have game_exe_path and wine_prefix set.")
            return

        self._show_process_frame()
        self._refresh_process_status()

    # Frame switching helpers
    def _show_setup_frame(self, status_text: str = "") -> None:
        self.process_frame.grid_remove()
        self.setup_frame.grid()
        self.setup_status_label.configure(text=status_text)
        if self.config_messages:
            self.setup_status_label.configure(text=status_text + "\n" + "\n".join(self.config_messages))

    def _show_process_frame(self) -> None:
        self.setup_frame.grid_remove()
        self.process_frame.grid()

    # Process list refresh and UI update
    def _refresh_process_status(self) -> None:
        self.raid_cards_frame.destroy()
        self.raid_cards_frame = ctk.CTkScrollableFrame(self.process_frame, fg_color="#1a1a1a")
        self.raid_cards_frame.grid(row=3, column=0, sticky="nsew", padx=20, pady=(12, 20))
        self.raid_cards_frame.grid_columnconfigure(0, weight=1)

        raid_procs = process_module.get_raid_processes()
        plarium_procs = process_module.get_plarium_processes()
        self.wine_available = process_module.check_wine_available()

        if not raid_procs:
            self.process_status_label.configure(text="No Raid processes currently running")
        else:
            self.process_status_label.configure(text=f"{len(raid_procs)} Raid process(es) detected")

        if plarium_procs:
            self.kill_plarium_button.configure(state="normal")
        else:
            self.kill_plarium_button.configure(state="disabled")

        for index, proc in enumerate(raid_procs, start=1):
            self._add_raid_card(index, proc)

        if self.process_refresh_job is not None:
            self.after_cancel(self.process_refresh_job)
        self.process_refresh_job = self.after(self.refresh_interval_ms, self._refresh_process_status)

    # Raid process card creation helpers
    def _add_raid_card(self, index: int, proc: Dict[str, Any]) -> None:
        card = ctk.CTkFrame(self.raid_cards_frame, fg_color="#1f1f1f")
        card.grid(row=index - 1, column=0, sticky="ew", pady=8, padx=8)
        card.grid_columnconfigure(1, weight=1)

        label = ctk.CTkLabel(card, text=f"Raid Process {index}", font=ctk.CTkFont(size=16, weight="bold"))
        label.grid(row=0, column=0, sticky="w", padx=12, pady=12)

        pid_label = ctk.CTkLabel(card, text=f"PID: {proc['pid']}")
        pid_label.grid(row=0, column=1, sticky="w", padx=12)

        exit_button = ctk.CTkButton(card, text="Exit", width=120, command=lambda pid=proc["pid"]: self._exit_raid_process(pid))
        exit_button.grid(row=0, column=2, sticky="e", padx=12)

    # Process launch and control actions
    def _start_new_process(self) -> None:
        self._update_config_from_fields()
        self._save_config_data()
        if not self.wine_available:
            messagebox.showwarning("Wine Missing", "Wine is not available. Install Wine first.")
            return

        plarium_procs = process_module.get_plarium_processes()
        for proc in plarium_procs:
            process_module.kill_process(proc["pid"])

        success, message = process_module.launch_plarium(
            self.config_data["game_exe_path"], self.config_data["wine_prefix"]
        )
        if not success:
            messagebox.showerror("Launch Failed", message)
        self._refresh_process_status()

    def _kill_plarium(self) -> None:
        plarium_procs = process_module.get_plarium_processes()
        if not plarium_procs:
            messagebox.showinfo("No Process", "No plarium.exe process was found.")
            return
        for proc in plarium_procs:
            process_module.kill_process(proc["pid"])
        self._refresh_process_status()

    def _exit_raid_process(self, pid: int) -> None:
        process_module.kill_process(pid)
        self._refresh_process_status()


if __name__ == "__main__":
    app = RSLManagerApp()
    app.mainloop()
