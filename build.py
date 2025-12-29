#!/usr/bin/env python3
"""
Build Script for Video Subtitle Toolkit
========================================

Creates a standalone executable using PyInstaller.

Usage:
    python build.py          # Build standard version
    python build.py --full   # Build with all ML dependencies (large!)
    python build.py --clean  # Clean build artifacts
"""

import os
import sys
import shutil
import subprocess
import argparse
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
BUILD_DIR = SCRIPT_DIR / "build"
DIST_DIR = SCRIPT_DIR / "dist"


def run_command(cmd, description=""):
    """Run a command and handle errors."""
    print(f"\n{'='*60}")
    print(f"  {description}" if description else f"  Running: {' '.join(cmd)}")
    print(f"{'='*60}\n")

    result = subprocess.run(cmd, cwd=str(SCRIPT_DIR))

    if result.returncode != 0:
        print(f"\n❌ Command failed with code {result.returncode}")
        return False
    return True


def check_pyinstaller():
    """Check if PyInstaller is installed."""
    try:
        import PyInstaller
        print(f"✓ PyInstaller {PyInstaller.__version__} found")
        return True
    except ImportError:
        print("⚠ PyInstaller not found. Installing...")
        if run_command([sys.executable, "-m", "pip", "install", "pyinstaller"],
                       "Installing PyInstaller"):
            return True
        return False


def clean_build():
    """Remove build artifacts."""
    print("\n🧹 Cleaning build artifacts...")

    dirs_to_clean = [BUILD_DIR, DIST_DIR, SCRIPT_DIR / "__pycache__"]
    files_to_clean = list(SCRIPT_DIR.glob("*.spec.bak"))

    for d in dirs_to_clean:
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)
            print(f"  Removed: {d.name}/")

    for f in files_to_clean:
        f.unlink()
        print(f"  Removed: {f.name}")

    print("✓ Clean complete!")


def build_executable(full_build=False):
    """Build the executable."""

    if not check_pyinstaller():
        print("❌ Cannot proceed without PyInstaller")
        return False

    # Clean previous builds
    clean_build()

    print("\n" + "="*60)
    print("  🔨 Building Video Subtitle Toolkit")
    print("  Mode:", "FULL (with ML libs)" if full_build else "STANDARD")
    print("="*60)

    if full_build:
        # Full build with all dependencies - will be LARGE
        cmd = [
            sys.executable, "-m", "PyInstaller",
            "--onefile",
            "--windowed",
            "--name", "VideoSubtitleToolkit_Full",
            "--add-data", f"run_canary.py{os.pathsep}.",
            "--add-data", f"srt.py{os.pathsep}.",
            "--add-data", f"text_to_srt.py{os.pathsep}.",
            "--add-data", f"video_speed_adjuster_v3.py{os.pathsep}.",
            "--hidden-import", "torch",
            "--hidden-import", "numpy",
            "--hidden-import", "soundfile",
            "--collect-all", "nemo",
            "--collect-all", "nemo_toolkit",
            str(SCRIPT_DIR / "gui.py")
        ]
    else:
        # Standard build - lightweight, uses external Python for ASR
        cmd = [
            sys.executable, "-m", "PyInstaller",
            "--onefile",
            "--windowed",
            "--name", "VideoSubtitleToolkit",
            "--add-data", f"run_canary.py{os.pathsep}.",
            "--add-data", f"srt.py{os.pathsep}.",
            "--add-data", f"text_to_srt.py{os.pathsep}.",
            "--add-data", f"video_speed_adjuster_v3.py{os.pathsep}.",
            "--add-data", f"menu.py{os.pathsep}.",
            str(SCRIPT_DIR / "gui.py")
        ]

    if not run_command(cmd, "Building executable..."):
        return False

    # Check output
    exe_name = "VideoSubtitleToolkit_Full" if full_build else "VideoSubtitleToolkit"
    if sys.platform == "win32":
        exe_name += ".exe"

    exe_path = DIST_DIR / exe_name

    if exe_path.exists():
        size_mb = exe_path.stat().st_size / (1024 * 1024)
        print(f"\n{'='*60}")
        print(f"  ✅ BUILD SUCCESSFUL!")
        print(f"{'='*60}")
        print(f"  📦 Output: {exe_path}")
        print(f"  📊 Size: {size_mb:.1f} MB")
        print(f"\n  To run: {exe_path}")
        print(f"{'='*60}\n")
        return True
    else:
        print("\n❌ Build failed - executable not found")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Build Video Subtitle Toolkit executable",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python build.py          Build standard version (recommended)
  python build.py --full   Build with ML dependencies (very large!)
  python build.py --clean  Remove build artifacts only
        """
    )
    parser.add_argument("--full", action="store_true",
                        help="Include all ML dependencies (creates large executable)")
    parser.add_argument("--clean", action="store_true",
                        help="Clean build artifacts and exit")

    args = parser.parse_args()

    if args.clean:
        clean_build()
        return 0

    if args.full:
        print("\n⚠️  WARNING: Full build includes PyTorch, NeMo, etc.")
        print("   This will create a VERY LARGE executable (2-5 GB)")
        print("   and may take 10-30 minutes to build.\n")
        response = input("   Continue? [y/N]: ").strip().lower()
        if response != 'y':
            print("   Build cancelled.")
            return 0

    success = build_executable(full_build=args.full)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
