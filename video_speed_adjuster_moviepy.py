#!/usr/bin/env python3
"""
Video Speed Adjuster - MoviePy версия
Простой и понятный: замедляет где надо, подстраивает сабы.
"""

import re
import sys
import os
from pathlib import Path

try:
    from moviepy import VideoFileClip, concatenate_videoclips
except ImportError:
    try:
        # Старая версия MoviePy
        from moviepy.editor import VideoFileClip, concatenate_videoclips
    except ImportError:
        print("❌ Установи moviepy: pip install moviepy")
        sys.exit(1)

# === НАСТРОЙКИ ===
TARGET_CPS = 16.0
SOFT_THRESHOLD = 16.0
HARD_THRESHOLD = 20.0
MAX_SLOWDOWN = 3.0


def time_to_ms(time_str):
    match = re.match(r'(\d+):(\d+):(\d+)[,.](\d+)', time_str.strip())
    if not match:
        return 0
    h, m, s, ms = match.groups()
    ms = ms.ljust(3, '0')[:3]
    return int(h) * 3600000 + int(m) * 60000 + int(s) * 1000 + int(ms)


def ms_to_time(ms):
    if ms < 0:
        ms = 0
    h = ms // 3600000
    ms %= 3600000
    m = ms // 60000
    ms %= 60000
    s = ms // 1000
    ms %= 1000
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def parse_srt(content):
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
        start = time_to_ms(parts[0])
        end = time_to_ms(parts[1])
        text = ' '.join(line.strip() for line in lines[text_start:] if line.strip())
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'\{[^}]+\}', '', text)
        text = re.sub(r'\([^)]*\)', '', text)
        text = text.strip()
        if text and end > start:
            subs.append({'start': start, 'end': end, 'text': text})
    return subs


def parse_txt(content):
    lines = []
    for line in content.replace('\r', '').split('\n'):
        line = line.strip()
        if not line:
            continue
        match = re.match(r'^\d+[\.\):]?\s*(.+)$', line)
        if match:
            lines.append(match.group(1).strip())
    return lines


def read_file(path):
    for enc in ['utf-8', 'utf-8-sig', 'windows-1251', 'cp1252', 'latin-1']:
        try:
            return path.read_text(encoding=enc)
        except:
            pass
    return None


def calc_slowdown(text, duration_ms):
    if not text or duration_ms <= 0:
        return 1.0
    chars = len(text)
    duration_sec = duration_ms / 1000.0
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

    output_video = input_video.parent / 'output_adjusted.mp4'
    output_srt = input_video.parent / 'adjusted.srt'

    print("\n" + "=" * 50)
    print("  VIDEO SPEED ADJUSTER (MoviePy)")
    print("=" * 50)

    # Проверки
    if not input_video.exists():
        print(f"❌ Видео не найдено: {input_video}")
        sys.exit(1)
    if not eng_srt.exists():
        print(f"❌ SRT не найден: {eng_srt}")
        sys.exit(1)
    if not rus_translation.exists():
        print(f"❌ Перевод не найден: {rus_translation}")
        sys.exit(1)

    # Читаем субтитры
    eng_subs = parse_srt(read_file(eng_srt))
    print(f"📝 Субтитров: {len(eng_subs)}")

    content = read_file(rus_translation)
    if rus_translation.suffix.lower() == '.srt':
        rus_texts = [s['text'] for s in parse_srt(content)]
    else:
        rus_texts = parse_txt(content)
    print(f"📝 Переводов: {len(rus_texts)}")

    # Загружаем видео
    print(f"\n🎬 Загрузка видео...")
    video = VideoFileClip(str(input_video))
    video_duration_ms = int(video.duration * 1000)
    print(f"   Длительность: {ms_to_time(video_duration_ms)}")

    # Строим сегменты
    print("\n🔍 Анализ...")
    segments = []
    count = min(len(eng_subs), len(rus_texts))
    current_pos = 0

    for i in range(count):
        sub = eng_subs[i]
        rus_text = rus_texts[i]
        start = sub['start']
        end = sub['end']

        # Gap перед субтитром
        if start > current_pos:
            segments.append({
                'start_ms': current_pos,
                'end_ms': start,
                'slowdown': 1.0,
                'text': None
            })

        # Субтитр
        if start < current_pos:
            start = current_pos
        if start >= end:
            continue

        duration = end - start
        slowdown = calc_slowdown(rus_text, duration)

        if slowdown > 1.01:
            print(f"   [{i+1}] CPS: {len(rus_text)/(duration/1000):.1f} → {len(rus_text)/(duration/1000*slowdown):.1f} (x{slowdown:.2f})")

        segments.append({
            'start_ms': start,
            'end_ms': end,
            'slowdown': slowdown,
            'text': rus_text,
            'sub_idx': i + 1
        })
        current_pos = end

    # Хвост
    if current_pos < video_duration_ms:
        segments.append({
            'start_ms': current_pos,
            'end_ms': video_duration_ms,
            'slowdown': 1.0,
            'text': None
        })

    slow_count = sum(1 for s in segments if s['slowdown'] > 1.01)
    print(f"\n📊 Сегментов: {len(segments)} | Замедлений: {slow_count}")

    # Рендерим сегменты
    print("\n🚀 Рендер...")
    clips = []
    new_subs = []  # (start_ms, end_ms, text, idx)
    new_pos_ms = 0

    for i, seg in enumerate(segments):
        start_sec = seg['start_ms'] / 1000.0
        end_sec = seg['end_ms'] / 1000.0
        slowdown = seg['slowdown']

        if end_sec <= start_sec:
            continue

        # Вырезаем кусок (MoviePy 2.x API)
        clip = video.subclipped(start_sec, end_sec)

        # Замедляем если нужно (factor < 1 = медленнее)
        if slowdown > 1.01:
            clip = clip.with_speed_scaled(1.0 / slowdown)

        clips.append(clip)

        # Вычисляем новую длительность
        new_duration_ms = int((seg['end_ms'] - seg['start_ms']) * slowdown)

        # Сохраняем субтитр
        if seg.get('text'):
            new_subs.append({
                'start': new_pos_ms,
                'end': new_pos_ms + new_duration_ms,
                'text': seg['text'],
                'idx': seg.get('sub_idx', i)
            })

        new_pos_ms += new_duration_ms

        if (i + 1) % 100 == 0:
            print(f"   {i + 1}/{len(segments)}...")

    print(f"\n🔗 Склеивание {len(clips)} клипов...")
    final = concatenate_videoclips(clips, method="compose")

    print(f"💾 Сохранение видео...")
    final.write_videofile(
        str(output_video),
        codec='libx264',
        audio_codec='aac',
        preset='fast',
        threads=4,
        logger=None
    )

    # Закрываем
    video.close()
    final.close()
    for c in clips:
        c.close()

    # Сохраняем субтитры
    print("✍️ Субтитры...")
    srt_lines = []
    for sub in new_subs:
        srt_lines.append(f"{sub['idx']}\n{ms_to_time(sub['start'])} --> {ms_to_time(sub['end'])}\n{sub['text']}")
    output_srt.write_text('\n\n'.join(srt_lines), encoding='utf-8')

    print(f"\n{'=' * 50}")
    print(f"✅ ГОТОВО!")
    print(f"   Видео: {output_video}")
    print(f"   Субтитры: {output_srt}")
    print(f"   Было: {ms_to_time(video_duration_ms)}")
    print(f"   Стало: {ms_to_time(new_pos_ms)}")
    print(f"{'=' * 50}\n")


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if sys.platform == 'win32':
            input("\nНажми Enter...")
