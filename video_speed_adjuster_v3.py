#!/usr/bin/env python3
"""
Video Speed Adjuster v6.1 - Pure MoviePy 2.x Edition

Замедляет видео на основе CPS (символов в секунду) для комфортной озвучки.
Использует MoviePy 2.x для обработки видео.

Логика:
1. Парсим SRT субтитры (получаем начало/конец каждого субтитра)
2. Парсим русский перевод (текст для расчёта CPS)
3. Для каждого субтитра вычисляем CPS = символы / длительность
4. Если CPS > порога - замедляем этот сегмент видео
5. Склеиваем все сегменты в памяти
6. Записываем один раз в конце

Требования:
    pip install moviepy

Автор: Claude AI
"""

import re
import os
import sys
import gc
from pathlib import Path
from typing import List, Dict, Optional

# === НАСТРОЙКИ ===
TARGET_CPS = 16.0        # Целевой CPS после замедления
SOFT_THRESHOLD = 16.0    # Ниже этого - не трогаем
HARD_THRESHOLD = 20.0    # Выше этого - полное замедление
MAX_SLOWDOWN = 3.0       # Максимальное замедление (3x = в 3 раза медленнее)


def time_to_seconds(time_str: str) -> float:
    """Конвертирует '00:01:23,456' в секунды (float)"""
    match = re.match(r'(\d+):(\d+):(\d+)[,.](\d+)', time_str.strip())
    if not match:
        return 0.0
    h, m, s, ms = match.groups()
    ms = ms.ljust(3, '0')[:3]
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0


def seconds_to_srt_time(seconds: float) -> str:
    """Конвертирует секунды в формат SRT '00:01:23,456'"""
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
    """Парсит нумерованный текстовый файл."""
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
    """Вычисляет коэффициент замедления на основе CPS."""
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

    slowdown = min(slowdown, MAX_SLOWDOWN)
    return slowdown


def process_video(
    input_video: Path,
    eng_srt: Path,
    rus_translation: Path,
    output_video: Path,
    output_srt: Path
):
    """Основная функция обработки видео через MoviePy 2.x"""

    # === ИМПОРТ MOVIEPY 2.x ===
    try:
        from moviepy import VideoFileClip, concatenate_videoclips
        print("✅ MoviePy 2.x загружен")
    except ImportError:
        print("❌ MoviePy 2.x не установлен!")
        print("   pip install moviepy")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("  🎬 VIDEO SPEED ADJUSTER v6.1 (Pure MoviePy 2.x)")
    print("=" * 60)
    print(f"  Target CPS: {TARGET_CPS}")
    print(f"  Soft threshold: {SOFT_THRESHOLD}")
    print(f"  Hard threshold: {HARD_THRESHOLD}")
    print(f"  Max slowdown: {MAX_SLOWDOWN}x")
    print("=" * 60)

    # === ЧИТАЕМ СУБТИТРЫ ===
    print("\n📝 Загрузка субтитров...")

    eng_content = read_file_with_encoding(eng_srt)
    if not eng_content:
        print(f"❌ Не удалось прочитать SRT: {eng_srt}")
        sys.exit(1)

    eng_subs = parse_srt(eng_content)
    if not eng_subs:
        print("❌ SRT файл пустой!")
        sys.exit(1)
    print(f"   Субтитров: {len(eng_subs)}")

    # === ЧИТАЕМ ПЕРЕВОД ===
    rus_content = read_file_with_encoding(rus_translation)
    if not rus_content:
        print(f"❌ Не удалось прочитать перевод: {rus_translation}")
        sys.exit(1)

    if rus_translation.suffix.lower() == '.srt':
        rus_texts = [s['text'] for s in parse_srt(rus_content)]
    else:
        rus_texts = parse_numbered_text(rus_content)

    if not rus_texts:
        print(f"❌ Перевод пустой!")
        sys.exit(1)
    print(f"   Русских текстов: {len(rus_texts)}")

    if len(eng_subs) != len(rus_texts):
        print(f"⚠️  Количество не совпадает! Используем: {min(len(eng_subs), len(rus_texts))}")

    # === ЗАГРУЖАЕМ ВИДЕО ===
    print("\n📼 Загрузка видео...")
    video = VideoFileClip(str(input_video))
    video_duration = video.duration
    video_fps = video.fps
    print(f"   Длительность: {seconds_to_srt_time(video_duration)}")
    print(f"   FPS: {video_fps}")

    # === СТРОИМ СЕГМЕНТЫ ===
    print("\n🔍 Построение сегментов...")

    segments_info = []
    count = min(len(eng_subs), len(rus_texts))
    current_pos = 0.0
    total_slow = 0

    for i in range(count):
        sub = eng_subs[i]
        rus_text = rus_texts[i]
        start = sub['start']
        end = sub['end']

        # Gap перед субтитром
        if start > current_pos + 0.05:
            segments_info.append({
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
            orig_cps = len(rus_text) / duration
            new_cps = len(rus_text) / (duration * slowdown)
            print(f"   #{i+1:03d} CPS: {orig_cps:.1f} → {new_cps:.1f} (x{slowdown:.2f})")

        segments_info.append({
            'start': start,
            'end': end,
            'slowdown': slowdown,
            'sub_index': i + 1,
            'text': rus_text
        })

        current_pos = end

    # Хвост видео
    if current_pos < video_duration - 0.05:
        segments_info.append({
            'start': current_pos,
            'end': video_duration,
            'slowdown': 1.0,
            'sub_index': None,
            'text': ''
        })

    print(f"\n   📊 Сегментов: {len(segments_info)} | Замедлений: {total_slow}")

    # === ОБРАБОТКА ЧЕРЕЗ MOVIEPY ===
    print("\n🚀 Обработка сегментов в памяти...")

    clips = []
    new_timings = []
    current_output_time = 0.0

    for idx, seg in enumerate(segments_info):
        start = seg['start']
        end = seg['end']
        slowdown = seg['slowdown']
        duration = end - start

        if duration < 0.04:
            continue

        # Вырезаем сегмент (MoviePy 2.x)
        clip = video.subclipped(start, end)

        # Замедляем если нужно (MoviePy 2.x)
        if slowdown > 1.01:
            speed_factor = 1.0 / slowdown
            clip = clip.with_speed_scaled(speed_factor)
            new_duration = duration * slowdown
        else:
            new_duration = duration

        clips.append(clip)

        # Сохраняем тайминги для субтитров
        if seg['sub_index'] is not None and seg['text']:
            new_timings.append({
                'index': seg['sub_index'],
                'start': current_output_time,
                'end': current_output_time + new_duration,
                'text': seg['text']
            })

        current_output_time += new_duration

        # Прогресс каждые 50 сегментов
        if (idx + 1) % 50 == 0 or idx == len(segments_info) - 1:
            print(f"   Обработано: {idx + 1}/{len(segments_info)}")

    if not clips:
        print("❌ Нет сегментов!")
        video.close()
        sys.exit(1)

    # === СКЛЕЙКА ===
    print("\n🔗 Склеивание...")
    final_clip = concatenate_videoclips(clips, method="compose")
    print(f"   Итоговая длительность: {seconds_to_srt_time(final_clip.duration)}")

    # === ЗАПИСЬ ===
    print("\n💾 Запись видео (это займёт время)...")

    final_clip.write_videofile(
        str(output_video),
        fps=video_fps,
        codec='libx264',
        audio_codec='aac',
        bitrate='5000k',
        preset='fast',
        logger='bar'
    )

    # === СУБТИТРЫ ===
    print("\n✍️ Генерация субтитров...")
    srt_lines = []
    for timing in new_timings:
        start_time = seconds_to_srt_time(timing['start'])
        end_time = seconds_to_srt_time(timing['end'])
        srt_lines.append(f"{timing['index']}\n{start_time} --> {end_time}\n{timing['text']}")

    output_srt.write_text('\n\n'.join(srt_lines), encoding='utf-8')
    print(f"   Сохранено: {len(srt_lines)} субтитров")

    # === ОЧИСТКА ===
    print("\n🧹 Очистка памяти...")
    for clip in clips:
        try:
            clip.close()
        except:
            pass
    final_clip.close()
    video.close()
    gc.collect()

    # === ИТОГИ ===
    total_chars = sum(len(t['text']) for t in new_timings)
    avg_cps = total_chars / current_output_time if current_output_time > 0 else 0

    print(f"\n{'=' * 60}")
    print("✅ ГОТОВО!")
    print(f"   📹 Видео: {output_video}")
    print(f"   📝 Субтитры: {output_srt}")
    print(f"   ⏱️  Было: {seconds_to_srt_time(video_duration)}")
    print(f"   ⏱️  Стало: {seconds_to_srt_time(current_output_time)}")
    print(f"   📊 Средний CPS: {avg_cps:.1f}")
    print(f"{'=' * 60}\n")


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
