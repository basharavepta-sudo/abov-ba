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
    BG_DARK = "#0d1117"
    BG_SECONDARY = "#161b22"
    BG_CARD = "#1c2128"
    BG_INPUT = "#0d1117"
    BG_BUTTON = "#21262d"
    ACCENT = "#00d4aa"
    ACCENT_DARK = "#00a080"
    ACCENT_GLOW = "#00ffcc"
    TEXT = "#e6edf3"
    TEXT_DIM = "#7d8590"
    TEXT_LABEL = "#8b949e"
    SUCCESS = "#3fb950"
    WARNING = "#d29922"
    ERROR = "#f85149"
    FONT_LOGO = ("Segoe UI", 28, "bold")
    FONT_SUBTITLE = ("Segoe UI", 10)
    FONT_LABEL = ("Segoe UI", 9)
    FONT_NORMAL = ("Segoe UI", 10)
    FONT_BUTTON = ("Segoe UI", 11, "bold")
    FONT_SMALL = ("Segoe UI", 9)
    FONT_MONO = ("Consolas", 9)


class Tooltip:
    """Modern tooltip that appears on hover."""
    def __init__(self, widget, text, delay=500):
        self.widget = widget
        self.text = text
        self.delay = delay
        self.tooltip_window = None
        self.scheduled = None
        widget.bind("<Enter>", self._on_enter)
        widget.bind("<Leave>", self._on_leave)
        widget.bind("<Button-1>", self._on_leave)

    def _on_enter(self, event=None):
        self._cancel()
        self.scheduled = self.widget.after(self.delay, self._show)

    def _on_leave(self, event=None):
        self._cancel()
        self._hide()

    def _cancel(self):
        if self.scheduled:
            self.widget.after_cancel(self.scheduled)
            self.scheduled = None

    def _show(self):
        if self.tooltip_window:
            return
        x = self.widget.winfo_rootx() + 10
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        self.tooltip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tw.configure(bg=Theme.BG_CARD)
        frame = tk.Frame(tw, bg=Theme.ACCENT, padx=1, pady=1)
        frame.pack()
        label = tk.Label(frame, text=self.text, font=Theme.FONT_SMALL,
                        fg=Theme.TEXT, bg=Theme.BG_CARD, padx=8, pady=4,
                        wraplength=300, justify="left")
        label.pack()

    def _hide(self):
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None


class StyledButton(tk.Canvas):
    """Modern styled button with hover effects."""
    def __init__(self, parent, text, command=None, width=140, height=36,
                 accent=False, tooltip=None):
        super().__init__(parent, width=width, height=height,
                        bg=Theme.BG_SECONDARY, highlightthickness=0)
        self.text = text
        self.command = command
        self.width = width
        self.height = height
        self.accent = accent
        self.hovered = False
        self.disabled = False
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)
        self._draw()
        if tooltip:
            Tooltip(self, tooltip)

    def _draw(self):
        self.delete("all")
        if self.disabled:
            bg, fg, border = Theme.BG_CARD, Theme.TEXT_DIM, Theme.BG_CARD
        elif self.accent:
            bg = Theme.ACCENT if not self.hovered else Theme.ACCENT_GLOW
            fg, border = Theme.BG_DARK, bg
        else:
            bg = Theme.BG_BUTTON if not self.hovered else "#30363d"
            fg = Theme.TEXT
            border = "#30363d" if not self.hovered else Theme.ACCENT
        r = 6
        self._rounded_rect(2, 2, self.width-2, self.height-2, r, bg, border)
        self.create_text(self.width//2, self.height//2, text=self.text,
                        font=Theme.FONT_NORMAL, fill=fg)

    def _rounded_rect(self, x1, y1, x2, y2, r, fill, outline):
        self.create_arc(x1, y1, x1+2*r, y1+2*r, start=90, extent=90, fill=fill, outline=outline)
        self.create_arc(x2-2*r, y1, x2, y1+2*r, start=0, extent=90, fill=fill, outline=outline)
        self.create_arc(x1, y2-2*r, x1+2*r, y2, start=180, extent=90, fill=fill, outline=outline)
        self.create_arc(x2-2*r, y2-2*r, x2, y2, start=270, extent=90, fill=fill, outline=outline)
        self.create_rectangle(x1+r, y1, x2-r, y2, fill=fill, outline="")
        self.create_rectangle(x1, y1+r, x2, y2-r, fill=fill, outline="")

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


class FileInput(tk.Frame):
    """File input with label, entry and browse button."""
    def __init__(self, parent, label, default="", file_types=None, tooltip=None):
        super().__init__(parent, bg=Theme.BG_SECONDARY)
        self.file_types = file_types or [("All files", "*.*")]

        # Label
        tk.Label(self, text=label, font=Theme.FONT_LABEL,
                fg=Theme.TEXT_LABEL, bg=Theme.BG_SECONDARY).pack(anchor="w", pady=(0, 3))

        # Entry frame
        entry_frame = tk.Frame(self, bg=Theme.BG_SECONDARY)
        entry_frame.pack(fill="x")

        # Entry
        self.var = tk.StringVar(value=default)
        self.entry = tk.Entry(entry_frame, textvariable=self.var, font=Theme.FONT_NORMAL,
                             bg=Theme.BG_INPUT, fg=Theme.TEXT, insertbackground=Theme.TEXT,
                             relief="flat", highlightthickness=1,
                             highlightbackground=Theme.BG_CARD, highlightcolor=Theme.ACCENT)
        self.entry.pack(side="left", fill="x", expand=True, ipady=6)

        # Browse button
        self.browse_btn = StyledButton(entry_frame, "Browse", self._browse, width=80, height=32)
        self.browse_btn.pack(side="right", padx=(10, 0))

        if tooltip:
            Tooltip(self.entry, tooltip)

    def _browse(self):
        path = filedialog.askopenfilename(filetypes=self.file_types)
        if path:
            self.var.set(path)

    def get(self):
        return self.var.get()

    def set(self, value):
        self.var.set(value)


class LogOutput(tk.Frame):
    """Log output panel."""
    def __init__(self, parent):
        super().__init__(parent, bg=Theme.BG_CARD)
        header = tk.Frame(self, bg=Theme.BG_CARD)
        header.pack(fill="x", padx=15, pady=10)
        tk.Label(header, text="OUTPUT LOG", font=Theme.FONT_LABEL,
                fg=Theme.TEXT_LABEL, bg=Theme.BG_CARD).pack(side="left")
        clear_btn = tk.Label(header, text="Clear", font=Theme.FONT_SMALL,
                            fg=Theme.ACCENT, bg=Theme.BG_CARD, cursor="hand2")
        clear_btn.pack(side="right")
        clear_btn.bind("<Button-1>", lambda e: self.clear())

        self.text = tk.Text(self, font=Theme.FONT_MONO, bg=Theme.BG_INPUT,
                           fg=Theme.TEXT, insertbackground=Theme.TEXT,
                           relief="flat", height=10, padx=10, pady=10)
        self.text.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        scrollbar = tk.Scrollbar(self.text, command=self.text.yview)
        scrollbar.pack(side="right", fill="y")
        self.text.config(yscrollcommand=scrollbar.set)
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
        self.geometry("900x750")
        self.minsize(800, 650)
        self.configure(bg=Theme.BG_DARK)
        self._setup_styles()
        self.msg_queue = queue.Queue()
        self.is_running = False
        self.running_process = None
        self._create_ui()
        self._check_queue()

    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TCombobox", fieldbackground=Theme.BG_INPUT,
                       background=Theme.BG_BUTTON, foreground=Theme.TEXT, arrowcolor=Theme.TEXT)
        style.map("TCombobox", fieldbackground=[("readonly", Theme.BG_INPUT)],
                 selectbackground=[("readonly", Theme.ACCENT)],
                 selectforeground=[("readonly", Theme.BG_DARK)])
        style.configure("Custom.Horizontal.TProgressbar",
                       background=Theme.ACCENT, troughcolor=Theme.BG_INPUT)

    def _create_ui(self):
        main = tk.Frame(self, bg=Theme.BG_DARK)
        main.pack(fill="both", expand=True, padx=30, pady=20)

        # === HEADER ===
        header = tk.Frame(main, bg=Theme.BG_DARK)
        header.pack(fill="x", pady=(0, 20))
        tk.Label(header, text="VST", font=Theme.FONT_LOGO,
                fg=Theme.ACCENT, bg=Theme.BG_DARK).pack()
        tk.Label(header, text="VIDEO SUBTITLE TOOLKIT", font=Theme.FONT_SUBTITLE,
                fg=Theme.TEXT_DIM, bg=Theme.BG_DARK).pack()

        # === FILES SECTION ===
        files_frame = tk.Frame(main, bg=Theme.BG_SECONDARY)
        files_frame.pack(fill="x", pady=(0, 15), ipady=10)

        tk.Label(files_frame, text="FILES", font=Theme.FONT_LABEL,
                fg=Theme.TEXT_LABEL, bg=Theme.BG_SECONDARY).pack(anchor="w", padx=15, pady=(10, 5))

        # Audio input
        self.audio_input = FileInput(files_frame, "Audio Input (.mp3)", "input.mp3",
                                     [("MP3 files", "*.mp3"), ("WAV files", "*.wav"), ("All", "*.*")],
                                     tooltip="Audio file for transcription")
        self.audio_input.pack(fill="x", padx=15, pady=5)

        # Video input
        self.video_input = FileInput(files_frame, "Video Input (.mp4)", "input.mp4",
                                     [("MP4 files", "*.mp4"), ("All video", "*.mkv;*.avi"), ("All", "*.*")],
                                     tooltip="Video file for speed adjustment")
        self.video_input.pack(fill="x", padx=15, pady=5)

        # SRT input
        self.srt_input = FileInput(files_frame, "Original Subtitles (.srt)", "output.srt",
                                   [("SRT files", "*.srt"), ("All", "*.*")],
                                   tooltip="English subtitles from transcription")
        self.srt_input.pack(fill="x", padx=15, pady=5)

        # Translation input
        self.trans_input = FileInput(files_frame, "Translation (.txt / .srt)", "Penis.txt",
                                     [("Text files", "*.txt"), ("SRT files", "*.srt"), ("All", "*.*")],
                                     tooltip="Translated text file (numbered format)")
        self.trans_input.pack(fill="x", padx=15, pady=(5, 10))

        # === PROCESS SECTION ===
        process_frame = tk.Frame(main, bg=Theme.BG_SECONDARY)
        process_frame.pack(fill="x", pady=(0, 15), ipady=10)

        tk.Label(process_frame, text="CHOOSE PROCESS", font=Theme.FONT_LABEL,
                fg=Theme.TEXT_LABEL, bg=Theme.BG_SECONDARY).pack(anchor="w", padx=15, pady=(10, 5))

        # Dropdown
        self.process_var = tk.StringVar(value="4. Adjust Video Speed")
        dropdown_frame = tk.Frame(process_frame, bg=Theme.BG_SECONDARY)
        dropdown_frame.pack(fill="x", padx=15, pady=(0, 10))

        self.process_combo = ttk.Combobox(dropdown_frame, textvariable=self.process_var,
                                          values=["1. Transcribe Audio", "2. Export to Text",
                                                  "3. Merge Translation", "4. Adjust Video Speed"],
                                          state="readonly", font=Theme.FONT_NORMAL, width=25)
        self.process_combo.pack(side="left")
        Tooltip(self.process_combo, "1. Audio→SRT\n2. SRT→Text\n3. Merge translation\n4. Adjust video CPS<18")

        # === ACTION BUTTONS ===
        btn_frame = tk.Frame(main, bg=Theme.BG_SECONDARY)
        btn_frame.pack(fill="x", pady=(0, 15), ipady=15)

        btn_row = tk.Frame(btn_frame, bg=Theme.BG_SECONDARY)
        btn_row.pack(pady=15)

        self.btn_start = StyledButton(btn_row, "▶  Start Processing", self._start_selected,
                                      width=220, height=45, accent=True,
                                      tooltip="Run selected process with files above")
        self.btn_start.pack(side="left", padx=10)

        self.btn_pipeline = StyledButton(btn_row, "Full Pipeline", self._run_full_pipeline,
                                         width=140, height=45,
                                         tooltip="Run Transcribe → Export → Wait for translation")
        self.btn_pipeline.pack(side="left", padx=10)

        # Progress
        self.progress = ttk.Progressbar(btn_frame, style="Custom.Horizontal.TProgressbar",
                                        mode="indeterminate", length=450)
        self.progress.pack(pady=(0, 5))

        self.status_label = tk.Label(btn_frame, text="Ready", font=Theme.FONT_NORMAL,
                                    fg=Theme.TEXT, bg=Theme.BG_SECONDARY)
        self.status_label.pack(pady=(0, 10))

        # === LOG OUTPUT ===
        self.log_output = LogOutput(main)
        self.log_output.pack(fill="both", expand=True)

        # === STATUS BAR ===
        status_bar = tk.Frame(main, bg=Theme.BG_DARK)
        status_bar.pack(fill="x", pady=(10, 0))
        tk.Label(status_bar, text=f"Video Subtitle Toolkit v1.0 [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]",
                font=Theme.FONT_SMALL, fg=Theme.TEXT_DIM, bg=Theme.BG_DARK).pack(side="right")

    def _set_buttons_disabled(self, disabled):
        self.is_running = disabled
        self.btn_start.set_disabled(disabled)
        self.btn_pipeline.set_disabled(disabled)

    def _get_env_vars(self):
        """Get environment variables with file paths."""
        return {
            'VST_AUDIO_INPUT': self.audio_input.get(),
            'VST_VIDEO_INPUT': self.video_input.get(),
            'VST_SRT_INPUT': self.srt_input.get(),
            'VST_TRANSLATION': self.trans_input.get(),
        }

    def _start_selected(self):
        """Run the selected process."""
        selected = self.process_var.get()
        if "Transcribe" in selected:
            self._run_script("run_canary.py", "Transcribing audio...")
        elif "Export" in selected:
            self._run_script("srt.py", "Exporting to text...")
        elif "Merge" in selected:
            self._run_script("text_to_srt.py", "Merging translation...")
        elif "Adjust" in selected:
            self._run_script("video_speed_adjuster_v3.py", "Adjusting video speed...")

    def _run_script(self, script_name, status_msg):
        """Run a script in background with environment variables."""
        if self.is_running:
            return

        script_path = BUNDLE_DIR / script_name
        if not script_path.exists():
            script_path = SCRIPT_DIR / script_name
        if not script_path.exists():
            self.log_output.log(f"ERROR: Script not found: {script_name}", "error")
            return

        self._set_buttons_disabled(True)
        self.progress.start(10)
        self.status_label.config(text=status_msg, fg=Theme.WARNING)
        self.log_output.log(f"\n=== {status_msg} ===", "info")

        # Log file paths being used
        env_vars = self._get_env_vars()
        self.log_output.log(f"Video: {env_vars['VST_VIDEO_INPUT']}", "info")
        self.log_output.log(f"SRT: {env_vars['VST_SRT_INPUT']}", "info")
        self.log_output.log(f"Translation: {env_vars['VST_TRANSLATION']}", "info")

        def run():
            try:
                # Merge environment variables
                env = os.environ.copy()
                env.update(self._get_env_vars())

                python_exe = sys.executable if not IS_FROZEN else "python"
                process = subprocess.Popen(
                    [python_exe, "-u", str(script_path)],
                    cwd=str(SCRIPT_DIR),
                    env=env,
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
                self.msg_queue.put(("log", f"ERROR: {e}"))
                self.msg_queue.put(("done", False))

        threading.Thread(target=run, daemon=True).start()

    def _run_full_pipeline(self):
        """Run transcription + export pipeline."""
        if self.is_running:
            return

        audio_path = self.audio_input.get()
        if not Path(audio_path).exists():
            messagebox.showerror("Error", f"Audio file not found:\n{audio_path}")
            return

        self._set_buttons_disabled(True)
        self.progress.start(10)
        self.status_label.config(text="Running full pipeline...", fg=Theme.WARNING)

        def run():
            scripts = [
                ("run_canary.py", "Transcribing audio..."),
                ("srt.py", "Exporting to text...")
            ]

            env = os.environ.copy()
            env.update(self._get_env_vars())

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
                    env=env,
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
                    elif "✓" in data or "✅" in data or "done" in data.lower():
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
