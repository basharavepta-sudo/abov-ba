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
The GUI allows you to select input files and run the processing steps.

### Or use the console menu
```bash
python menu.py
```
The console menu expects files to be in the same directory (`input.mp3`, `input.mp4`, etc.) for quick processing.

## Workflow

1. **Transcription**
   - Select your audio file (`.mp3`, `.wav`)
   - It will produce `output.srt` with English subtitles

2. **Export to Text**
   - Convert the `output.srt` to `output.txt`
   - This creates a numbered list suitable for translation

3. **Translate**
   - Send `output.txt` to ChatGPT/Claude for translation
   - Save the result as a text file (e.g., `Penis.txt`), keeping the numbered format

4. **Merge Translation**
   - Combine the original timings from `output.srt` with your translated text file
   - Produces a `result.srt` with translated subtitles

5. **Adjust Video**
   - Select your video file (`.mp4`)
   - The tool will adjust the video speed to match the length of the translated subtitles
   - Creates `output_adjusted.mp4`

## Requirements

### For GUI and basic processing:
- Python 3.8+
- ffmpeg (for video processing)
- tkinter (usually included with Python)

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
├── requirements.txt          # Basic dependencies
└── requirements-full.txt     # Full dependencies with ASR
```

## License

MIT License
