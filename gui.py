#!/usr/bin/env python3
"""
Video Subtitle Processing Toolkit - Modern GUI
===============================================

A beautiful graphical interface for subtitle and video processing.
"""

import os
import sys
import subprocess
import threading
import queue
from pathlib import Path
from datetime import datetime
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

# Script directory
SCRIPT_DIR = Path(__file__).parent.resolve()


class ModernStyle:
    """Modern dark theme colors and fonts."""

    # Colors
    BG_DARK = "#1a1a2e"
    BG_CARD = "#16213e"
    BG_INPUT = "#0f3460"
    ACCENT = "#e94560"
    ACCENT_HOVER = "#ff6b6b"
    SUCCESS = "#00d26a"
    WARNING = "#ffc107"
    ERROR = "#ff4757"
    TEXT = "#eaeaea"
    TEXT_DIM = "#8892b0"
    BORDER = "#233554"

    # Fonts
    FONT_TITLE = ("Segoe UI", 24, "bold")
    FONT_HEADING = ("Segoe UI", 14, "bold")
    FONT_NORMAL = ("Segoe UI", 11)
    FONT_SMALL = ("Segoe UI", 10)
    FONT_MONO = ("Consolas", 10)


class FileStatusPanel(tk.Frame):
    """Panel showing file status with icons."""

    FILES = [
        ("input.mp3", "Audio input", "transcribe"),
        ("input.mp4", "Video input", "video"),
        ("output.srt", "English subtitles", "result"),
        ("output.txt", "Text for translation", "result"),
        ("Penis.txt", "Translated text", "translate"),
        ("russian.srt", "Russian subtitles", "translate"),
        ("result.srt", "Merged subtitles", "result"),
        ("output_adjusted.mp4", "Adjusted video", "final"),
        ("adjusted.srt", "Adjusted subtitles", "final"),
    ]

    def __init__(self, parent):
        super().__init__(parent, bg=ModernStyle.BG_CARD)
        self.labels = {}
        self.create_widgets()

    def create_widgets(self):
        # Header
        header = tk.Label(
            self, text="FILES",
            font=ModernStyle.FONT_HEADING,
            fg=ModernStyle.TEXT,
            bg=ModernStyle.BG_CARD
        )
        header.pack(pady=(15, 10), padx=15, anchor="w")

        # File list
        for filename, description, category in self.FILES:
            frame = tk.Frame(self, bg=ModernStyle.BG_CARD)
            frame.pack(fill="x", padx=15, pady=3)

            # Status indicator
            status_label = tk.Label(
                frame, text="●",
                font=("Segoe UI", 12),
                fg=ModernStyle.TEXT_DIM,
                bg=ModernStyle.BG_CARD,
                width=2
            )
            status_label.pack(side="left")

            # Filename
            name_label = tk.Label(
                frame, text=filename,
                font=ModernStyle.FONT_SMALL,
                fg=ModernStyle.TEXT,
                bg=ModernStyle.BG_CARD,
                width=22,
                anchor="w"
            )
            name_label.pack(side="left")

            # Size/status
            size_label = tk.Label(
                frame, text="--",
                font=ModernStyle.FONT_SMALL,
                fg=ModernStyle.TEXT_DIM,
                bg=ModernStyle.BG_CARD,
                width=12,
                anchor="e"
            )
            size_label.pack(side="right")

            self.labels[filename] = (status_label, size_label)

        # Padding at bottom
        tk.Frame(self, height=15, bg=ModernStyle.BG_CARD).pack()

    def refresh(self):
        """Update file status."""
        for filename, (status_label, size_label) in self.labels.items():
            path = SCRIPT_DIR / filename
            if path.exists():
                size = path.stat().st_size
                if size > 1024 * 1024:
                    size_str = f"{size / 1024 / 1024:.1f} MB"
                elif size > 1024:
                    size_str = f"{size / 1024:.1f} KB"
                else:
                    size_str = f"{size} B"

                status_label.config(fg=ModernStyle.SUCCESS)
                size_label.config(text=size_str, fg=ModernStyle.SUCCESS)
            else:
                status_label.config(fg=ModernStyle.TEXT_DIM)
                size_label.config(text="missing", fg=ModernStyle.TEXT_DIM)


class ActionButton(tk.Canvas):
    """Modern styled button."""

    def __init__(self, parent, text, command, color=None, width=200, height=45):
        super().__init__(
            parent,
            width=width,
            height=height,
            bg=ModernStyle.BG_DARK,
            highlightthickness=0
        )

        self.command = command
        self.text = text
        self.width = width
        self.height = height
        self.color = color or ModernStyle.ACCENT
        self.hover_color = ModernStyle.ACCENT_HOVER
        self.is_hovered = False
        self.is_disabled = False

        self.draw()

        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)
        self.bind("<Button-1>", self.on_click)

    def draw(self):
        self.delete("all")

        if self.is_disabled:
            fill = ModernStyle.BG_INPUT
            text_color = ModernStyle.TEXT_DIM
        else:
            fill = self.hover_color if self.is_hovered else self.color
            text_color = ModernStyle.TEXT

        # Rounded rectangle
        r = 8
        self.create_arc(0, 0, r*2, r*2, start=90, extent=90, fill=fill, outline="")
        self.create_arc(self.width-r*2, 0, self.width, r*2, start=0, extent=90, fill=fill, outline="")
        self.create_arc(0, self.height-r*2, r*2, self.height, start=180, extent=90, fill=fill, outline="")
        self.create_arc(self.width-r*2, self.height-r*2, self.width, self.height, start=270, extent=90, fill=fill, outline="")
        self.create_rectangle(r, 0, self.width-r, self.height, fill=fill, outline="")
        self.create_rectangle(0, r, self.width, self.height-r, fill=fill, outline="")

        # Text
        self.create_text(
            self.width // 2, self.height // 2,
            text=self.text,
            font=ModernStyle.FONT_NORMAL,
            fill=text_color
        )

    def on_enter(self, event):
        if not self.is_disabled:
            self.is_hovered = True
            self.draw()

    def on_leave(self, event):
        self.is_hovered = False
        self.draw()

    def on_click(self, event):
        if not self.is_disabled and self.command:
            self.command()

    def set_disabled(self, disabled):
        self.is_disabled = disabled
        self.draw()


class LogPanel(tk.Frame):
    """Log output panel with auto-scroll."""

    def __init__(self, parent):
        super().__init__(parent, bg=ModernStyle.BG_CARD)
        self.create_widgets()

    def create_widgets(self):
        # Header
        header_frame = tk.Frame(self, bg=ModernStyle.BG_CARD)
        header_frame.pack(fill="x", padx=15, pady=(15, 5))

        tk.Label(
            header_frame, text="LOG OUTPUT",
            font=ModernStyle.FONT_HEADING,
            fg=ModernStyle.TEXT,
            bg=ModernStyle.BG_CARD
        ).pack(side="left")

        clear_btn = tk.Label(
            header_frame, text="Clear",
            font=ModernStyle.FONT_SMALL,
            fg=ModernStyle.ACCENT,
            bg=ModernStyle.BG_CARD,
            cursor="hand2"
        )
        clear_btn.pack(side="right")
        clear_btn.bind("<Button-1>", lambda e: self.clear())

        # Text area
        self.text = scrolledtext.ScrolledText(
            self,
            font=ModernStyle.FONT_MONO,
            bg=ModernStyle.BG_INPUT,
            fg=ModernStyle.TEXT,
            insertbackground=ModernStyle.TEXT,
            relief="flat",
            padx=10,
            pady=10,
            height=12
        )
        self.text.pack(fill="both", expand=True, padx=15, pady=(5, 15))

        # Configure tags for colored output
        self.text.tag_config("error", foreground=ModernStyle.ERROR)
        self.text.tag_config("success", foreground=ModernStyle.SUCCESS)
        self.text.tag_config("warning", foreground=ModernStyle.WARNING)
        self.text.tag_config("info", foreground=ModernStyle.TEXT_DIM)

    def log(self, message, tag=None):
        """Add message to log."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.text.insert("end", f"[{timestamp}] ", "info")
        self.text.insert("end", message + "\n", tag)
        self.text.see("end")

    def clear(self):
        """Clear log."""
        self.text.delete("1.0", "end")


class ProgressPanel(tk.Frame):
    """Progress indicator panel."""

    def __init__(self, parent):
        super().__init__(parent, bg=ModernStyle.BG_CARD)
        self.create_widgets()

    def create_widgets(self):
        # Status label
        self.status_label = tk.Label(
            self,
            text="Ready",
            font=ModernStyle.FONT_NORMAL,
            fg=ModernStyle.TEXT,
            bg=ModernStyle.BG_CARD
        )
        self.status_label.pack(pady=(15, 10), padx=15, anchor="w")

        # Progress bar
        style = ttk.Style()
        style.theme_use('clam')
        style.configure(
            "Custom.Horizontal.TProgressbar",
            background=ModernStyle.ACCENT,
            troughcolor=ModernStyle.BG_INPUT,
            bordercolor=ModernStyle.BG_INPUT,
            lightcolor=ModernStyle.ACCENT,
            darkcolor=ModernStyle.ACCENT
        )

        self.progress = ttk.Progressbar(
            self,
            style="Custom.Horizontal.TProgressbar",
            mode="indeterminate",
            length=300
        )
        self.progress.pack(fill="x", padx=15, pady=(0, 15))

    def start(self, message="Processing..."):
        """Start progress animation."""
        self.status_label.config(text=message, fg=ModernStyle.WARNING)
        self.progress.start(10)

    def stop(self, message="Ready", success=True):
        """Stop progress animation."""
        self.progress.stop()
        color = ModernStyle.SUCCESS if success else ModernStyle.ERROR
        self.status_label.config(text=message, fg=color)

    def reset(self):
        """Reset to ready state."""
        self.progress.stop()
        self.status_label.config(text="Ready", fg=ModernStyle.TEXT)


class MainApplication(tk.Tk):
    """Main application window."""

    def __init__(self):
        super().__init__()

        self.title("Video Subtitle Toolkit")
        self.geometry("1000x700")
        self.minsize(900, 600)
        self.configure(bg=ModernStyle.BG_DARK)

        # Message queue for thread communication
        self.msg_queue = queue.Queue()
        self.running_process = None
        self.is_running = False

        self.create_widgets()
        self.check_queue()
        self.file_panel.refresh()

    def create_widgets(self):
        # Main container
        main = tk.Frame(self, bg=ModernStyle.BG_DARK)
        main.pack(fill="both", expand=True, padx=20, pady=20)

        # Header
        header = tk.Frame(main, bg=ModernStyle.BG_DARK)
        header.pack(fill="x", pady=(0, 20))

        tk.Label(
            header,
            text="Video Subtitle Toolkit",
            font=ModernStyle.FONT_TITLE,
            fg=ModernStyle.ACCENT,
            bg=ModernStyle.BG_DARK
        ).pack(side="left")

        # Refresh button
        refresh_btn = tk.Label(
            header,
            text="↻ Refresh Files",
            font=ModernStyle.FONT_NORMAL,
            fg=ModernStyle.TEXT_DIM,
            bg=ModernStyle.BG_DARK,
            cursor="hand2"
        )
        refresh_btn.pack(side="right", padx=10)
        refresh_btn.bind("<Button-1>", lambda e: self.file_panel.refresh())

        # Content area
        content = tk.Frame(main, bg=ModernStyle.BG_DARK)
        content.pack(fill="both", expand=True)

        # Left sidebar - Files
        left_panel = tk.Frame(content, bg=ModernStyle.BG_DARK, width=280)
        left_panel.pack(side="left", fill="y", padx=(0, 15))
        left_panel.pack_propagate(False)

        self.file_panel = FileStatusPanel(left_panel)
        self.file_panel.pack(fill="both", expand=True)

        # Center - Actions
        center = tk.Frame(content, bg=ModernStyle.BG_DARK)
        center.pack(side="left", fill="both", expand=True, padx=(0, 15))

        # Action cards
        self.create_action_cards(center)

        # Progress panel
        self.progress_panel = ProgressPanel(center)
        self.progress_panel.pack(fill="x", pady=(15, 0))

        # Right - Logs
        right_panel = tk.Frame(content, bg=ModernStyle.BG_DARK, width=350)
        right_panel.pack(side="right", fill="both", expand=True)

        self.log_panel = LogPanel(right_panel)
        self.log_panel.pack(fill="both", expand=True)

    def create_action_cards(self, parent):
        """Create action button cards."""

        # Transcription section
        section1 = tk.Frame(parent, bg=ModernStyle.BG_CARD)
        section1.pack(fill="x", pady=(0, 10))

        tk.Label(
            section1, text="1. TRANSCRIPTION",
            font=ModernStyle.FONT_HEADING,
            fg=ModernStyle.TEXT,
            bg=ModernStyle.BG_CARD
        ).pack(pady=(15, 5), padx=15, anchor="w")

        tk.Label(
            section1, text="Convert audio to English subtitles using AI",
            font=ModernStyle.FONT_SMALL,
            fg=ModernStyle.TEXT_DIM,
            bg=ModernStyle.BG_CARD
        ).pack(padx=15, anchor="w")

        btn_frame1 = tk.Frame(section1, bg=ModernStyle.BG_CARD)
        btn_frame1.pack(pady=15, padx=15, anchor="w")

        self.btn_transcribe = ActionButton(
            btn_frame1, "Transcribe Audio",
            lambda: self.run_script("run_canary.py", "Transcribing audio..."),
            width=180
        )
        self.btn_transcribe.pack(side="left", padx=(0, 10))

        # Subtitle processing section
        section2 = tk.Frame(parent, bg=ModernStyle.BG_CARD)
        section2.pack(fill="x", pady=(0, 10))

        tk.Label(
            section2, text="2. SUBTITLE PROCESSING",
            font=ModernStyle.FONT_HEADING,
            fg=ModernStyle.TEXT,
            bg=ModernStyle.BG_CARD
        ).pack(pady=(15, 5), padx=15, anchor="w")

        tk.Label(
            section2, text="Export for translation, then merge translated text",
            font=ModernStyle.FONT_SMALL,
            fg=ModernStyle.TEXT_DIM,
            bg=ModernStyle.BG_CARD
        ).pack(padx=15, anchor="w")

        btn_frame2 = tk.Frame(section2, bg=ModernStyle.BG_CARD)
        btn_frame2.pack(pady=15, padx=15, anchor="w")

        self.btn_export = ActionButton(
            btn_frame2, "Export to Text",
            lambda: self.run_script("srt.py", "Exporting to text..."),
            color="#4a69bd",
            width=150
        )
        self.btn_export.pack(side="left", padx=(0, 10))

        self.btn_merge = ActionButton(
            btn_frame2, "Merge Translation",
            lambda: self.run_script("text_to_srt.py", "Merging translation..."),
            color="#6a89cc",
            width=160
        )
        self.btn_merge.pack(side="left", padx=(0, 10))

        # Video processing section
        section3 = tk.Frame(parent, bg=ModernStyle.BG_CARD)
        section3.pack(fill="x", pady=(0, 10))

        tk.Label(
            section3, text="3. VIDEO PROCESSING",
            font=ModernStyle.FONT_HEADING,
            fg=ModernStyle.TEXT,
            bg=ModernStyle.BG_CARD
        ).pack(pady=(15, 5), padx=15, anchor="w")

        tk.Label(
            section3, text="Adjust video speed to match translated subtitle timing",
            font=ModernStyle.FONT_SMALL,
            fg=ModernStyle.TEXT_DIM,
            bg=ModernStyle.BG_CARD
        ).pack(padx=15, anchor="w")

        btn_frame3 = tk.Frame(section3, bg=ModernStyle.BG_CARD)
        btn_frame3.pack(pady=15, padx=15, anchor="w")

        self.btn_adjust = ActionButton(
            btn_frame3, "Adjust Video Speed",
            lambda: self.run_script("video_speed_adjuster_v3.py", "Adjusting video..."),
            color="#78e08f",
            width=180
        )
        self.btn_adjust.pack(side="left", padx=(0, 10))

        # Quick workflows
        section4 = tk.Frame(parent, bg=ModernStyle.BG_CARD)
        section4.pack(fill="x")

        tk.Label(
            section4, text="QUICK WORKFLOWS",
            font=ModernStyle.FONT_HEADING,
            fg=ModernStyle.TEXT,
            bg=ModernStyle.BG_CARD
        ).pack(pady=(15, 5), padx=15, anchor="w")

        btn_frame4 = tk.Frame(section4, bg=ModernStyle.BG_CARD)
        btn_frame4.pack(pady=15, padx=15, anchor="w")

        self.btn_full = ActionButton(
            btn_frame4, "Full Pipeline (1→2)",
            self.run_full_pipeline,
            color="#f8b739",
            width=160
        )
        self.btn_full.pack(side="left", padx=(0, 10))

        self.btn_post = ActionButton(
            btn_frame4, "Post-Translation (2→3)",
            self.run_post_translation,
            color="#e58e26",
            width=180
        )
        self.btn_post.pack(side="left")

    def set_buttons_state(self, disabled):
        """Enable/disable all action buttons."""
        self.is_running = disabled
        for btn in [self.btn_transcribe, self.btn_export, self.btn_merge,
                    self.btn_adjust, self.btn_full, self.btn_post]:
            btn.set_disabled(disabled)

    def run_script(self, script_name, status_message):
        """Run a script in background thread."""
        if self.is_running:
            return

        script_path = SCRIPT_DIR / script_name
        if not script_path.exists():
            self.log_panel.log(f"Script not found: {script_name}", "error")
            return

        self.set_buttons_state(True)
        self.progress_panel.start(status_message)
        self.log_panel.log(f"Starting: {script_name}", "info")

        def run():
            try:
                process = subprocess.Popen(
                    [sys.executable, "-u", str(script_path)],
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
                success = process.returncode == 0

                self.msg_queue.put(("done", success))

            except Exception as e:
                self.msg_queue.put(("log", f"Error: {e}"))
                self.msg_queue.put(("done", False))

        thread = threading.Thread(target=run, daemon=True)
        thread.start()

    def run_full_pipeline(self):
        """Run transcription + export."""
        if self.is_running:
            return

        if not (SCRIPT_DIR / "input.mp3").exists():
            self.log_panel.log("input.mp3 not found!", "error")
            messagebox.showerror("Error", "Please add input.mp3 file first!")
            return

        self.set_buttons_state(True)
        self.progress_panel.start("Running full pipeline...")

        def run():
            scripts = [
                ("run_canary.py", "Transcribing audio..."),
                ("srt.py", "Exporting to text...")
            ]

            for script, msg in scripts:
                self.msg_queue.put(("status", msg))
                self.msg_queue.put(("log", f"\n=== {msg} ==="))

                process = subprocess.Popen(
                    [sys.executable, "-u", str(SCRIPT_DIR / script)],
                    cwd=str(SCRIPT_DIR),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1
                )

                for line in process.stdout:
                    line = line.rstrip()
                    if line:
                        self.msg_queue.put(("log", line))

                process.wait()
                if process.returncode != 0:
                    self.msg_queue.put(("done", False))
                    return

            self.msg_queue.put(("log", "\n✓ Pipeline complete! Now translate output.txt → Penis.txt"))
            self.msg_queue.put(("done", True))

        thread = threading.Thread(target=run, daemon=True)
        thread.start()

    def run_post_translation(self):
        """Run merge + video adjust."""
        if self.is_running:
            return

        missing = []
        if not (SCRIPT_DIR / "output.srt").exists():
            missing.append("output.srt")
        if not (SCRIPT_DIR / "Penis.txt").exists():
            missing.append("Penis.txt")
        if not (SCRIPT_DIR / "input.mp4").exists():
            missing.append("input.mp4")

        if missing:
            self.log_panel.log(f"Missing files: {', '.join(missing)}", "error")
            messagebox.showerror("Error", f"Missing files:\n{chr(10).join(missing)}")
            return

        self.set_buttons_state(True)
        self.progress_panel.start("Running post-translation pipeline...")

        def run():
            scripts = [
                ("text_to_srt.py", "Merging translation..."),
                ("video_speed_adjuster_v3.py", "Adjusting video speed...")
            ]

            for script, msg in scripts:
                self.msg_queue.put(("status", msg))
                self.msg_queue.put(("log", f"\n=== {msg} ==="))

                process = subprocess.Popen(
                    [sys.executable, "-u", str(SCRIPT_DIR / script)],
                    cwd=str(SCRIPT_DIR),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1
                )

                for line in process.stdout:
                    line = line.rstrip()
                    if line:
                        self.msg_queue.put(("log", line))

                process.wait()
                if process.returncode != 0:
                    self.msg_queue.put(("done", False))
                    return

            self.msg_queue.put(("log", "\n✓ All done! Check output_adjusted.mp4"))
            self.msg_queue.put(("done", True))

        thread = threading.Thread(target=run, daemon=True)
        thread.start()

    def check_queue(self):
        """Process messages from background threads."""
        try:
            while True:
                msg_type, data = self.msg_queue.get_nowait()

                if msg_type == "log":
                    # Determine tag based on content
                    tag = None
                    if "error" in data.lower() or "❌" in data:
                        tag = "error"
                    elif "✓" in data or "✅" in data or "done" in data.lower():
                        tag = "success"
                    elif "warning" in data.lower() or "⚠" in data:
                        tag = "warning"

                    self.log_panel.log(data, tag)

                elif msg_type == "status":
                    self.progress_panel.start(data)

                elif msg_type == "done":
                    success = data
                    if success:
                        self.progress_panel.stop("Completed!", success=True)
                        self.log_panel.log("Task completed successfully!", "success")
                    else:
                        self.progress_panel.stop("Failed!", success=False)
                        self.log_panel.log("Task failed!", "error")

                    self.set_buttons_state(False)
                    self.file_panel.refresh()
                    self.running_process = None

        except queue.Empty:
            pass

        self.after(100, self.check_queue)

    def on_closing(self):
        """Handle window close."""
        if self.running_process:
            if messagebox.askyesno("Confirm", "A process is running. Stop it?"):
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
