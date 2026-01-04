# Video Subtitle Toolkit

A beautiful GUI application for video subtitle processing, including AI-powered transcription, translation workflow support, and video speed adjustment.

## Features

- **AI Transcription** - Convert audio to English subtitles using NVIDIA Parakeet TDT
- **Export for Translation** - Convert subtitles to numbered text format
- **Merge Translation** - Combine translated text with original timings
- **Video Speed Adjustment** - Adjust video speed to match translated subtitle timing

## Quick Start

### Run the GUI
```bash
python gui.py
```

### Or use the console menu
```bash
python menu.py
```

## Building Standalone Executable

### Prerequisites
```bash
pip install pyinstaller
```

### Build
```bash
python build.py
```

The executable will be created in the `dist/` folder.

### Build Options
```bash
python build.py          # Standard build (lightweight)
python build.py --full   # Include all ML dependencies (large!)
python build.py --clean  # Clean build artifacts
```

## Workflow

1. **Prepare files:**
   - `input.mp3` - Audio to transcribe
   - `input.mp4` - Video to adjust (optional)

2. **Transcribe** (Option 1)
   - Creates `output.srt` with English subtitles

3. **Export to Text** (Option 2)
   - Creates `output.txt` - numbered list for translation

4. **Translate**
   - Send `output.txt` to ChatGPT/Claude for translation
   - Save result as `translated.txt` (keep numbered format)

5. **Merge Translation** (Option 3)
   - Combines timings + translation → `result.srt`

6. **Adjust Video** (Option 4)
   - Creates `output_adjusted.mp4` with speed adjustments

## Requirements

### For GUI and basic processing:
- Python 3.8+
- ffmpeg (for video processing)

### For AI transcription:
- NVIDIA GPU with CUDA
- PyTorch, NeMo toolkit
- Install with: `pip install -r requirements-full.txt`

## File Structure

```
├── gui.py                    # Modern GUI application
├── menu.py                   # Console menu interface
├── run_canary.py             # AI transcription (Parakeet TDT)
├── srt.py                    # SRT to text converter
├── text_to_srt.py            # Merge translation with timings
├── video_speed_adjuster_v3.py # Video speed adjustment
├── build.py                  # Build script for executable
├── build.spec                # PyInstaller configuration
├── requirements.txt          # Basic dependencies
└── requirements-full.txt     # Full dependencies with ASR
```

## License

MIT License
