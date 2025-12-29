#!/usr/bin/env python3
"""
Text to SRT Converter

Takes timings from output.srt and text from Penis.txt
and creates a new SRT file with the combined result.

Files must be in the same folder as this script.
"""

import re
import sys
from pathlib import Path


def parse_srt_timings(content: str) -> list[str]:
    """Parse SRT content and extract timecodes."""

    # Normalize line endings
    content = content.replace('\r\n', '\n').replace('\r', '\n')

    # Split into blocks (separated by blank lines)
    blocks = re.split(r'\n\s*\n', content.strip())

    timecodes = []

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

        timecodes.append(lines[1].strip())

    return timecodes


def parse_numbered_text(content: str) -> list[str]:
    """Parse numbered text and extract lines."""

    # Normalize line endings
    content = content.replace('\r\n', '\n').replace('\r', '\n')

    lines = []

    # Match lines starting with number and dot (with optional spaces)
    # Handles both "1. text" and "1.text" formats
    # Also handles empty lines between items
    pattern = r'^\d+\.\s*(.+)$'

    for line in content.split('\n'):
        line = line.strip()
        if not line:
            continue

        match = re.match(pattern, line)
        if match:
            lines.append(match.group(1).strip())

    return lines


def create_srt(timecodes: list[str], texts: list[str]) -> str:
    """Create SRT content from timecodes and texts."""

    if len(timecodes) != len(texts):
        print(f"Warning: Number of timecodes ({len(timecodes)}) doesn't match number of text lines ({len(texts)})")
        # Use the minimum of the two
        count = min(len(timecodes), len(texts))
    else:
        count = len(timecodes)

    blocks = []

    for i in range(count):
        block = f"{i + 1}\n{timecodes[i]}\n{texts[i]}"
        blocks.append(block)

    return '\n\n'.join(blocks)


def main():
    # Get the directory where this script is located
    script_dir = Path(__file__).parent.resolve()

    # Input files
    srt_file = script_dir / 'output.srt'
    text_file = script_dir / 'Penis.txt'

    # Output file
    output_file = script_dir / 'result.srt'

    print(f"Reading timings from: {srt_file}")
    print(f"Reading text from: {text_file}")

    # Check if files exist
    if not srt_file.exists():
        print(f"Error: {srt_file} not found!", file=sys.stderr)
        sys.exit(1)

    if not text_file.exists():
        print(f"Error: {text_file} not found!", file=sys.stderr)
        sys.exit(1)

    # Try different encodings for SRT
    encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']
    srt_content = None

    for encoding in encodings:
        try:
            srt_content = srt_file.read_text(encoding=encoding)
            break
        except UnicodeDecodeError:
            continue

    if srt_content is None:
        print("Error: Could not decode SRT file", file=sys.stderr)
        sys.exit(1)

    # Try different encodings for text file
    text_content = None

    for encoding in encodings:
        try:
            text_content = text_file.read_text(encoding=encoding)
            break
        except UnicodeDecodeError:
            continue

    if text_content is None:
        print("Error: Could not decode text file", file=sys.stderr)
        sys.exit(1)

    # Parse files
    timecodes = parse_srt_timings(srt_content)
    texts = parse_numbered_text(text_content)

    print(f"Found {len(timecodes)} timecodes and {len(texts)} text lines")

    if not timecodes:
        print("Error: No timecodes found in SRT file", file=sys.stderr)
        sys.exit(1)

    if not texts:
        print("Error: No text lines found in text file", file=sys.stderr)
        sys.exit(1)

    # Create new SRT
    result = create_srt(timecodes, texts)

    # Save result
    output_file.write_text(result, encoding='utf-8')

    print(f"Done! Saved to: {output_file}")


if __name__ == '__main__':
    main()
