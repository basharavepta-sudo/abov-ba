#!/usr/bin/env python3
"""
SRT to Numbered Text Converter

Converts SRT subtitle files to a simple numbered list format:
1. First subtitle text
2. Second subtitle text
...

By default, looks for 'output.srt' in the same folder as this script.
"""

import re
import sys
import argparse
from pathlib import Path


def parse_srt(content: str) -> list[str]:
    """Parse SRT content and extract subtitle texts."""

    # Normalize line endings
    content = content.replace('\r\n', '\n').replace('\r', '\n')

    # Split into blocks (separated by blank lines)
    blocks = re.split(r'\n\s*\n', content.strip())

    subtitles = []

    for block in blocks:
        lines = block.strip().split('\n')

        if len(lines) < 3:
            continue

        # First line should be the sequence number
        if not lines[0].strip().isdigit():
            continue

        # Second line should be the timecode (contains "-->")
        if '-->' not in lines[1]:
            continue

        # Remaining lines are the subtitle text
        text_lines = lines[2:]
        text = ' '.join(line.strip() for line in text_lines if line.strip())

        # Remove HTML-like tags (e.g., <i>, </i>, <b>, etc.)
        text = re.sub(r'<[^>]+>', '', text)

        # Remove ASS/SSA style tags like {\an8}
        text = re.sub(r'\{[^}]+\}', '', text)

        if text:
            subtitles.append(text)

    return subtitles


def convert_srt_to_numbered(input_path: Path, output_path: Path) -> str:
    """Convert an SRT file to numbered text format."""

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    # Try different encodings
    encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']
    content = None

    for encoding in encodings:
        try:
            content = input_path.read_text(encoding=encoding)
            break
        except UnicodeDecodeError:
            continue

    if content is None:
        raise ValueError(f"Could not decode file with any supported encoding")

    # Parse the SRT content
    subtitles = parse_srt(content)

    if not subtitles:
        raise ValueError("No valid subtitles found in the file")

    # Create numbered output
    output_lines = []
    for i, text in enumerate(subtitles, 1):
        output_lines.append(f"{i}. {text}")

    output_text = '\n\n'.join(output_lines)

    # Write to output file
    output_path.write_text(output_text, encoding='utf-8')

    return output_text


def main():
    parser = argparse.ArgumentParser(description="SRT to Numbered Text Converter")
    parser.add_argument("--input", "-i", type=str, default="output.srt", help="Input SRT file")
    parser.add_argument("--output", "-o", type=str, default="output.txt", help="Output Text file")
    args = parser.parse_args()

    # Get the directory where this script is located
    # script_dir = Path(__file__).parent.resolve()

    # Input and output files
    input_file = Path(args.input).resolve()
    output_file = Path(args.output).resolve()

    print(f"Looking for: {input_file}")

    try:
        result = convert_srt_to_numbered(input_file, output_file)

        subtitle_count = len(result.strip().split('\n'))
        print(f"Done! Converted {subtitle_count} subtitles.")
        print(f"Saved to: {output_file}")

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        # print(f"\nMake sure 'output.srt' is in the same folder as this script.", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
