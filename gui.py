import io
import json
import os
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path
from typing import Any, Dict, List

import customtkinter as ctk
import tkinter as tk
from PIL import Image
from tkinter import filedialog, messagebox

import config as config_module
import process as process_module

REFRESH_MS_DEFAULT = 1000
PROMO_CODE_URL = "https://raid-promo-link-finder.vercel.app/"
CHAMPION_INFO_URL = "https://rsl-x.vercel.app/tools/champions-index"
PLARIUM_URL = "https://plarium.com/en/plarium-play/"
PROTON_GE_URL = "https://github.com/GloriousEggroll/proton-ge-custom/releases/download/GE-Proton10-10/GE-Proton10-10.tar.gz"
UPDATE_REMOTE_URL = "https://github.com/koralis-gh/RSLManagerForLinux.git"
UPDATE_REMOTE_BRANCH = "main"
APP_ICON_PATH = Path(__file__).resolve().parent / "img" / "rsl-icon.png"
APP_BANNER_PATH = Path(__file__).resolve().parent / "img" / "rsl-banner.png"
APP_LOG_PATH = config_module.get_app_log_path()


class RSLManagerApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__(className="RSLManagerForLinux")
        self.title("RSLManagerForLinux")
        self.geometry("980x760")
        self.minsize(900, 680)
        self._set_window_icon()

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.config_data: Dict[str, Any] = {}
        self.config_messages: List[str] = []
        self.proton_available = False
        self.windows_dotnet_available = False
        self.refresh_interval_ms = REFRESH_MS_DEFAULT
        self.process_refresh_job = None
        self.last_process_signature: tuple[tuple[int, ...], tuple[int, ...], bool] | None = None
        self.launch_in_progress = False
        self.launch_button_reset_job = None
        self.config_mtime = 0.0
        self.proton_progress_window = None
        self.proton_progress_bar = None
        self.proton_progress_label = None
        self.show_window_numbers_var = tk.BooleanVar(value=False)
        self.window_number_overlays: dict[str, tk.Toplevel] = {}
        self.window_number_refresh_job = None
        self.raid_window_pid_order: dict[int, int] = {}
        self.update_available_commit = ""
        self.update_check_in_progress = False
        self.header_icon_image = self._load_header_icon_image(max_size=150)
        self.header_banner_source = self._load_header_banner_source()
        self.header_banner_image = self._resize_header_banner_image(1000)
        self.last_banner_width = 0

        self._create_widgets()
        self._load_config()
        self._refresh_state()
        self.after(1000, self._start_update_check)

    def _set_window_icon(self) -> None:
        if not APP_ICON_PATH.exists():
            return

        try:
            self.icon_image = tk.PhotoImage(file=str(APP_ICON_PATH))
            self.iconphoto(True, self.icon_image)
        except tk.TclError:
            self.icon_image = None

    def _load_header_icon_image(self, max_size: int) -> tk.PhotoImage | None:
        if not APP_ICON_PATH.exists():
            return None

        try:
            image = tk.PhotoImage(file=str(APP_ICON_PATH))
        except tk.TclError:
            return None

        largest_side = max(image.width(), image.height())
        scale = max(1, -(-largest_side // max_size))
        return image.subsample(scale, scale)

    def _load_header_banner_source(self) -> Image.Image | None:
        if not APP_BANNER_PATH.exists():
            return None

        try:
            return Image.open(APP_BANNER_PATH).convert("RGBA")
        except OSError:
            return None

    def _resize_header_banner_image(self, target_width: int) -> tk.PhotoImage | None:
        if self.header_banner_source is None:
            return None

        source_width, source_height = self.header_banner_source.size
        width = max(320, min(target_width, source_width))
        height = max(1, round(source_height * (width / source_width)))
        resized = self.header_banner_source.resize((width, height), Image.Resampling.LANCZOS)

        buffer = io.BytesIO()
        resized.save(buffer, format="PNG")
        return tk.PhotoImage(data=buffer.getvalue())

    def _resize_header_banner_to_frame(self, event: tk.Event | None = None) -> None:
        frame_width = self.header_frame.winfo_width()
        if frame_width <= 1:
            return

        target_width = max(320, frame_width - 24)
        if abs(target_width - self.last_banner_width) < 16:
            return

        banner_image = self._resize_header_banner_image(target_width)
        if banner_image is None:
            return

        self.last_banner_width = target_width
        self.header_banner_image = banner_image
        self.banner_label.configure(image=self.header_banner_image)

    def _create_widgets(self) -> None:
        # Configure main layout grid
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Header frame and title area
        self.header_frame = ctk.CTkFrame(self, fg_color="#1a1a1a")
        self.header_frame.grid(row=0, column=0, sticky="nsew", padx=16, pady=(16, 8))
        self.header_frame.grid_columnconfigure(0, weight=1)
        self.header_frame.bind("<Configure>", self._resize_header_banner_to_frame)

        self.banner_label = tk.Label(
            self.header_frame,
            image=self.header_banner_image,
            bg="#1a1a1a",
            borderwidth=0,
            highlightthickness=0,
        )
        self.banner_label.grid(row=0, column=0, sticky="w", padx=12, pady=(12, 6))

        # Promo and helper buttons
        self.button_frame = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        self.button_frame.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 12))
        self.button_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self.promo_button = ctk.CTkButton(self.button_frame, text="Promo Code Chooser", command=lambda: webbrowser.open(PROMO_CODE_URL), width=170)
        self.promo_button.grid(row=0, column=0, padx=4, pady=3, sticky="ew")
        self.champion_button = ctk.CTkButton(self.button_frame, text="Champion Info", command=lambda: webbrowser.open(CHAMPION_INFO_URL), width=140)
        self.champion_button.grid(row=0, column=1, padx=4, pady=3, sticky="ew")
        self.edit_config_button = ctk.CTkButton(self.button_frame, text="Edit Config", command=self._show_setup_frame)
        self.edit_config_button.grid(row=0, column=2, padx=4, pady=3, sticky="ew")
        self.open_log_button = ctk.CTkButton(self.button_frame, text="Open Log", command=self._open_log_file)
        self.open_log_button.grid(row=0, column=3, padx=4, pady=3, sticky="ew")
        self.new_raid_button = ctk.CTkButton(self.button_frame, text="New Raid Process", command=self._start_new_process)
        self.new_raid_button.grid(row=1, column=0, columnspan=4, padx=4, pady=3, sticky="ew")
        self.update_button = ctk.CTkButton(self.button_frame, text="Update Available", command=self._run_update)
        self.update_button.grid(row=2, column=0, columnspan=4, padx=4, pady=3, sticky="ew")
        self.update_button.grid_remove()

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
        self.setup_scroll.grid_rowconfigure(6, weight=1)

        title = ctk.CTkLabel(self.setup_scroll, text="Setup / Config", font=ctk.CTkFont(size=20, weight="bold"))
        title.grid(row=0, column=0, sticky="w", pady=(0, 12))

        self.setup_info_label = ctk.CTkLabel(self.setup_scroll, text="Please provide the Raid setup executable.", wraplength=760, justify="left")
        self.setup_info_label.grid(row=1, column=0, sticky="w", pady=(0, 16))

        # Raid setup executable selection
        self.game_path_entry = ctk.CTkEntry(self.setup_scroll, placeholder_text="Path to RaidSetup.exe")
        self.game_path_entry.grid(row=2, column=0, sticky="ew", pady=(0, 6))

        button_row = ctk.CTkFrame(self.setup_scroll, fg_color="transparent")
        button_row.grid(row=3, column=0, sticky="w", pady=(0, 12))
        self.choose_game_button = ctk.CTkButton(button_row, text="Browse RaidSetup.exe", command=self._browse_game_exe)
        self.choose_game_button.grid(row=0, column=0, padx=(0, 4))

        # Prefix scanning helper
        self.scan_prefix_button = ctk.CTkButton(self.setup_scroll, text="Scan for existing RSLManagerForLinux prefixes", command=self._scan_prefixes)
        self.scan_prefix_button.grid(row=4, column=0, sticky="w", pady=(0, 12))

        # Raw JSON config editor
        self.raw_config_label = ctk.CTkLabel(self.setup_scroll, text="Raw config JSON", font=ctk.CTkFont(size=16, weight="bold"))
        self.raw_config_label.grid(row=5, column=0, sticky="w", pady=(12, 6))

        self.raw_config_box = ctk.CTkTextbox(self.setup_scroll, width=760, height=95)
        self.raw_config_box.grid(row=6, column=0, sticky="nsew", pady=(0, 12))

        self.apply_json_button = ctk.CTkButton(self.setup_scroll, text="Apply JSON", command=self._apply_json)
        self.apply_json_button.grid(row=7, column=0, sticky="w", pady=(0, 12))

        self.reload_config_button = ctk.CTkButton(self.setup_scroll, text="Reload Config", command=self._reload_config)
        self.reload_config_button.grid(row=8, column=0, sticky="w", pady=(0, 12))

        # Main setup action buttons
        action_row = ctk.CTkFrame(self.setup_scroll, fg_color="transparent")
        action_row.grid(row=9, column=0, sticky="ew", pady=(0, 12))
        action_row.grid_columnconfigure((0, 1, 2), weight=1)

        self.create_config_button = ctk.CTkButton(action_row, text="Create Config", command=self._save_config)
        self.create_config_button.grid(row=0, column=0, padx=4, pady=4, sticky="ew")
        self.get_plarium_button = ctk.CTkButton(action_row, text="Get Plarium", command=lambda: webbrowser.open(PLARIUM_URL))
        self.get_plarium_button.grid(row=0, column=1, padx=4, pady=4, sticky="ew")
        self.diagnose_button = ctk.CTkButton(action_row, text="Diagnose", command=self._run_diagnostics)
        self.diagnose_button.grid(row=0, column=2, padx=4, pady=4, sticky="ew")

        # Setup status and validation messages
        self.setup_status_label = ctk.CTkLabel(
            self.setup_scroll,
            text="",
            wraplength=760,
            justify="left",
            font=ctk.CTkFont(size=15, weight="bold"),
        )
        self.setup_status_label.grid(row=10, column=0, sticky="w", pady=(8, 0))

    def _create_process_frame(self) -> None:
        self.process_frame.grid(row=0, column=0, sticky="nsew")
        self.process_frame.grid_columnconfigure(0, weight=1)
        self.process_frame.grid_rowconfigure(3, weight=1)

        # Process page header and status message
        header_label = ctk.CTkLabel(self.process_frame, text="Raid process dashboard", font=ctk.CTkFont(size=20, weight="bold"))
        header_label.grid(row=0, column=0, sticky="w", padx=20, pady=(20, 8))

        self.process_status_label = ctk.CTkLabel(self.process_frame, text="", wraplength=760, justify="left")
        self.process_status_label.grid(row=1, column=0, sticky="w", padx=20, pady=(0, 12))

        self.window_number_checkbox = ctk.CTkCheckBox(
            self.process_frame,
            text="Show window numbers",
            variable=self.show_window_numbers_var,
            command=self._toggle_window_number_overlays,
        )
        self.window_number_checkbox.grid(row=2, column=0, sticky="w", padx=20, pady=(0, 8))

        self.raid_cards_frame = ctk.CTkScrollableFrame(self.process_frame, fg_color="#1a1a1a")
        self.raid_cards_frame.grid(row=3, column=0, sticky="nsew", padx=20, pady=(4, 20))
        self.raid_cards_frame.grid_columnconfigure(0, weight=1)

    # Config load and population methods
    def _load_config(self) -> None:
        try:
            self.config_data = config_module.load_config()
        except ValueError as exc:
            self.config_data = dict(config_module.DEFAULT_CONFIG)
            messagebox.showerror("Config Error", str(exc))

        self._populate_setup_fields()
        self.config_mtime = self._get_config_mtime()

    # Setup form population helpers
    def _populate_setup_fields(self) -> None:
        self.game_path_entry.delete(0, "end")
        self.game_path_entry.insert(0, str(self.config_data.get("game_exe_path", "")))

        prefix_path = str(self.config_data.get("prefix_path", ""))
        if not prefix_path:
            self.config_data["prefix_path"] = str(config_module.get_default_prefix())

        self._refresh_config_text()

    def _refresh_config_text(self) -> None:
        self.raw_config_box.delete("1.0", "end")
        self.raw_config_box.insert("1.0", json.dumps(self.config_data, indent=2))

    # File browser helpers
    def _browse_game_exe(self) -> None:
        selected = filedialog.askopenfilename(
            title="Select RaidSetup.exe",
            initialdir=str(Path.home() / "Downloads"),
        )
        if selected:
            self.game_path_entry.delete(0, "end")
            self.game_path_entry.insert(0, selected)
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
            self.config_mtime = self._get_config_mtime()
            self._refresh_state()
        except json.JSONDecodeError as exc:
            messagebox.showerror("JSON Error", f"Unable to parse JSON: {exc}")
        except ValueError as exc:
            messagebox.showerror("Config Error", str(exc))

    def _reload_config(self) -> None:
        try:
            self.config_data = config_module.load_config()
        except ValueError as exc:
            messagebox.showerror("Config Error", str(exc))
            return
        self._populate_setup_fields()
        self.config_mtime = self._get_config_mtime()
        self._refresh_state()

    # Config persistence helpers
    def _save_config_data(self) -> None:
        try:
            config_module.save_config(self.config_data)
            self.config_mtime = self._get_config_mtime()
        except OSError as exc:
            messagebox.showerror("Save Error", f"Unable to write config: {exc}")

    def _get_config_mtime(self) -> float:
        config_path = config_module.get_config_path()
        try:
            return config_path.stat().st_mtime
        except OSError:
            return 0.0

    def _has_config_changed_on_disk(self) -> bool:
        config_path = config_module.get_config_path()
        try:
            current_mtime = config_path.stat().st_mtime
            return self.config_mtime != 0.0 and current_mtime != self.config_mtime
        except OSError:
            return False

    def _save_config(self) -> None:
        if self._has_config_changed_on_disk():
            messagebox.showwarning(
                "Config Changed",
                "The configuration file has changed on disk. Reload it first before saving to avoid overwriting your changes.",
            )
            return

        self._update_config_from_fields()
        self._save_config_data()
        self._refresh_state()
        messagebox.showinfo("Config Saved", "Config has been saved.")

    def _update_config_from_fields(self) -> None:
        self.config_data["game_exe_path"] = self.game_path_entry.get().strip()
        self._refresh_config_text()

    # Proton prefix scanning helpers
    def _scan_prefixes(self) -> None:
        candidates = config_module.scan_existing_prefixes()
        if not candidates:
            messagebox.showinfo("Prefix Scan", "No existing RSLManagerForLinux prefixes were found. A default prefix will be created when you launch Raid.")
            return

        if len(candidates) == 1:
            chosen = candidates[0]
        else:
            dialog_text = "\n".join(f"{i + 1}. {path}" for i, path in enumerate(candidates))
            messagebox.showinfo("Prefix candidates", dialog_text)
            chosen = candidates[0]

        self.config_data["prefix_path"] = chosen
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
            messagebox.showinfo(
                "Edit Config",
                "Config file opened. Save any changes and click Reload Config to refresh the app state.",
            )
        except OSError:
            messagebox.showerror("Open Error", f"Unable to open config file: {config_path}")

    def _open_log_file(self) -> None:
        try:
            APP_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            APP_LOG_PATH.touch(exist_ok=True)
            if os.name == "nt":
                os.startfile(APP_LOG_PATH)
            else:
                subprocess.Popen(["xdg-open", str(APP_LOG_PATH)])
        except OSError as exc:
            messagebox.showerror("Open Error", f"Unable to open log file: {APP_LOG_PATH}\n\n{exc}")

    def _start_update_check(self) -> None:
        if self.update_check_in_progress:
            return

        self.update_check_in_progress = True

        def worker() -> None:
            update_commit = ""
            try:
                update_commit = self._find_available_update_commit()
            except (OSError, subprocess.SubprocessError) as exc:
                config_module.append_app_log(f"Update check failed: {exc}")
            finally:
                self.after(0, lambda: self._finish_update_check(update_commit))

        threading.Thread(target=worker, daemon=True).start()

    def _find_available_update_commit(self) -> str:
        repo_root = config_module.get_repo_root()
        try:
            fetch_result = subprocess.run(
                ["git", "fetch", "--quiet", UPDATE_REMOTE_URL, UPDATE_REMOTE_BRANCH],
                cwd=repo_root,
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=30,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            config_module.append_app_log(f"Update check failed: {exc}")
            return ""
        if fetch_result.returncode != 0:
            config_module.append_app_log(f"Update check failed: {fetch_result.stderr.strip()}")
            return ""

        head = self._git_stdout(["git", "rev-parse", "HEAD"])
        remote_head = self._git_stdout(["git", "rev-parse", "FETCH_HEAD"])
        if not head or not remote_head or head == remote_head:
            return ""

        try:
            ancestor_result = subprocess.run(
                ["git", "merge-base", "--is-ancestor", head, remote_head],
                cwd=repo_root,
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            config_module.append_app_log(f"Update check failed: {exc}")
            return ""
        if ancestor_result.returncode != 0:
            config_module.append_app_log("Update check found a remote commit, but local branch is not a fast-forward.")
            return ""

        return remote_head

    def _git_stdout(self, command: list[str]) -> str:
        try:
            result = subprocess.run(
                command,
                cwd=config_module.get_repo_root(),
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                timeout=10,
            )
        except (OSError, subprocess.SubprocessError):
            return ""
        if result.returncode != 0:
            return ""
        return result.stdout.strip()

    def _finish_update_check(self, update_commit: str) -> None:
        self.update_check_in_progress = False
        self.update_available_commit = update_commit
        if not update_commit:
            self.update_button.grid_remove()
            return

        self.update_button.configure(text=f"Update Available ({update_commit[:7]})", state="normal")
        self.update_button.grid()

    def _run_update(self) -> None:
        self.update_button.configure(text="Updating...", state="disabled")

        def worker() -> None:
            try:
                result = subprocess.run(
                    ["git", "pull", "--ff-only", UPDATE_REMOTE_URL, UPDATE_REMOTE_BRANCH],
                    cwd=config_module.get_repo_root(),
                    check=False,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    timeout=120,
                )
                output = result.stdout.strip()
            except (OSError, subprocess.SubprocessError) as exc:
                self.after(0, lambda: self._show_update_failed(str(exc)))
                return

            if result.returncode != 0:
                self.after(0, lambda: self._show_update_failed(output or "git pull failed."))
                return

            config_module.append_app_log(f"Update applied: {output}")
            self.after(0, self._restart_after_update)

        threading.Thread(target=worker, daemon=True).start()

    def _show_update_failed(self, output: str) -> None:
        self.update_button.configure(text="Update Available", state="normal")
        messagebox.showerror("Update Failed", output)

    def _restart_after_update(self) -> None:
        config_module.append_app_log("Restarting after update")
        os.chdir(config_module.get_repo_root())
        os.execv(sys.executable, [sys.executable, str(Path(__file__).resolve())])

    def _run_diagnostics(self) -> None:
        self._update_config_from_fields()
        self._save_config_data()
        self.diagnose_button.configure(state="disabled", text="Checking...")

        def worker() -> None:
            try:
                result = subprocess.run(
                    ["make", "diagnose"],
                    cwd=config_module.get_repo_root(),
                    check=False,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    timeout=30,
                )
                output = result.stdout.strip() or "No diagnostic output."
            except (OSError, subprocess.SubprocessError) as exc:
                fallback = "\n".join(config_module.get_dependency_diagnostics(self.config_data.get("prefix_path", "")))
                output = f"{fallback}\n\nUnable to run make diagnose: {exc}"

            self.after(0, lambda: self._show_diagnostics(output))

        threading.Thread(target=worker, daemon=True).start()

    def _show_diagnostics(self, output: str) -> None:
        self.diagnose_button.configure(state="normal", text="Diagnose")
        self._refresh_state()
        messagebox.showinfo("Diagnostics", output)

    # App state refresh helpers
    def _refresh_state(self) -> None:
        self.proton_available = config_module.check_proton_available()
        prefix_path = self.config_data.get("prefix_path", "")
        self.windows_dotnet_available = config_module.check_windows_dotnet_available(prefix_path)
        valid, messages = config_module.validate_config(self.config_data)
        self.config_messages = messages
        if not self.proton_available or not self.windows_dotnet_available:
            detail_lines = config_module.get_dependency_diagnostics(prefix_path)
            detail_lines.append("")
            detail_lines.append("Run `make install` from the repo to install missing dependencies.")
            self._show_setup_frame("\n".join(detail_lines))
            return

        if not valid:
            self._show_setup_frame("Config must have game_exe_path and prefix_path set.")
            return

        self._show_process_frame()
        self._refresh_process_status()

    # Frame switching helpers
    def _show_setup_frame(self, status_text: str = "") -> None:
        self.process_frame.grid_remove()
        self.setup_frame.grid()
        self.new_raid_button.configure(state="disabled", text="New Raid Process")
        self.edit_config_button.configure(state="disabled")
        if "Dependency diagnostics" in status_text or "Proton" in status_text:
            self.setup_status_label.configure(text=status_text, text_color="#ffb86c")
        else:
            self.setup_status_label.configure(text=status_text, text_color=None)
        if self.config_messages:
            self.setup_status_label.configure(text=status_text + "\n" + "\n".join(self.config_messages))

    def _show_process_frame(self) -> None:
        self.setup_frame.grid_remove()
        self.process_frame.grid()
        if not self.launch_in_progress and self.proton_available and self.windows_dotnet_available:
            self.new_raid_button.configure(state="normal", text="New Raid Process")
        self.edit_config_button.configure(state="normal")

    # Process list refresh and UI update
    def _refresh_process_status(self) -> None:
        raid_procs = process_module.get_raid_processes()
        plarium_procs = process_module.get_plarium_processes()
        self.proton_available = config_module.check_proton_available()
        self.windows_dotnet_available = config_module.check_windows_dotnet_available(self.config_data.get("prefix_path", ""))

        process_signature = (
            tuple(
                (
                    proc["pid"],
                    proc.get("window", {}).get("window_id", ""),
                    proc.get("window", {}).get("x", 0),
                    proc.get("window", {}).get("y", 0),
                    proc.get("window", {}).get("width", 0),
                    proc.get("window", {}).get("height", 0),
                )
                for proc in raid_procs
            ),
            tuple(proc["pid"] for proc in plarium_procs),
            self.launch_in_progress,
            self.show_window_numbers_var.get(),
        )
        if process_signature == self.last_process_signature:
            self._sync_window_number_overlays(raid_procs)
            self.process_refresh_job = self.after(self.refresh_interval_ms, self._refresh_process_status)
            return

        self.last_process_signature = process_signature

        self.raid_cards_frame.destroy()
        self.raid_cards_frame = ctk.CTkScrollableFrame(self.process_frame, fg_color="#1a1a1a")
        self.raid_cards_frame.grid(row=3, column=0, sticky="nsew", padx=20, pady=(4, 20))
        self.raid_cards_frame.grid_columnconfigure(0, weight=1)

        if self.launch_in_progress and not raid_procs:
            self.process_status_label.configure(text="Opening Raid in the background...")
        elif plarium_procs and raid_procs:
            self.process_status_label.configure(text=f"{len(raid_procs)} Raid process(es) detected; Plarium launcher activity is running")
        elif plarium_procs:
            self.process_status_label.configure(text="Plarium launcher activity is running")
        elif not raid_procs:
            self.process_status_label.configure(text="No Raid processes currently running")
        else:
            self.process_status_label.configure(text=f"{len(raid_procs)} Raid process(es) detected")

        row_index = 0
        if plarium_procs:
            self._add_plarium_card(plarium_procs, row_index)
            row_index += 1

        for index, proc in enumerate(raid_procs, start=1):
            self._add_raid_card(index, proc, row_index)
            row_index += 1

        self.raid_window_pid_order = {proc["pid"]: index for index, proc in enumerate(raid_procs)}
        self._sync_window_number_overlays(raid_procs)

        if self.process_refresh_job is not None:
            self.after_cancel(self.process_refresh_job)
        self.process_refresh_job = self.after(self.refresh_interval_ms, self._refresh_process_status)

    # Raid process card creation helpers
    def _add_plarium_card(self, procs: List[Dict[str, Any]], row_index: int) -> None:
        card = ctk.CTkFrame(self.raid_cards_frame, fg_color="#252018")
        card.grid(row=row_index, column=0, sticky="ew", pady=8, padx=8)
        card.grid_columnconfigure(1, weight=1)

        main_proc = self._choose_main_plarium_process(procs)

        label = ctk.CTkLabel(card, text="Plarium Launcher", font=ctk.CTkFont(size=16, weight="bold"))
        label.grid(row=0, column=0, sticky="w", padx=12, pady=(10, 2))

        pid_label = ctk.CTkLabel(card, text=f"PID: {main_proc['pid']}")
        pid_label.grid(row=0, column=1, sticky="w", padx=12)

        exit_button = ctk.CTkButton(card, text="Exit", width=120, command=self._exit_plarium_processes)
        exit_button.grid(row=0, column=2, sticky="e", padx=12)

    def _choose_main_plarium_process(self, procs: List[Dict[str, Any]]) -> Dict[str, Any]:
        for proc in procs:
            cmdline = proc.get("cmdline", "").lower()
            if "plariumplay.exe" in cmdline and "--type=" not in cmdline:
                return proc
        return procs[0]

    def _add_raid_card(self, index: int, proc: Dict[str, Any], row_index: int) -> None:
        card = ctk.CTkFrame(self.raid_cards_frame, fg_color="#1f1f1f")
        card.grid(row=row_index, column=0, sticky="ew", pady=8, padx=8)
        card.grid_columnconfigure(1, weight=1)

        label = ctk.CTkLabel(card, text=f"Raid Process {index}", font=ctk.CTkFont(size=16, weight="bold"))
        label.grid(row=0, column=0, sticky="w", padx=12, pady=12)

        pid_label = ctk.CTkLabel(card, text=f"PID: {proc['pid']}")
        pid_label.grid(row=0, column=1, sticky="w", padx=12)

        has_window = bool(proc.get("window"))
        button_state = "normal" if has_window else "disabled"
        center_button = ctk.CTkButton(
            card,
            text="><",
            width=48,
            state=button_state,
            command=lambda pid=proc["pid"]: self._center_raid_window(pid),
        )
        center_button.grid(row=0, column=2, sticky="e", padx=(12, 4))

        focus_button = ctk.CTkButton(
            card,
            text="Focus",
            width=100,
            state=button_state,
            command=lambda pid=proc["pid"]: self._focus_raid_window(pid),
        )
        focus_button.grid(row=0, column=3, sticky="e", padx=4)

        exit_button = ctk.CTkButton(card, text="Exit", width=120, command=lambda pid=proc["pid"]: self._exit_raid_process(pid))
        exit_button.grid(row=0, column=4, sticky="e", padx=(4, 12))

    def _get_raid_window_for_pid(self, pid: int) -> Dict[str, Any] | None:
        return process_module.get_raid_window_for_pid(pid)

    def _focus_raid_window(self, pid: int) -> None:
        window = self._get_raid_window_for_pid(pid)
        if window is None:
            self.process_status_label.configure(text=f"No Raid window found for PID {pid}")
            self.last_process_signature = None
            self._refresh_process_status()
            return

        if not process_module.focus_window(str(window["window_id"])):
            self.process_status_label.configure(text=f"Unable to focus Raid window for PID {pid}")
            return

        self.process_status_label.configure(text=f"Focused Raid window for PID {pid}")

    def _center_raid_window(self, pid: int) -> None:
        window = self._get_raid_window_for_pid(pid)
        if window is None:
            self.process_status_label.configure(text=f"No Raid window found for PID {pid}")
            self.last_process_signature = None
            self._refresh_process_status()
            return

        monitor = self._get_monitor_for_window(window)
        screen_x = int(monitor["x"])
        screen_y = int(monitor["y"])
        screen_width = max(1, int(monitor["width"]))
        screen_height = max(1, int(monitor["height"]))
        margin = 48
        max_width = max(320, screen_width - margin)
        max_height = max(240, screen_height - margin)
        width = min(max(320, int(window.get("width", 0) or 0)), max_width)
        height = min(max(240, int(window.get("height", 0) or 0)), max_height)
        x = screen_x + max(0, (screen_width - width) // 2)
        y = screen_y + max(0, (screen_height - height) // 2)

        window_id = str(window["window_id"])
        if not process_module.move_resize_window(window_id, x, y, width, height):
            self.process_status_label.configure(text=f"Unable to center Raid window for PID {pid}")
            return

        process_module.focus_window(window_id)
        self.process_status_label.configure(text=f"Centered Raid window for PID {pid}")

    def _get_monitor_for_window(self, window: Dict[str, Any]) -> Dict[str, int]:
        fallback = {
            "x": 0,
            "y": 0,
            "width": max(1, self.winfo_screenwidth()),
            "height": max(1, self.winfo_screenheight()),
        }
        monitors = process_module.get_monitor_geometries()
        if not monitors:
            return fallback

        window_x = int(window.get("x", 0) or 0)
        window_y = int(window.get("y", 0) or 0)
        window_width = int(window.get("width", 0) or 0)
        window_height = int(window.get("height", 0) or 0)
        center_x = window_x + max(1, window_width) // 2
        center_y = window_y + max(1, window_height) // 2

        for monitor in monitors:
            monitor_x = int(monitor["x"])
            monitor_y = int(monitor["y"])
            monitor_width = int(monitor["width"])
            monitor_height = int(monitor["height"])
            if monitor_x <= center_x < monitor_x + monitor_width and monitor_y <= center_y < monitor_y + monitor_height:
                return {
                    "x": monitor_x,
                    "y": monitor_y,
                    "width": monitor_width,
                    "height": monitor_height,
                }

        def distance_to_monitor(monitor: Dict[str, Any]) -> int:
            monitor_center_x = int(monitor["x"]) + int(monitor["width"]) // 2
            monitor_center_y = int(monitor["y"]) + int(monitor["height"]) // 2
            return abs(center_x - monitor_center_x) + abs(center_y - monitor_center_y)

        nearest = min(monitors, key=distance_to_monitor)
        return {
            "x": int(nearest["x"]),
            "y": int(nearest["y"]),
            "width": int(nearest["width"]),
            "height": int(nearest["height"]),
        }

    def _toggle_window_number_overlays(self) -> None:
        if not self.show_window_numbers_var.get():
            self._cancel_window_number_refresh()
            self._clear_window_number_overlays()
            return
        self.last_process_signature = None
        self._refresh_process_status()
        self._schedule_window_number_refresh()

    def _schedule_window_number_refresh(self) -> None:
        if not self.show_window_numbers_var.get():
            return
        if self.window_number_refresh_job is not None:
            self.after_cancel(self.window_number_refresh_job)
        self.window_number_refresh_job = self.after(50, self._refresh_window_number_overlays)

    def _cancel_window_number_refresh(self) -> None:
        if self.window_number_refresh_job is not None:
            self.after_cancel(self.window_number_refresh_job)
            self.window_number_refresh_job = None

    def _refresh_window_number_overlays(self) -> None:
        self.window_number_refresh_job = None
        if not self.show_window_numbers_var.get():
            self._clear_window_number_overlays()
            return
        numbered_windows = [window for window in process_module.get_raid_windows() if window["pid"] in self.raid_window_pid_order]
        numbered_windows.sort(key=lambda window: self.raid_window_pid_order[window["pid"]])
        self._sync_window_number_overlays_for_windows(numbered_windows)
        self._schedule_window_number_refresh()

    def _sync_window_number_overlays(self, raid_procs: List[Dict[str, Any]]) -> None:
        windows = [proc["window"] for proc in raid_procs if proc.get("window")]
        self._sync_window_number_overlays_for_windows(windows)

    def _sync_window_number_overlays_for_windows(self, windows: List[Dict[str, Any]]) -> None:
        if not self.show_window_numbers_var.get():
            self._clear_window_number_overlays()
            return

        active_window_ids: set[str] = set()
        for index, window in enumerate(windows, start=1):
            window_id = str(window.get("window_id", ""))
            if not window_id:
                continue

            active_window_ids.add(window_id)
            overlay = self.window_number_overlays.get(window_id)
            if overlay is None or not overlay.winfo_exists():
                overlay = self._create_window_number_overlay(index)
                self.window_number_overlays[window_id] = overlay
            else:
                label = overlay.children.get("number_label")
                if isinstance(label, tk.Label):
                    label.configure(text=str(index))

            x = int(window.get("x", 0)) + 12
            y = int(window.get("y", 0)) + 28
            overlay.update_idletasks()
            overlay.geometry(f"72x54+{x}+{y}")
            overlay.deiconify()
            overlay.attributes("-topmost", True)
            overlay.lift()
            overlay.update()

        for window_id in list(self.window_number_overlays):
            if window_id not in active_window_ids:
                overlay = self.window_number_overlays.pop(window_id)
                overlay.destroy()

    def _create_window_number_overlay(self, index: int) -> tk.Toplevel:
        overlay = tk.Toplevel()
        overlay.overrideredirect(True)
        overlay.attributes("-topmost", True)
        overlay.configure(bg="#111111")
        label = tk.Label(
            overlay,
            name="number_label",
            text=str(index),
            bg="#111111",
            fg="#f8d44c",
            font=("TkDefaultFont", 36, "bold"),
            padx=18,
            pady=6,
        )
        label.pack()
        return overlay

    def _clear_window_number_overlays(self) -> None:
        for overlay in self.window_number_overlays.values():
            if overlay.winfo_exists():
                overlay.destroy()
        self.window_number_overlays.clear()

    # Process launch and control actions
    def _start_new_process(self) -> None:
        self._update_config_from_fields()
        self._save_config_data()
        if not self.proton_available:
            messagebox.showwarning("Proton Missing", "Proton GE is not available. Install it first.")
            self._refresh_state()
            return
        if not self.windows_dotnet_available:
            messagebox.showwarning("Windows .NET Missing", "Windows .NET Desktop Runtime 8 is missing from this Proton prefix. Run `make install` from the repo, then restart the app.")
            self._refresh_state()
            return

        self._set_launch_in_progress()
        for proc in process_module.get_plarium_processes():
            process_module.kill_process(proc["pid"])

        success, message = process_module.launch_raid(
            self.config_data["game_exe_path"], self.config_data["prefix_path"]
        )
        if not success:
            messagebox.showerror("Launch Failed", message)
        self._refresh_process_status()

    def _set_launch_in_progress(self) -> None:
        self.launch_in_progress = True
        self.new_raid_button.configure(state="disabled", text="Opening...")
        self.process_status_label.configure(text="Opening Raid in the background...")
        if self.launch_button_reset_job is not None:
            self.after_cancel(self.launch_button_reset_job)
        self.launch_button_reset_job = self.after(6000, self._reset_launch_button)

    def _reset_launch_button(self) -> None:
        self.launch_in_progress = False
        self.launch_button_reset_job = None
        self.new_raid_button.configure(state="normal", text="New Raid Process")
        self._refresh_process_status()

    def _exit_raid_process(self, pid: int) -> None:
        process_module.kill_process(pid)
        self._refresh_process_status()

    def _exit_plarium_processes(self) -> None:
        for proc in process_module.get_plarium_processes():
            process_module.kill_process(proc["pid"])
        self._refresh_process_status()


if __name__ == "__main__":
    app = RSLManagerApp()
    app.mainloop()
