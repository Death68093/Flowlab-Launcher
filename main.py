import os
import sys
import shutil
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

# --------- Config / constants ---------
MODDER_EXE = "FlowlabModdingUtility.exe"
GAMES_FOLDER_NAME = "games"  # folder inside launcher dir where games live
MODDED_EXT = ".exe"
STATUS_POLL_MS = 2000  # ms to poll modder running status

# --------- Helpers ---------
def get_base_dir():
    # Works when running as script or as frozen exe
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.abspath(os.path.dirname(sys.argv[0]) or os.getcwd())

def is_process_running(exe_name: str) -> bool:
    exe_name = exe_name.lower()
    try:
        import psutil
        for p in psutil.process_iter(["name"]):
            name = p.info.get("name")
            if name and name.lower() == exe_name:
                return True
    except Exception:
        pass
    try:
        out = subprocess.check_output(["tasklist"], text=True, stderr=subprocess.DEVNULL)
        return exe_name in out.lower()
    except Exception:
        return False

def safe_copy_file(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)

def safe_copy_folder(src, dst):
    if os.path.exists(dst):
        shutil.copytree(src, dst, dirs_exist_ok=True)
    else:
        shutil.copytree(src, dst)

# --------- Launcher App ---------
class FlowlabLauncher(tk.Tk):
    def __init__(self):
        super().__init__()
        self.base_dir = get_base_dir()
        self.games_dir = os.path.join(self.base_dir, GAMES_FOLDER_NAME)
        os.makedirs(self.games_dir, exist_ok=True)

        self.title("Flowlab Modding Launcher")
        self.geometry("900x600")
        self.minsize(700, 450)

        self.games = []  # list of full paths to found .exe games

        self._build_ui()
        self.scan_games()        # initial scan
        self._poll_modder_status()  # start status polling

    # ---------- UI ----------
    def _build_ui(self):
        # Notebook tabs
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True)

        # Games tab
        self.tab_games = ttk.Frame(nb)
        nb.add(self.tab_games, text="Games")

        games_top = ttk.Frame(self.tab_games)
        games_top.pack(fill="x", padx=10, pady=(10, 6))

        self.btn_scan = ttk.Button(games_top, text="Scan games/", command=self.scan_games)
        self.btn_scan.pack(side="left")

        self.btn_upload_files = ttk.Button(games_top, text="Upload .exe(s) → games/", command=self.upload_files)
        self.btn_upload_files.pack(side="left", padx=8)

        self.btn_upload_folder = ttk.Button(games_top, text="Upload Folder → games/", command=self.upload_folder)
        self.btn_upload_folder.pack(side="left", padx=8)

        self.games_listbox = tk.Listbox(self.tab_games, activestyle="none")
        self.games_listbox.pack(fill="both", expand=True, padx=10, pady=(6,10))
        self.games_listbox.bind("<Double-1>", lambda e: self.play_selected_game())

        # Launcher tab
        self.tab_launcher = ttk.Frame(nb)
        nb.add(self.tab_launcher, text="Launcher")

        launcher_top = ttk.Frame(self.tab_launcher)
        launcher_top.pack(fill="x", padx=10, pady=10)

        self.modder_status_label = ttk.Label(launcher_top, text="Modder status: unknown")
        self.modder_status_label.pack(side="left")

        self.btn_launch_modder = ttk.Button(launcher_top, text=f"Launch {MODDER_EXE}", command=self.launch_modder)
        self.btn_launch_modder.pack(side="right")

        # modded games list and actions
        mod_frame = ttk.Frame(self.tab_launcher)
        mod_frame.pack(fill="both", expand=True, padx=10, pady=(6,10))

        self.modded_listbox = tk.Listbox(mod_frame, activestyle="none")
        self.modded_listbox.pack(side="left", fill="both", expand=True)
        self.modded_listbox.bind("<Double-1>", lambda e: self.play_selected_game(from_modded=True))

        scrollbar = ttk.Scrollbar(mod_frame, orient="vertical", command=self.modded_listbox.yview)
        scrollbar.pack(side="left", fill="y")
        self.modded_listbox.config(yscrollcommand=scrollbar.set)

        actions = ttk.Frame(self.tab_launcher)
        actions.pack(fill="x", padx=10, pady=(6,10))

        self.btn_play = ttk.Button(actions, text="Play Selected", command=self.play_selected_game)
        self.btn_play.pack(side="left", padx=(0,6))
        self.btn_delete = ttk.Button(actions, text="Delete Selected", command=self.delete_selected_game)
        self.btn_delete.pack(side="left", padx=(0,6))
        self.btn_rename = ttk.Button(actions, text="Rename Selected", command=self.rename_selected_game)
        self.btn_rename.pack(side="left", padx=(0,6))
        self.btn_refresh = ttk.Button(actions, text="Refresh Lists", command=self.scan_games)
        self.btn_refresh.pack(side="right")

        # About / footer
        footer = ttk.Frame(self)
        footer.pack(fill="x", padx=10, pady=6)
        ttk.Label(footer, text=f"Games folder: {self.games_dir}").pack(side="left")
        ttk.Label(footer, text=f"Launcher folder: {self.base_dir}").pack(side="right")

    # ---------- Game scanning ----------
    def scan_games(self):
        """Recursively find all .exe files inside games_dir and populate lists."""
        self.games.clear()
        self.games_listbox.delete(0, tk.END)
        self.modded_listbox.delete(0, tk.END)

        for root, dirs, files in os.walk(self.games_dir):
            for fname in files:
                if fname.lower().endswith(MODDED_EXT):
                    full = os.path.join(root, fname)
                    self.games.append(full)

        self.games.sort(key=lambda p: os.path.relpath(p, self.base_dir).lower())

        if not self.games:
            self.games_listbox.insert(tk.END, "(No games found in games/)")
        else:
            for p in self.games:
                display = os.path.relpath(p, self.base_dir)
                self.games_listbox.insert(tk.END, display)
                self.modded_listbox.insert(tk.END, display)

    # ---------- Upload ----------
    def upload_files(self):
        files = filedialog.askopenfilenames(title="Select game .exe files to upload", filetypes=[("EXE files", "*.exe")])
        if not files:
            return
        for src in files:
            try:
                dst = os.path.join(self.games_dir, os.path.basename(src))
                safe_copy_file(src, dst)
            except Exception as e:
                messagebox.showerror("Upload error", f"Failed to copy {src}:\n{e}")
        self.scan_games()

    def upload_folder(self):
        src = filedialog.askdirectory(title="Select a folder to upload into games/")
        if not src:
            return
        try:
            base_name = os.path.basename(os.path.normpath(src))
            dst = os.path.join(self.games_dir, base_name)
            safe_copy_folder(src, dst)
        except Exception as e:
            messagebox.showerror("Upload error", f"Failed to copy folder:\n{e}")
        self.scan_games()

    # ---------- Modder / launcher ----------
    def _modder_path(self):
        return os.path.join(self.base_dir, MODDER_EXE)

    def _update_modder_label(self, running: bool):
        text = f"Modder status: {'running' if running else 'not running'}"
        self.modder_status_label.config(text=text)

    def _poll_modder_status(self):
        running = is_process_running(MODDER_EXE)
        self._update_modder_label(running)
        self.after(STATUS_POLL_MS, self._poll_modder_status)

    def launch_modder(self):
        modder = self._modder_path()
        if not os.path.exists(modder):
            messagebox.showerror("Launch error", f"{MODDER_EXE} not found in launcher folder:\n{modder}")
            return
        try:
            subprocess.Popen([modder], cwd=self.base_dir)
            self._update_modder_label(True)
        except Exception as e:
            messagebox.showerror("Launch error", f"Failed to launch modder:\n{e}")

    # ---------- Play / delete / rename ----------
    def _get_selected_game(self, from_modded=False):
        lb = self.modded_listbox if from_modded else self.games_listbox
        sel = lb.curselection()
        if not sel:
            return None
        idx = sel[0]
        if idx >= len(self.games):
            return None
        return self.games[idx]

    def play_selected_game(self, from_modded=False):
        if from_modded:
            lb = self.modded_listbox
            sel = lb.curselection()
            if not sel:
                messagebox.showwarning("Play", "No game selected.")
                return
            display = lb.get(sel[0])
            full = os.path.join(self.base_dir, display) if not os.path.isabs(display) else display
            if not os.path.exists(full):
                matches = [p for p in self.games if os.path.relpath(p, self.base_dir) == display or os.path.basename(p) == os.path.basename(display)]
                full = matches[0] if matches else None
        else:
            full = self._get_selected_game(from_modded=False)

        if not full or not os.path.exists(full):
            messagebox.showerror("Play", "Selected game not found.")
            return
        try:
            subprocess.Popen([full], cwd=os.path.dirname(full))
        except Exception as e:
            messagebox.showerror("Play error", f"Failed to launch game:\n{e}")

    def delete_selected_game(self):
        sel = self.modded_listbox.curselection()
        if not sel:
            messagebox.showwarning("Delete", "No game selected.")
            return
        display = self.modded_listbox.get(sel[0])
        full = os.path.join(self.base_dir, display) if not os.path.isabs(display) else display
        if not os.path.exists(full):
            matches = [p for p in self.games if os.path.relpath(p, self.base_dir) == display or os.path.basename(p) == os.path.basename(display)]
            full = matches[0] if matches else None
        if not full:
            messagebox.showerror("Delete", "Could not resolve selected game path.")
            return
        confirm = messagebox.askyesno("Delete", f"Delete:\n{full}\n\nThis will permanently remove the file.")
        if not confirm:
            return
        try:
            os.remove(full)
            self.scan_games()
        except Exception as e:
            messagebox.showerror("Delete error", f"Failed to delete:\n{e}")

    def rename_selected_game(self):
        sel = self.modded_listbox.curselection()
        if not sel:
            messagebox.showwarning("Rename", "No game selected.")
            return
        display = self.modded_listbox.get(sel[0])
        matches = [p for p in self.games if os.path.relpath(p, self.base_dir) == display or os.path.basename(p) == os.path.basename(display)]
        full = matches[0] if matches else None
        if not full or not os.path.exists(full):
            messagebox.showerror("Rename", "Could not resolve selected game path.")
            return
        new_name = simpledialog.askstring("Rename", "New filename (must end with .exe):", initialvalue=os.path.basename(full))
        if not new_name:
            return
        if not new_name.lower().endswith(".exe"):
            messagebox.showerror("Rename", "Filename must end with .exe")
            return
        new_path = os.path.join(os.path.dirname(full), new_name)
        try:
            os.rename(full, new_path)
            self.scan_games()
        except Exception as e:
            messagebox.showerror("Rename error", f"Failed to rename:\n{e}")

# --------- Run app ---------
if __name__ == "__main__":
    app = FlowlabLauncher()
    app.mainloop()
