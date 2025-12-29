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

SCRIPT_DIR = Path(__file__).parent.resolve()

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

    def __init__(self, parent, label, is_folder=False, file_types=None, default_text=""):
        super().__init__(parent, bg=Theme.BG_SECONDARY)

        self.is_folder = is_folder
        self.file_types = file_types or [("All files", "*.*")]
        self.path_var = tk.StringVar(value=default_text)

        # Label
        tk.Label(
            self, text=label,
            font=Theme.FONT_LABEL,
            fg=Theme.TEXT_LABEL,
            bg=Theme.BG_SECONDARY
        ).pack(anchor="w", pady=(0, 5))

        container = tk.Frame(self, bg=Theme.BG_SECONDARY)
        container.pack(fill="x")

        # Entry
        self.entry = tk.Entry(
            container, textvariable=self.path_var,
            font=Theme.FONT_NORMAL,
            bg=Theme.BG_INPUT,
            fg=Theme.TEXT,
            insertbackground=Theme.TEXT,
            relief="flat",
            highlightthickness=1,
            highlightbackground=Theme.BG_CARD,
            highlightcolor=Theme.ACCENT
        )
        self.entry.pack(side="left", fill="x", expand=True, ipady=5)

        # Button
        self.btn = StyledButton(container, "Browse", self._browse, width=80, height=30)
        self.btn.pack(side="right", padx=(10, 0))

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
    """Bottom status bar with simple status."""

    def __init__(self, parent):
        super().__init__(parent, bg=Theme.BG_DARK)

        # Version label on right
        self.version = tk.Label(
            self, text=f"Video Subtitle Toolkit v3.0",
            font=Theme.FONT_SMALL,
            fg=Theme.TEXT_DIM,
            bg=Theme.BG_DARK
        )
        self.version.pack(side="right", padx=15, pady=5)

    def refresh(self):
        pass


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
        self.geometry("900x800")
        self.minsize(800, 700)
        self.configure(bg=Theme.BG_DARK)

        # Configure ttk styles
        self._setup_styles()

        # State
        self.msg_queue = queue.Queue()
        self.is_running = False
        self.running_process = None

        self._create_ui()
        self._check_queue()

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
        header.pack(fill="x", pady=(0, 20))

        # Logo
        logo_frame = tk.Frame(header, bg=Theme.BG_DARK)
        logo_frame.pack()

        tk.Label(logo_frame, text="VST", font=Theme.FONT_LOGO,
                fg=Theme.ACCENT, bg=Theme.BG_DARK).pack()
        tk.Label(logo_frame, text="VIDEO SUBTITLE TOOLKIT",
                font=Theme.FONT_SUBTITLE, fg=Theme.TEXT_DIM,
                bg=Theme.BG_DARK).pack()

        # === INPUT SECTION ===
        input_frame = tk.LabelFrame(main, text="  FILES  ", bg=Theme.BG_SECONDARY,
                                   fg=Theme.TEXT_LABEL, font=Theme.FONT_LABEL, bd=0)
        input_frame.pack(fill="x", pady=(0, 15), ipady=10, ipadx=10)

        # File Selectors
        self.file_audio = FileSelector(input_frame, "Audio Input (.mp3)", file_types=[("Audio", "*.mp3 *.wav *.m4a")], default_text="input.mp3")
        self.file_audio.pack(fill="x", padx=10, pady=5)

        self.file_video = FileSelector(input_frame, "Video Input (.mp4)", file_types=[("Video", "*.mp4 *.mkv *.mov")], default_text="input.mp4")
        self.file_video.pack(fill="x", padx=10, pady=5)

        self.file_srt_eng = FileSelector(input_frame, "Original Subtitles (.srt)", file_types=[("SRT", "*.srt")], default_text="output.srt")
        self.file_srt_eng.pack(fill="x", padx=10, pady=5)

        self.file_trans = FileSelector(input_frame, "Translation (.txt / .srt)", file_types=[("Text/SRT", "*.txt *.srt")], default_text="Penis.txt")
        self.file_trans.pack(fill="x", padx=10, pady=5)


        # === PROCESS OPTIONS ===
        options_frame = tk.Frame(main, bg=Theme.BG_SECONDARY)
        options_frame.pack(fill="x", pady=(0, 15), ipady=10, ipadx=10)

        # Row 1: Dropdowns
        row1 = tk.Frame(options_frame, bg=Theme.BG_SECONDARY)
        row1.pack(fill="x", padx=10, pady=5)

        self.process_dropdown = LabeledDropdown(
            row1, "CHOOSE PROCESS",
            ["1. Transcribe Audio", "2. Export to Text",
             "3. Merge Translation", "4. Adjust Video Speed"],
            "1. Transcribe Audio"
        )
        self.process_dropdown.pack(side="left", padx=(0, 20))

        self.process_dropdown.combo.bind("<<ComboboxSelected>>", self._on_process_change)


        # === ACTION BUTTONS ===
        action_frame = tk.Frame(main, bg=Theme.BG_SECONDARY)
        action_frame.pack(fill="x", pady=(0, 15), ipady=15, ipadx=15)

        # Main action button
        btn_row = tk.Frame(action_frame, bg=Theme.BG_SECONDARY)
        btn_row.pack(pady=10)

        self.btn_start = StyledButton(btn_row, "▶  Start Processing",
                                      self._start_selected, width=250, height=45, accent=True)
        self.btn_start.pack(side="left", padx=5)

        self.btn_pipeline = StyledButton(btn_row, "Full Pipeline",
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

        # Initial validation state
        self._on_process_change(None)

    def _on_process_change(self, event):
        """Update UI based on selected process."""
        # Could hide/show relevant file inputs, but simpler to just keep all visible for now
        pass

    def _set_buttons_disabled(self, disabled):
        self.is_running = disabled
        for btn in [self.btn_start, self.btn_pipeline]:
            btn.set_disabled(disabled)

        # Also disable file inputs during run
        state = "disabled" if disabled else "normal"
        self.file_audio.entry.config(state=state)
        self.file_video.entry.config(state=state)
        self.file_srt_eng.entry.config(state=state)
        self.file_trans.entry.config(state=state)

    def _get_abs_path(self, path_str):
        if not path_str: return None
        return str(Path(path_str).resolve())

    def _start_selected(self):
        """Run the selected process from dropdown."""
        selected = self.process_dropdown.get()

        if "Transcribe" in selected:
            audio = self._get_abs_path(self.file_audio.get())
            output = self._get_abs_path(self.file_srt_eng.get())
            if not audio: return messagebox.showerror("Error", "Please select an audio file.")

            self._run_script("run_canary.py", ["--input", audio, "--output", output], "Transcribing audio...")

        elif "Export" in selected:
            input_srt = self._get_abs_path(self.file_srt_eng.get())
            output_txt = str(Path(input_srt).parent / "output.txt") # Default output based on input
            if not input_srt: return messagebox.showerror("Error", "Please select an input SRT file.")

            self._run_script("srt.py", ["--input", input_srt, "--output", output_txt], "Exporting to text...")
            self.log_output.log(f"Output will be: {output_txt}", "info")

        elif "Merge" in selected:
            srt = self._get_abs_path(self.file_srt_eng.get())
            text = self._get_abs_path(self.file_trans.get())
            output = str(Path(srt).parent / "result.srt")
            if not srt or not text: return messagebox.showerror("Error", "Please select SRT and Translation file.")

            self._run_script("text_to_srt.py", ["--srt", srt, "--text", text, "--output", output], "Merging translation...")

        elif "Adjust" in selected:
            video = self._get_abs_path(self.file_video.get())
            eng_srt = self._get_abs_path(self.file_srt_eng.get())
            trans_file = self._get_abs_path(self.file_trans.get())
            output_video = str(Path(video).parent / "output_adjusted.mp4")
            output_srt = str(Path(video).parent / "adjusted.srt")

            if not video or not eng_srt or not trans_file:
                return messagebox.showerror("Error", "Please select Video, English SRT, and Translation file.")

            self._run_script("video_speed_adjuster_v3.py",
                             ["--input_video", video, "--eng_srt", eng_srt,
                              "--trans_file", trans_file, "--output_video", output_video,
                              "--output_srt", output_srt],
                             "Adjusting video...")

    def _run_script(self, script_name, args, status_msg):
        """Run a script in background."""
        if self.is_running:
            return

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
                cmd = [sys.executable, "-u", str(script_path)] + args

                process = subprocess.Popen(
                    cmd,
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

        audio = self._get_abs_path(self.file_audio.get())
        if not audio:
            messagebox.showerror("Error", "Please select an Audio file.")
            return

        # Define outputs
        srt_out = str(Path(audio).parent / "output.srt")
        txt_out = str(Path(audio).parent / "output.txt")

        self._set_buttons_disabled(True)
        self.progress.start(10)
        self.status_label.config(text="Running full pipeline...", fg=Theme.WARNING)

        def run():
            steps = [
                ("run_canary.py", ["--input", audio, "--output", srt_out], "Transcribing audio..."),
                ("srt.py", ["--input", srt_out, "--output", txt_out], "Exporting to text...")
            ]

            for script, args, msg in steps:
                self.msg_queue.put(("status", msg))
                self.msg_queue.put(("log", f"\n=== {msg} ==="))

                script_path = SCRIPT_DIR / script
                cmd = [sys.executable, "-u", str(script_path)] + args

                process = subprocess.Popen(
                    cmd,
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

            # Update the fields in UI to point to generated files
            self.file_srt_eng.set(srt_out)

            self.msg_queue.put(("log", f"\n✓ Pipeline complete!\nTranslate {txt_out} -> Then select it in Translation field."))
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
