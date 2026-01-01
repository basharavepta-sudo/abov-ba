#!/usr/bin/env python3
"""
Video Speed Adjuster v6.2 - MoviePy 2.x with Chunked Processing

Замедляет видео на основе CPS (символов в секунду) для комфортной озвучки.
Обработка ЧАНКАМИ для экономии памяти.

Логика:
1. Парсим SRT субтитры
2. Парсим русский перевод
3. Вычисляем CPS и замедление для каждого субтитра
4. Обрабатываем ЧАНКАМИ по N сегментов
5. Каждый чанк записываем во временный файл
6. Склеиваем все чанки через ffmpeg

Требования:
    pip install moviepy

Автор: Claude AI
"""

import re
import os
import sys
import gc
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import List, Dict, Optional

# === НАСТРОЙКИ ===
TARGET_CPS = 16.0        # Целевой CPS после замедления
SOFT_THRESHOLD = 16.0    # Ниже этого - не трогаем
HARD_THRESHOLD = 20.0    # Выше этого - полное замедление
MAX_SLOWDOWN = 3.0       # Максимальное замедление
CHUNK_SIZE = 50          # Сегментов в одном чанке (меньше = меньше RAM)


def time_to_seconds(time_str: str) -> float:
    """Конвертирует '00:01:23,456' в секунды"""
    match = re.match(r'(\d+):(\d+):(\d+)[,.](\d+)', time_str.strip())
    if not match:
        return 0.0
    h, m, s, ms = match.groups()
    ms = ms.ljust(3, '0')[:3]
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0


def seconds_to_srt_time(seconds: float) -> str:
    """Конвертирует секунды в формат SRT"""
    if seconds < 0:
        seconds = 0
    h = int(seconds // 3600)
    seconds %= 3600
    m = int(seconds // 60)
    seconds %= 60
    s = int(seconds)
    ms = int((seconds - s) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def parse_srt(content: str) -> List[Dict]:
    """Парсит SRT файл."""
    content = content.replace('\r\n', '\n').replace('\r', '\n')
    blocks = re.split(r'\n\s*\n', content.strip())
    subs = []

    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) < 2:
            continue

        timecode_line = None
        text_start = 0
        for i, line in enumerate(lines):
            if '-->' in line:
                timecode_line = line
                text_start = i + 1
                break

        if not timecode_line:
            continue

        parts = timecode_line.split('-->')
        if len(parts) != 2:
            continue

        start = time_to_seconds(parts[0])
        end = time_to_seconds(parts[1])

        text = ' '.join(line.strip() for line in lines[text_start:] if line.strip())
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'\{[^}]+\}', '', text)
        text = re.sub(r'\([^)]*\)', '', text)
        text = text.strip()

        if text and end > start:
            subs.append({'start': start, 'end': end, 'text': text})

    return subs


def parse_numbered_text(content: str) -> List[str]:
    """Парсит нумерованный текст."""
    lines = []
    for line in content.replace('\r', '').split('\n'):
        line = line.strip()
        if not line:
            continue
        match = re.match(r'^\d+[\.\):]?\s*(.+)$', line)
        if match:
            lines.append(match.group(1).strip())
    return lines


def read_file_with_encoding(path: Path) -> Optional[str]:
    """Читает файл с автоопределением кодировки"""
    for enc in ['utf-8', 'utf-8-sig', 'windows-1251', 'cp1252', 'latin-1']:
        try:
            return path.read_text(encoding=enc)
        except (UnicodeDecodeError, UnicodeError):
            continue
    return None


def calculate_slowdown(text: str, duration_sec: float) -> float:
    """Вычисляет коэффициент замедления."""
    if not text or duration_sec <= 0:
        return 1.0

    chars = len(text)
    current_cps = chars / duration_sec

    if current_cps <= SOFT_THRESHOLD:
        return 1.0

    full_slowdown = current_cps / TARGET_CPS

    threshold_range = HARD_THRESHOLD - SOFT_THRESHOLD
    if threshold_range > 0 and current_cps < HARD_THRESHOLD:
        blend = (current_cps - SOFT_THRESHOLD) / threshold_range
        blend = blend * blend * (3 - 2 * blend)
        slowdown = 1.0 + (full_slowdown - 1.0) * blend
    else:
        slowdown = full_slowdown

    return min(slowdown, MAX_SLOWDOWN)


def process_chunk(
    video_path: str,
    segments: List[Dict],
    output_file: Path,
    fps: float,
    chunk_idx: int,
    total_chunks: int
) -> tuple[bool, float]:
    """
    Обрабатывает один чанк сегментов через MoviePy.
    Возвращает (успех, длительность_чанка)
    """
    from moviepy import VideoFileClip, concatenate_videoclips

    print(f"\n   📦 Чанк {chunk_idx + 1}/{total_chunks} ({len(segments)} сегментов)")

    video = None
    clips = []
    chunk_duration = 0.0

    try:
        video = VideoFileClip(video_path)

        for seg in segments:
            start = seg['start']
            end = seg['end']
            slowdown = seg['slowdown']
            duration = end - start

            if duration < 0.04:
                continue

            # Вырезаем сегмент
            clip = video.subclipped(start, end)

            # Замедляем если нужно
            if slowdown > 1.01:
                speed_factor = 1.0 / slowdown
                clip = clip.with_speed_scaled(speed_factor)
                new_duration = duration * slowdown
            else:
                new_duration = duration

            clips.append(clip)
            chunk_duration += new_duration

        if not clips:
            return False, 0.0

        # Склеиваем клипы чанка
        if len(clips) == 1:
            final_chunk = clips[0]
        else:
            final_chunk = concatenate_videoclips(clips, method="compose")

        # Записываем чанк
        final_chunk.write_videofile(
            str(output_file),
            fps=fps,
            codec='libx264',
            audio_codec='aac',
            bitrate='5000k',
            preset='fast',
            logger='bar'
        )

        # Закрываем клипы
        for clip in clips:
            try:
                clip.close()
            except:
                pass
        if len(clips) > 1:
            final_chunk.close()

        success = output_file.exists() and output_file.stat().st_size > 1000
        print(f"   ✅ Чанк {chunk_idx + 1} записан: {output_file.name} ({chunk_duration:.1f}s)")
        return success, chunk_duration

    except Exception as e:
        print(f"   ❌ Ошибка чанка {chunk_idx + 1}: {e}")
        return False, 0.0

    finally:
        if video:
            video.close()
        gc.collect()


def concatenate_chunks(chunk_files: List[Path], output_path: Path):
    """Склеивает чанки через ffmpeg concat."""
    print("\n🔗 Склеивание чанков через ffmpeg...")

    concat_list = output_path.parent / 'concat_list.txt'

    with open(concat_list, 'w', encoding='utf-8') as f:
        for chunk_file in chunk_files:
            escaped = str(chunk_file.absolute()).replace("'", "'\\''")
            f.write(f"file '{escaped}'\n")

    cmd = [
        'ffmpeg', '-hide_banner', '-y',
        '-f', 'concat', '-safe', '0',
        '-i', str(concat_list),
        '-c', 'copy',
        '-movflags', '+faststart',
        str(output_path)
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    concat_list.unlink(missing_ok=True)

    if result.returncode != 0:
        print(f"   ❌ Ошибка ffmpeg: {result.stderr[:200]}")
        return False

    print(f"   ✅ Склеено в {output_path.name}")
    return True


def process_video(
    input_video: Path,
    eng_srt: Path,
    rus_translation: Path,
    output_video: Path,
    output_srt: Path
):
    """Основная функция с обработкой чанками."""

    # === ИМПОРТ ===
    try:
        from moviepy import VideoFileClip
        print("✅ MoviePy 2.x загружен")
    except ImportError:
        print("❌ MoviePy 2.x не установлен! pip install moviepy")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("  🎬 VIDEO SPEED ADJUSTER v6.2 (Chunked Processing)")
    print("=" * 60)
    print(f"  Target CPS: {TARGET_CPS}")
    print(f"  Chunk size: {CHUNK_SIZE} сегментов")
    print("=" * 60)

    # === СУБТИТРЫ ===
    print("\n📝 Загрузка субтитров...")

    eng_content = read_file_with_encoding(eng_srt)
    if not eng_content:
        print(f"❌ Не удалось прочитать: {eng_srt}")
        sys.exit(1)

    eng_subs = parse_srt(eng_content)
    if not eng_subs:
        print("❌ SRT пустой!")
        sys.exit(1)
    print(f"   Субтитров: {len(eng_subs)}")

    # === ПЕРЕВОД ===
    rus_content = read_file_with_encoding(rus_translation)
    if not rus_content:
        print(f"❌ Не удалось прочитать: {rus_translation}")
        sys.exit(1)

    if rus_translation.suffix.lower() == '.srt':
        rus_texts = [s['text'] for s in parse_srt(rus_content)]
    else:
        rus_texts = parse_numbered_text(rus_content)

    if not rus_texts:
        print("❌ Перевод пустой!")
        sys.exit(1)
    print(f"   Русских: {len(rus_texts)}")

    # === ВИДЕО ИНФО ===
    print("\n📼 Анализ видео...")
    video = VideoFileClip(str(input_video))
    video_duration = video.duration
    video_fps = video.fps
    video.close()
    print(f"   Длительность: {seconds_to_srt_time(video_duration)}")
    print(f"   FPS: {video_fps}")

    # === СТРОИМ СЕГМЕНТЫ ===
    print("\n🔍 Построение сегментов...")

    segments = []
    count = min(len(eng_subs), len(rus_texts))
    current_pos = 0.0
    total_slow = 0

    for i in range(count):
        sub = eng_subs[i]
        rus_text = rus_texts[i]
        start = sub['start']
        end = sub['end']

        # Gap
        if start > current_pos + 0.05:
            segments.append({
                'start': current_pos,
                'end': start,
                'slowdown': 1.0,
                'sub_index': None,
                'text': ''
            })

        if start < current_pos:
            start = current_pos
        if start >= end:
            continue

        duration = end - start
        slowdown = calculate_slowdown(rus_text, duration)

        if slowdown > 1.01:
            total_slow += 1

        segments.append({
            'start': start,
            'end': end,
            'slowdown': slowdown,
            'sub_index': i + 1,
            'text': rus_text
        })

        current_pos = end

    # Хвост
    if current_pos < video_duration - 0.05:
        segments.append({
            'start': current_pos,
            'end': video_duration,
            'slowdown': 1.0,
            'sub_index': None,
            'text': ''
        })

    num_chunks = (len(segments) + CHUNK_SIZE - 1) // CHUNK_SIZE
    print(f"   Сегментов: {len(segments)} | Замедлений: {total_slow}")
    print(f"   Чанков: {num_chunks} (по {CHUNK_SIZE} сегментов)")

    # === ВРЕМЕННАЯ ПАПКА ===
    temp_dir = Path(tempfile.mkdtemp(prefix='video_chunks_'))
    print(f"\n📁 Временная папка: {temp_dir}")

    try:
        # === ОБРАБОТКА ЧАНКАМИ ===
        print("\n🚀 Обработка чанками...")

        chunk_files = []
        chunk_durations = []
        total_output_time = 0.0

        for chunk_idx in range(num_chunks):
            start_idx = chunk_idx * CHUNK_SIZE
            end_idx = min(start_idx + CHUNK_SIZE, len(segments))
            chunk_segments = segments[start_idx:end_idx]

            chunk_file = temp_dir / f"chunk_{chunk_idx:04d}.mp4"

            success, duration = process_chunk(
                video_path=str(input_video),
                segments=chunk_segments,
                output_file=chunk_file,
                fps=video_fps,
                chunk_idx=chunk_idx,
                total_chunks=num_chunks
            )

            if success:
                chunk_files.append(chunk_file)
                chunk_durations.append(duration)
                total_output_time += duration

            gc.collect()

        if not chunk_files:
            print("❌ Ни один чанк не создан!")
            sys.exit(1)

        # === СКЛЕЙКА ===
        if len(chunk_files) == 1:
            # Один чанк - просто копируем
            shutil.copy(chunk_files[0], output_video)
        else:
            concatenate_chunks(chunk_files, output_video)

        if not output_video.exists():
            print("❌ Выходное видео не создано!")
            sys.exit(1)

        # === СУБТИТРЫ ===
        print("\n✍️ Генерация субтитров...")

        new_timings = []
        current_time = 0.0
        seg_idx = 0

        for chunk_idx, chunk_segs in enumerate([segments[i:i+CHUNK_SIZE] for i in range(0, len(segments), CHUNK_SIZE)]):
            for seg in chunk_segs:
                duration = seg['end'] - seg['start']
                if duration < 0.04:
                    continue

                slowdown = seg['slowdown']
                new_duration = duration * slowdown if slowdown > 1.01 else duration

                if seg['sub_index'] is not None and seg['text']:
                    new_timings.append({
                        'index': seg['sub_index'],
                        'start': current_time,
                        'end': current_time + new_duration,
                        'text': seg['text']
                    })

                current_time += new_duration

        srt_lines = []
        for t in new_timings:
            srt_lines.append(f"{t['index']}\n{seconds_to_srt_time(t['start'])} --> {seconds_to_srt_time(t['end'])}\n{t['text']}")

        output_srt.write_text('\n\n'.join(srt_lines), encoding='utf-8')
        print(f"   Сохранено: {len(srt_lines)} субтитров")

        # === ИТОГИ ===
        total_chars = sum(len(t['text']) for t in new_timings)
        avg_cps = total_chars / current_time if current_time > 0 else 0

        print(f"\n{'=' * 60}")
        print("✅ ГОТОВО!")
        print(f"   📹 Видео: {output_video}")
        print(f"   📝 Субтитры: {output_srt}")
        print(f"   ⏱️  Было: {seconds_to_srt_time(video_duration)}")
        print(f"   ⏱️  Стало: {seconds_to_srt_time(current_time)}")
        print(f"   📊 Средний CPS: {avg_cps:.1f}")
        print(f"   📦 Чанков обработано: {len(chunk_files)}")
        print(f"{'=' * 60}\n")

    finally:
        print("🧹 Очистка временных файлов...")
        shutil.rmtree(temp_dir, ignore_errors=True)
        gc.collect()


def main():
    script_dir = Path(__file__).parent.resolve()

    input_video = Path(os.environ.get('VST_VIDEO_INPUT', script_dir / 'input.mp4'))
    eng_srt = Path(os.environ.get('VST_SRT_INPUT', script_dir / 'output.srt'))

    translation_env = os.environ.get('VST_TRANSLATION', '')
    if translation_env:
        rus_translation = Path(translation_env)
    elif (script_dir / 'russian.srt').exists():
        rus_translation = script_dir / 'russian.srt'
    else:
        rus_translation = script_dir / 'Penis.txt'

    output_dir = Path(os.environ.get('VST_OUTPUT_DIR', '')) or input_video.parent
    output_video = output_dir / 'output_adjusted.mp4'
    output_srt = output_dir / 'adjusted.srt'

    if not input_video.exists():
        print(f"❌ Видео не найдено: {input_video}")
        sys.exit(1)
    if not eng_srt.exists():
        print(f"❌ SRT не найден: {eng_srt}")
        sys.exit(1)
    if not rus_translation.exists():
        print(f"❌ Перевод не найден: {rus_translation}")
        sys.exit(1)

    print("=" * 60)
    print("📁 ФАЙЛЫ:")
    print(f"   Видео: {input_video}")
    print(f"   SRT: {eng_srt}")
    print(f"   Перевод: {rus_translation}")
    print("=" * 60)

    process_video(
        input_video=input_video,
        eng_srt=eng_srt,
        rus_translation=rus_translation,
        output_video=output_video,
        output_srt=output_srt
    )


if __name__ == '__main__':
    main()
