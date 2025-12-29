#!/usr/bin/env python3
"""
Video Subtitle Processing Toolkit - Modern GUI
===============================================

A beautiful graphical interface inspired by UVR5 design.
"""

import os
import sys
import subprocess
import threading
import queue
from pathlib import Path
from datetime import datetime
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# Detect if running as PyInstaller bundle
if getattr(sys, 'frozen', False):
    BUNDLE_DIR = Path(sys._MEIPASS)
    SCRIPT_DIR = Path(sys.executable).parent.resolve()
    IS_FROZEN = True
else:
    BUNDLE_DIR = Path(__file__).parent.resolve()
    SCRIPT_DIR = BUNDLE_DIR
    IS_FROZEN = False


class Theme:
    """Modern dark theme with teal accents (UVR5 style)."""

    # Main colors
    BG_DARK = "#0d1117"
    BG_SECONDARY = "#161b22"
    BG_CARD = "#1c2128"
    BG_INPUT = "#0d1117"
    BG_BUTTON = "#21262d"

    # Accent colors
    ACCENT = "#00d4aa"
    ACCENT_DARK = "#00a080"
    ACCENT_GLOW = "#00ffcc"

    # Text colors
    TEXT = "#e6edf3"
    TEXT_DIM = "#7d8590"
    TEXT_LABEL = "#8b949e"

    # Status colors
    SUCCESS = "#3fb950"
    WARNING = "#d29922"
    ERROR = "#f85149"

    # Fonts
    FONT_LOGO = ("Segoe UI", 28, "bold")
    FONT_SUBTITLE = ("Segoe UI", 10)
    FONT_LABEL = ("Segoe UI", 9)
    FONT_NORMAL = ("Segoe UI", 10)
    FONT_BUTTON = ("Segoe UI", 11, "bold")
    FONT_SMALL = ("Segoe UI", 9)
    FONT_MONO = ("Consolas", 9)


class StyledButton(tk.Canvas):
    """Modern styled button with hover effects."""

    def __init__(self, parent, text, command=None, width=140, height=36,
                 accent=False, icon=None):
        super().__init__(parent, width=width, height=height,
                        bg=Theme.BG_SECONDARY, highlightthickness=0)

        self.text = text
        self.command = command
        self.width = width
        self.height = height
        self.accent = accent
        self.icon = icon
        self.hovered = False
        self.disabled = False

        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)

        self._draw()

    def _draw(self):
        self.delete("all")

        if self.disabled:
            bg = Theme.BG_CARD
            fg = Theme.TEXT_DIM
            border = Theme.BG_CARD
        elif self.accent:
            bg = Theme.ACCENT if not self.hovered else Theme.ACCENT_GLOW
            fg = Theme.BG_DARK
            border = bg
        else:
            bg = Theme.BG_BUTTON if not self.hovered else "#30363d"
            fg = Theme.TEXT
            border = "#30363d" if not self.hovered else Theme.ACCENT

        # Draw rounded rectangle
        r = 6
        self.create_rounded_rect(2, 2, self.width-2, self.height-2, r, bg, border)

        # Draw text
        self.create_text(self.width//2, self.height//2, text=self.text,
                        font=Theme.FONT_NORMAL, fill=fg)

    def create_rounded_rect(self, x1, y1, x2, y2, r, fill, outline):
        """Draw a rounded rectangle."""
        self.create_arc(x1, y1, x1+2*r, y1+2*r, start=90, extent=90, fill=fill, outline=outline)
        self.create_arc(x2-2*r, y1, x2, y1+2*r, start=0, extent=90, fill=fill, outline=outline)
        self.create_arc(x1, y2-2*r, x1+2*r, y2, start=180, extent=90, fill=fill, outline=outline)
        self.create_arc(x2-2*r, y2-2*r, x2, y2, start=270, extent=90, fill=fill, outline=outline)
        self.create_rectangle(x1+r, y1, x2-r, y2, fill=fill, outline="")
        self.create_rectangle(x1, y1+r, x2, y2-r, fill=fill, outline="")
        self.create_line(x1+r, y1, x2-r, y1, fill=outline)
        self.create_line(x1+r, y2, x2-r, y2, fill=outline)
        self.create_line(x1, y1+r, x1, y2-r, fill=outline)
        self.create_line(x2, y1+r, x2, y2-r, fill=outline)

    def _on_enter(self, e):
        if not self.disabled:
            self.hovered = True
            self._draw()

    def _on_leave(self, e):
        self.hovered = False
        self._draw()

    def _on_click(self, e):
        if not self.disabled and self.command:
            self.command()

    def set_disabled(self, disabled):
        self.disabled = disabled
        self._draw()


class FileSelector(tk.Frame):
    """File/folder selector with button and entry."""

    def __init__(self, parent, label, is_folder=False, file_types=None):
        super().__init__(parent, bg=Theme.BG_SECONDARY)

        self.is_folder = is_folder
        self.file_types = file_types or [("All files", "*.*")]
        self.path_var = tk.StringVar()

        # Button
        self.btn = StyledButton(self, label, self._browse, width=120)
        self.btn.pack(side="left", padx=(0, 10))

        # Entry
        self.entry = tk.Entry(
            self, textvariable=self.path_var,
            font=Theme.FONT_NORMAL,
            bg=Theme.BG_INPUT,
            fg=Theme.TEXT,
            insertbackground=Theme.TEXT,
            relief="flat",
            highlightthickness=1,
            highlightbackground=Theme.BG_CARD,
            highlightcolor=Theme.ACCENT
        )
        self.entry.pack(side="left", fill="x", expand=True, ipady=8)

        # Browse icon button
        self.icon_btn = tk.Label(
            self, text="📁", font=("Segoe UI", 14),
            bg=Theme.BG_SECONDARY, fg=Theme.TEXT_DIM,
            cursor="hand2"
        )
        self.icon_btn.pack(side="right", padx=(10, 0))
        self.icon_btn.bind("<Button-1>", lambda e: self._browse())

    def _browse(self):
        if self.is_folder:
            path = filedialog.askdirectory(initialdir=SCRIPT_DIR)
        else:
            path = filedialog.askopenfilename(
                initialdir=SCRIPT_DIR,
                filetypes=self.file_types
            )
        if path:
            self.path_var.set(path)

    def get(self):
        return self.path_var.get()

    def set(self, value):
        self.path_var.set(value)


class LabeledDropdown(tk.Frame):
    """Dropdown with label above."""

    def __init__(self, parent, label, values, default=None):
        super().__init__(parent, bg=Theme.BG_SECONDARY)

        # Label
        tk.Label(
            self, text=label,
            font=Theme.FONT_LABEL,
            fg=Theme.TEXT_LABEL,
            bg=Theme.BG_SECONDARY
        ).pack(anchor="w", pady=(0, 5))

        # Combobox
        self.var = tk.StringVar(value=default or (values[0] if values else ""))

        style = ttk.Style()
        style.configure("Custom.TCombobox",
                       fieldbackground=Theme.BG_INPUT,
                       background=Theme.BG_BUTTON,
                       foreground=Theme.TEXT)

        self.combo = ttk.Combobox(
            self, textvariable=self.var,
            values=values,
            state="readonly",
            font=Theme.FONT_NORMAL,
            width=20
        )
        self.combo.pack(fill="x")

    def get(self):
        return self.var.get()

    def set(self, value):
        self.var.set(value)


class CheckOption(tk.Frame):
    """Styled checkbox option."""

    def __init__(self, parent, text, default=False):
        super().__init__(parent, bg=Theme.BG_SECONDARY)

        self.var = tk.BooleanVar(value=default)

        self.check = tk.Checkbutton(
            self, text=text,
            variable=self.var,
            font=Theme.FONT_NORMAL,
            fg=Theme.TEXT,
            bg=Theme.BG_SECONDARY,
            activebackground=Theme.BG_SECONDARY,
            activeforeground=Theme.TEXT,
            selectcolor=Theme.BG_INPUT,
            highlightthickness=0
        )
        self.check.pack(anchor="w")

    def get(self):
        return self.var.get()


class StatusBar(tk.Frame):
    """Bottom status bar with file indicators."""

    FILES = [
        ("input.mp3", "Audio"),
        ("input.mp4", "Video"),
        ("output.srt", "SRT"),
        ("Penis.txt", "Translation"),
    ]

    def __init__(self, parent):
        super().__init__(parent, bg=Theme.BG_DARK)

        self.indicators = {}

        for filename, label in self.FILES:
            frame = tk.Frame(self, bg=Theme.BG_DARK)
            frame.pack(side="left", padx=15)

            dot = tk.Label(frame, text="●", font=("Segoe UI", 10),
                          fg=Theme.TEXT_DIM, bg=Theme.BG_DARK)
            dot.pack(side="left")

            lbl = tk.Label(frame, text=label, font=Theme.FONT_SMALL,
                          fg=Theme.TEXT_DIM, bg=Theme.BG_DARK)
            lbl.pack(side="left", padx=(5, 0))

            self.indicators[filename] = dot

        # Version label on right
        self.version = tk.Label(
            self, text=f"Video Subtitle Toolkit v1.0 [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]",
            font=Theme.FONT_SMALL,
            fg=Theme.TEXT_DIM,
            bg=Theme.BG_DARK
        )
        self.version.pack(side="right", padx=15)

    def refresh(self):
        for filename, dot in self.indicators.items():
            if (SCRIPT_DIR / filename).exists():
                dot.config(fg=Theme.SUCCESS)
            else:
                dot.config(fg=Theme.TEXT_DIM)


class LogOutput(tk.Frame):
    """Expandable log output panel."""

    def __init__(self, parent):
        super().__init__(parent, bg=Theme.BG_CARD)

        # Header with toggle
        header = tk.Frame(self, bg=Theme.BG_CARD)
        header.pack(fill="x", padx=15, pady=10)

        tk.Label(header, text="OUTPUT LOG", font=Theme.FONT_LABEL,
                fg=Theme.TEXT_LABEL, bg=Theme.BG_CARD).pack(side="left")

        self.clear_btn = tk.Label(header, text="Clear", font=Theme.FONT_SMALL,
                                  fg=Theme.ACCENT, bg=Theme.BG_CARD, cursor="hand2")
        self.clear_btn.pack(side="right")
        self.clear_btn.bind("<Button-1>", lambda e: self.clear())

        # Text widget
        self.text = tk.Text(
            self, font=Theme.FONT_MONO,
            bg=Theme.BG_INPUT,
            fg=Theme.TEXT,
            insertbackground=Theme.TEXT,
            relief="flat",
            height=8,
            padx=10,
            pady=10
        )
        self.text.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        # Scrollbar
        scrollbar = tk.Scrollbar(self.text, command=self.text.yview)
        scrollbar.pack(side="right", fill="y")
        self.text.config(yscrollcommand=scrollbar.set)

        # Tags
        self.text.tag_config("error", foreground=Theme.ERROR)
        self.text.tag_config("success", foreground=Theme.SUCCESS)
        self.text.tag_config("info", foreground=Theme.TEXT_DIM)

    def log(self, message, tag=None):
        self.text.insert("end", message + "\n", tag)
        self.text.see("end")

    def clear(self):
        self.text.delete("1.0", "end")


class MainApplication(tk.Tk):
    """Main application window."""

    def __init__(self):
        super().__init__()

        self.title("Video Subtitle Toolkit")
        self.geometry("800x700")
        self.minsize(700, 600)
        self.configure(bg=Theme.BG_DARK)

        # Configure ttk styles
        self._setup_styles()

        # State
        self.msg_queue = queue.Queue()
        self.is_running = False
        self.running_process = None

        self._create_ui()
        self._check_queue()
        self.status_bar.refresh()

    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')

        style.configure("TCombobox",
                       fieldbackground=Theme.BG_INPUT,
                       background=Theme.BG_BUTTON,
                       foreground=Theme.TEXT,
                       arrowcolor=Theme.TEXT)

        style.map("TCombobox",
                 fieldbackground=[("readonly", Theme.BG_INPUT)],
                 selectbackground=[("readonly", Theme.ACCENT)],
                 selectforeground=[("readonly", Theme.BG_DARK)])

        style.configure("Custom.Horizontal.TProgressbar",
                       background=Theme.ACCENT,
                       troughcolor=Theme.BG_INPUT)

    def _create_ui(self):
        # Main container with padding
        main = tk.Frame(self, bg=Theme.BG_DARK)
        main.pack(fill="both", expand=True, padx=30, pady=20)

        # === HEADER ===
        header = tk.Frame(main, bg=Theme.BG_DARK)
        header.pack(fill="x", pady=(0, 25))

        # Logo
        logo_frame = tk.Frame(header, bg=Theme.BG_DARK)
        logo_frame.pack()

        tk.Label(logo_frame, text="VST", font=Theme.FONT_LOGO,
                fg=Theme.ACCENT, bg=Theme.BG_DARK).pack()
        tk.Label(logo_frame, text="VIDEO SUBTITLE TOOLKIT",
                font=Theme.FONT_SUBTITLE, fg=Theme.TEXT_DIM,
                bg=Theme.BG_DARK).pack()

        # === INPUT/OUTPUT SECTION ===
        io_frame = tk.Frame(main, bg=Theme.BG_SECONDARY)
        io_frame.pack(fill="x", pady=(0, 15), ipady=15, ipadx=15)

        # Working directory display
        dir_frame = tk.Frame(io_frame, bg=Theme.BG_SECONDARY)
        dir_frame.pack(fill="x", padx=15, pady=(15, 10))

        tk.Label(dir_frame, text="WORKING DIRECTORY", font=Theme.FONT_LABEL,
                fg=Theme.TEXT_LABEL, bg=Theme.BG_SECONDARY).pack(anchor="w")

        dir_entry = tk.Entry(dir_frame, font=Theme.FONT_NORMAL,
                            bg=Theme.BG_INPUT, fg=Theme.TEXT,
                            relief="flat", highlightthickness=1,
                            highlightbackground=Theme.BG_CARD)
        dir_entry.pack(fill="x", pady=(5, 0), ipady=8)
        dir_entry.insert(0, str(SCRIPT_DIR))
        dir_entry.config(state="readonly")

        # === PROCESS OPTIONS ===
        options_frame = tk.Frame(main, bg=Theme.BG_SECONDARY)
        options_frame.pack(fill="x", pady=(0, 15), ipady=15, ipadx=15)

        # Row 1: Dropdowns
        row1 = tk.Frame(options_frame, bg=Theme.BG_SECONDARY)
        row1.pack(fill="x", padx=15, pady=(15, 10))

        self.process_dropdown = LabeledDropdown(
            row1, "CHOOSE PROCESS",
            ["1. Transcribe Audio", "2. Export to Text",
             "3. Merge Translation", "4. Adjust Video Speed"],
            "1. Transcribe Audio"
        )
        self.process_dropdown.pack(side="left", padx=(0, 20))

        # Checkboxes
        check_frame = tk.Frame(row1, bg=Theme.BG_SECONDARY)
        check_frame.pack(side="left", padx=20)

        self.gpu_check = CheckOption(check_frame, "GPU Acceleration", True)
        self.gpu_check.pack(anchor="w")

        self.auto_continue = CheckOption(check_frame, "Auto-continue Pipeline", False)
        self.auto_continue.pack(anchor="w")

        # === ACTION BUTTONS ===
        action_frame = tk.Frame(main, bg=Theme.BG_SECONDARY)
        action_frame.pack(fill="x", pady=(0, 15), ipady=20, ipadx=15)

        # Quick action buttons
        quick_label = tk.Label(action_frame, text="QUICK ACTIONS",
                              font=Theme.FONT_LABEL, fg=Theme.TEXT_LABEL,
                              bg=Theme.BG_SECONDARY)
        quick_label.pack(pady=(15, 10))

        btn_row1 = tk.Frame(action_frame, bg=Theme.BG_SECONDARY)
        btn_row1.pack(pady=5)

        self.btn_transcribe = StyledButton(btn_row1, "Transcribe",
                                           lambda: self._run_script("run_canary.py", "Transcribing..."),
                                           width=130)
        self.btn_transcribe.pack(side="left", padx=5)

        self.btn_export = StyledButton(btn_row1, "Export Text",
                                       lambda: self._run_script("srt.py", "Exporting..."),
                                       width=130)
        self.btn_export.pack(side="left", padx=5)

        self.btn_merge = StyledButton(btn_row1, "Merge",
                                      lambda: self._run_script("text_to_srt.py", "Merging..."),
                                      width=130)
        self.btn_merge.pack(side="left", padx=5)

        self.btn_adjust = StyledButton(btn_row1, "Adjust Video",
                                       lambda: self._run_script("video_speed_adjuster_v3.py", "Adjusting..."),
                                       width=130)
        self.btn_adjust.pack(side="left", padx=5)

        # Main action button
        btn_row2 = tk.Frame(action_frame, bg=Theme.BG_SECONDARY)
        btn_row2.pack(pady=(15, 10))

        self.btn_start = StyledButton(btn_row2, "▶  Start Processing",
                                      self._start_selected, width=250, height=45, accent=True)
        self.btn_start.pack(side="left", padx=5)

        self.btn_pipeline = StyledButton(btn_row2, "Full Pipeline",
                                         self._run_full_pipeline, width=150, height=45)
        self.btn_pipeline.pack(side="left", padx=5)

        # Progress bar
        self.progress = ttk.Progressbar(action_frame, style="Custom.Horizontal.TProgressbar",
                                        mode="indeterminate", length=400)
        self.progress.pack(pady=(10, 5))

        self.status_label = tk.Label(action_frame, text="Ready",
                                    font=Theme.FONT_NORMAL, fg=Theme.TEXT,
                                    bg=Theme.BG_SECONDARY)
        self.status_label.pack(pady=(0, 10))

        # === LOG OUTPUT ===
        self.log_output = LogOutput(main)
        self.log_output.pack(fill="both", expand=True, pady=(0, 15))

        # === STATUS BAR ===
        self.status_bar = StatusBar(main)
        self.status_bar.pack(fill="x")

    def _set_buttons_disabled(self, disabled):
        self.is_running = disabled
        for btn in [self.btn_transcribe, self.btn_export, self.btn_merge,
                   self.btn_adjust, self.btn_start, self.btn_pipeline]:
            btn.set_disabled(disabled)

    def _start_selected(self):
        """Run the selected process from dropdown."""
        selected = self.process_dropdown.get()

        if "Transcribe" in selected:
            self._run_script("run_canary.py", "Transcribing audio...")
        elif "Export" in selected:
            self._run_script("srt.py", "Exporting to text...")
        elif "Merge" in selected:
            self._run_script("text_to_srt.py", "Merging translation...")
        elif "Adjust" in selected:
            self._run_script("video_speed_adjuster_v3.py", "Adjusting video...")

    def _run_script(self, script_name, status_msg):
        """Run a script in background."""
        if self.is_running:
            return

        script_path = BUNDLE_DIR / script_name
        if not script_path.exists():
            script_path = SCRIPT_DIR / script_name

        if not script_path.exists():
            self.log_output.log(f"Script not found: {script_name}", "error")
            return

        self._set_buttons_disabled(True)
        self.progress.start(10)
        self.status_label.config(text=status_msg, fg=Theme.WARNING)
        self.log_output.log(f"\n=== {status_msg} ===", "info")

        def run():
            try:
                python_exe = sys.executable if not IS_FROZEN else "python"
                process = subprocess.Popen(
                    [python_exe, "-u", str(script_path)],
                    cwd=str(SCRIPT_DIR),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1
                )
                self.running_process = process

                for line in process.stdout:
                    line = line.rstrip()
                    if line:
                        self.msg_queue.put(("log", line))

                process.wait()
                self.msg_queue.put(("done", process.returncode == 0))

            except Exception as e:
                self.msg_queue.put(("log", f"Error: {e}"))
                self.msg_queue.put(("done", False))

        threading.Thread(target=run, daemon=True).start()

    def _run_full_pipeline(self):
        """Run complete transcription + export pipeline."""
        if self.is_running:
            return

        if not (SCRIPT_DIR / "input.mp3").exists():
            messagebox.showerror("Error", "input.mp3 not found!\n\nPlace your audio file in the working directory.")
            return

        self._set_buttons_disabled(True)
        self.progress.start(10)
        self.status_label.config(text="Running full pipeline...", fg=Theme.WARNING)

        def run():
            scripts = [
                ("run_canary.py", "Transcribing audio..."),
                ("srt.py", "Exporting to text...")
            ]

            for script, msg in scripts:
                self.msg_queue.put(("status", msg))
                self.msg_queue.put(("log", f"\n=== {msg} ==="))

                script_path = BUNDLE_DIR / script
                if not script_path.exists():
                    script_path = SCRIPT_DIR / script

                python_exe = sys.executable if not IS_FROZEN else "python"
                process = subprocess.Popen(
                    [python_exe, "-u", str(script_path)],
                    cwd=str(SCRIPT_DIR),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1
                )

                for line in process.stdout:
                    if line.strip():
                        self.msg_queue.put(("log", line.rstrip()))

                process.wait()
                if process.returncode != 0:
                    self.msg_queue.put(("done", False))
                    return

            self.msg_queue.put(("log", "\n✓ Pipeline complete! Translate output.txt → Penis.txt"))
            self.msg_queue.put(("done", True))

        threading.Thread(target=run, daemon=True).start()

    def _check_queue(self):
        """Process messages from background threads."""
        try:
            while True:
                msg_type, data = self.msg_queue.get_nowait()

                if msg_type == "log":
                    tag = None
                    if "error" in data.lower() or "❌" in data:
                        tag = "error"
                    elif "✓" in data or "✅" in data:
                        tag = "success"
                    self.log_output.log(data, tag)

                elif msg_type == "status":
                    self.status_label.config(text=data, fg=Theme.WARNING)

                elif msg_type == "done":
                    self.progress.stop()
                    if data:
                        self.status_label.config(text="Completed!", fg=Theme.SUCCESS)
                    else:
                        self.status_label.config(text="Failed!", fg=Theme.ERROR)

                    self._set_buttons_disabled(False)
                    self.status_bar.refresh()
                    self.running_process = None

        except queue.Empty:
            pass

        self.after(100, self._check_queue)

    def on_closing(self):
        if self.running_process:
            if messagebox.askyesno("Confirm", "Process running. Stop and exit?"):
                self.running_process.terminate()
                self.destroy()
        else:
            self.destroy()


def main():
    app = MainApplication()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()


if __name__ == "__main__":
    main()
