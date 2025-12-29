#!/usr/bin/env python3
"""
Video Subtitle Processing Toolkit - Interactive Menu
=====================================================

A convenient menu for all subtitle and video processing tools.

Workflow:
1. Transcribe audio (input.mp3 -> output.srt)
2. Export to text (output.srt -> output.txt) - for translation
3. Merge translated text (output.srt + Penis.txt -> result.srt)
4. Adjust video speed (input.mp4 + subtitles -> output_adjusted.mp4)
"""

import os
import sys
import subprocess
from pathlib import Path

# Get script directory
SCRIPT_DIR = Path(__file__).parent.resolve()


def clear_screen():
    """Clear terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')


def check_file(filename: str) -> tuple[bool, str]:
    """Check if file exists and return status."""
    path = SCRIPT_DIR / filename
    if path.exists():
        size = path.stat().st_size
        if size > 1024 * 1024:
            size_str = f"{size / 1024 / 1024:.1f} MB"
        elif size > 1024:
            size_str = f"{size / 1024:.1f} KB"
        else:
            size_str = f"{size} bytes"
        return True, size_str
    return False, "not found"


def print_file_status():
    """Print status of all relevant files."""
    files = [
        ("input.mp3", "Audio input for transcription"),
        ("input.mp4", "Video input for speed adjustment"),
        ("output.srt", "English subtitles (from transcription)"),
        ("output.txt", "Numbered text (for translation)"),
        ("Penis.txt", "Translated text (numbered)"),
        ("russian.srt", "Russian subtitles (alternative)"),
        ("result.srt", "Merged subtitles (timing + translation)"),
        ("output_adjusted.mp4", "Speed-adjusted video"),
        ("adjusted.srt", "Adjusted subtitles"),
    ]

    print("\n  FILE STATUS")
    print("  " + "-" * 50)

    for filename, description in files:
        exists, size = check_file(filename)
        status = f"[OK] {size}" if exists else "[--] missing"
        print(f"  {status:20} {filename:25} {description}")

    print("  " + "-" * 50)


def run_script(script_name: str, description: str) -> bool:
    """Run a Python script and return success status."""
    script_path = SCRIPT_DIR / script_name

    if not script_path.exists():
        print(f"\n  ERROR: {script_name} not found!")
        return False

    print(f"\n  Running: {description}")
    print("  " + "=" * 50)

    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=str(SCRIPT_DIR)
        )
        return result.returncode == 0
    except KeyboardInterrupt:
        print("\n\n  Interrupted by user.")
        return False
    except Exception as e:
        print(f"\n  ERROR: {e}")
        return False


def show_menu():
    """Display the main menu."""
    print("""
  ╔═══════════════════════════════════════════════════════════════╗
  ║         VIDEO SUBTITLE PROCESSING TOOLKIT                     ║
  ╠═══════════════════════════════════════════════════════════════╣
  ║                                                               ║
  ║   TRANSCRIPTION                                               ║
  ║   [1] Transcribe audio    (input.mp3 -> output.srt)           ║
  ║                                                               ║
  ║   SUBTITLE PROCESSING                                         ║
  ║   [2] Export to text      (output.srt -> output.txt)          ║
  ║   [3] Merge translation   (output.srt + Penis.txt -> result)  ║
  ║                                                               ║
  ║   VIDEO PROCESSING                                            ║
  ║   [4] Adjust video speed  (match video to translation)        ║
  ║                                                               ║
  ║   WORKFLOWS                                                   ║
  ║   [5] Full pipeline       (1 -> 2, then wait for translation) ║
  ║   [6] Post-translation    (3 -> 4)                            ║
  ║                                                               ║
  ║   UTILITIES                                                   ║
  ║   [S] Show file status                                        ║
  ║   [C] Clean temp files                                        ║
  ║   [H] Help / Workflow guide                                   ║
  ║   [Q] Quit                                                    ║
  ║                                                               ║
  ╚═══════════════════════════════════════════════════════════════╝
""")


def show_help():
    """Display workflow help."""
    print("""
  ╔═══════════════════════════════════════════════════════════════╗
  ║                    WORKFLOW GUIDE                             ║
  ╠═══════════════════════════════════════════════════════════════╣
  ║                                                               ║
  ║  STEP 1: PREPARE FILES                                        ║
  ║  ─────────────────────                                        ║
  ║  Place in this folder:                                        ║
  ║  • input.mp3 - Audio to transcribe (English)                  ║
  ║  • input.mp4 - Video to adjust (optional, for step 4)         ║
  ║                                                               ║
  ║  STEP 2: TRANSCRIBE [Option 1]                                ║
  ║  ─────────────────────────────                                ║
  ║  Creates output.srt with English subtitles + timestamps       ║
  ║  Uses NVIDIA Parakeet TDT model (requires GPU)                ║
  ║                                                               ║
  ║  STEP 3: EXPORT FOR TRANSLATION [Option 2]                    ║
  ║  ─────────────────────────────────────────                    ║
  ║  Creates output.txt - numbered list of subtitles              ║
  ║  Send this to ChatGPT/Claude for translation                  ║
  ║                                                               ║
  ║  STEP 4: SAVE TRANSLATION                                     ║
  ║  ────────────────────────                                     ║
  ║  Save translated text as Penis.txt in this folder             ║
  ║  Keep the same numbered format (1. text, 2. text, etc.)       ║
  ║                                                               ║
  ║  STEP 5: MERGE [Option 3]                                     ║
  ║  ────────────────────────                                     ║
  ║  Combines timings from output.srt with text from Penis.txt    ║
  ║  Creates result.srt                                           ║
  ║                                                               ║
  ║  STEP 6: ADJUST VIDEO [Option 4]                              ║
  ║  ───────────────────────────────                              ║
  ║  Slows/speeds video segments to match translated text length  ║
  ║  Creates output_adjusted.mp4 and adjusted.srt                 ║
  ║                                                               ║
  ╚═══════════════════════════════════════════════════════════════╝
""")
    input("  Press Enter to continue...")


def clean_temp_files():
    """Clean temporary files."""
    temp_patterns = [
        "_nemo_temp",
        "_temp_audio.wav",
        "temp_segments",
        "*.pyc",
        "__pycache__",
    ]

    print("\n  Cleaning temporary files...")

    cleaned = 0
    for pattern in temp_patterns:
        if "*" in pattern:
            for f in SCRIPT_DIR.glob(pattern):
                try:
                    if f.is_file():
                        f.unlink()
                        cleaned += 1
                except:
                    pass
        else:
            path = SCRIPT_DIR / pattern
            if path.exists():
                try:
                    if path.is_file():
                        path.unlink()
                    else:
                        import shutil
                        shutil.rmtree(path, ignore_errors=True)
                    cleaned += 1
                except:
                    pass

    print(f"  Cleaned {cleaned} items.")


def main():
    """Main menu loop."""
    while True:
        clear_screen()
        show_menu()

        choice = input("  Enter choice: ").strip().upper()

        if choice == "1":
            # Check for input file
            if not (SCRIPT_DIR / "input.mp3").exists():
                print("\n  ERROR: input.mp3 not found!")
                print("  Please place your audio file as 'input.mp3' in this folder.")
                input("\n  Press Enter to continue...")
                continue
            run_script("run_canary.py", "Parakeet TDT Transcription")
            input("\n  Press Enter to continue...")

        elif choice == "2":
            if not (SCRIPT_DIR / "output.srt").exists():
                print("\n  ERROR: output.srt not found!")
                print("  Run transcription first (option 1).")
                input("\n  Press Enter to continue...")
                continue
            run_script("srt.py", "SRT to Text Converter")
            input("\n  Press Enter to continue...")

        elif choice == "3":
            if not (SCRIPT_DIR / "output.srt").exists():
                print("\n  ERROR: output.srt not found!")
                input("\n  Press Enter to continue...")
                continue
            if not (SCRIPT_DIR / "Penis.txt").exists():
                print("\n  ERROR: Penis.txt not found!")
                print("  Save your translated text as 'Penis.txt' in this folder.")
                input("\n  Press Enter to continue...")
                continue
            run_script("text_to_srt.py", "Merge Translation with Timings")
            input("\n  Press Enter to continue...")

        elif choice == "4":
            if not (SCRIPT_DIR / "input.mp4").exists():
                print("\n  ERROR: input.mp4 not found!")
                input("\n  Press Enter to continue...")
                continue
            if not (SCRIPT_DIR / "output.srt").exists():
                print("\n  ERROR: output.srt not found!")
                input("\n  Press Enter to continue...")
                continue
            if not (SCRIPT_DIR / "Penis.txt").exists() and not (SCRIPT_DIR / "russian.srt").exists():
                print("\n  ERROR: No translation found!")
                print("  Need either Penis.txt or russian.srt")
                input("\n  Press Enter to continue...")
                continue
            run_script("video_speed_adjuster_v3.py", "Video Speed Adjuster")
            input("\n  Press Enter to continue...")

        elif choice == "5":
            # Full pipeline: transcribe + export
            print("\n  FULL PIPELINE: Transcription + Export")
            print("  " + "=" * 50)

            if not (SCRIPT_DIR / "input.mp3").exists():
                print("\n  ERROR: input.mp3 not found!")
                input("\n  Press Enter to continue...")
                continue

            if run_script("run_canary.py", "Step 1: Transcription"):
                print("\n  Step 1 complete!")
                if run_script("srt.py", "Step 2: Export to Text"):
                    print("\n  " + "=" * 50)
                    print("  Pipeline complete!")
                    print("  ")
                    print("  Next steps:")
                    print("  1. Open output.txt")
                    print("  2. Translate it (ChatGPT/Claude)")
                    print("  3. Save translation as Penis.txt")
                    print("  4. Run option [6] for post-translation")

            input("\n  Press Enter to continue...")

        elif choice == "6":
            # Post-translation: merge + video
            print("\n  POST-TRANSLATION: Merge + Video Adjustment")
            print("  " + "=" * 50)

            missing = []
            if not (SCRIPT_DIR / "output.srt").exists():
                missing.append("output.srt")
            if not (SCRIPT_DIR / "Penis.txt").exists():
                missing.append("Penis.txt")
            if not (SCRIPT_DIR / "input.mp4").exists():
                missing.append("input.mp4")

            if missing:
                print(f"\n  ERROR: Missing files: {', '.join(missing)}")
                input("\n  Press Enter to continue...")
                continue

            if run_script("text_to_srt.py", "Step 1: Merge Translation"):
                print("\n  Step 1 complete!")
                if run_script("video_speed_adjuster_v3.py", "Step 2: Adjust Video"):
                    print("\n  " + "=" * 50)
                    print("  Pipeline complete!")
                    print("  ")
                    print("  Output files:")
                    print("  • result.srt - Translated subtitles")
                    print("  • output_adjusted.mp4 - Speed-adjusted video")
                    print("  • adjusted.srt - Adjusted subtitle timings")

            input("\n  Press Enter to continue...")

        elif choice == "S":
            clear_screen()
            print_file_status()
            input("\n  Press Enter to continue...")

        elif choice == "C":
            clean_temp_files()
            input("\n  Press Enter to continue...")

        elif choice == "H":
            clear_screen()
            show_help()

        elif choice == "Q":
            print("\n  Goodbye!\n")
            break

        else:
            print(f"\n  Unknown option: {choice}")
            input("  Press Enter to continue...")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n  Goodbye!\n")
        sys.exit(0)
