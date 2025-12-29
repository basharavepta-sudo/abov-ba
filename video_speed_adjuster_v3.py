#!/usr/bin/env python3
"""
Video Speed Adjuster v3.0 - NO DUPLICATE FRAMES

Корректно замедляет/ускоряет видео на основе сравнения субтитров.
Каждый кадр исходного видео используется РОВНО ОДИН РАЗ.

Принцип работы:
1. Читает английские субтитры (output.srt) — исходные тайминги
2. Читает русские субтитры (russian.srt) или текст (Penis.txt)
3. Для каждого субтитра вычисляет коэффициент: len(рус) / len(англ)
4. Замедляет сегменты где русский текст длиннее (нужно больше времени)
5. Использует ТОЧНЫЙ trim через фильтры ffmpeg (без дублирования)

Required files:
  - input.mp4
  - output.srt (английские субтитры)
  - russian.srt ИЛИ Penis.txt (русский перевод)
"""

import re
import sys
import subprocess
import os
import shutil
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from typing import List, Dict, Tuple, Optional, Any

# --- CONFIGURATION ---
TARGET_CPS = 17.0           # Target CPS (below 18 for Aegisub safety margin)
MAX_CPS = 18.0              # Aegisub limit - we stay below this
TARGET_WPS = 2.5            # Target Words Per Second (comfortable speaking rate)
MAX_WPS = 3.0               # Max WPS before slowdown (normal speech ~2.5-3 WPS)
MIN_SPEED = 0.4             # Минимальная скорость (макс. замедление 2.5x)
MAX_SPEED = 2.0             # Максимальная скорость (макс. ускорение 2x)
MERGE_THRESHOLD = 0.02      # Порог для слияния сегментов (разница скоростей)
CPS_MODE = True             # Use CPS-based calculation (more accurate for dubbing)

print_lock = threading.Lock()

def safe_print(msg: str) -> None:
    with print_lock:
        print(msg)


def time_to_ms(time_str: str) -> int:
    """Конвертирует SRT таймкод в миллисекунды."""
    match = re.match(r'(\d+):(\d+):(\d+)[,.](\d+)', time_str.strip())
    if not match:
        return 0
    h, m, s, ms = match.groups()
    # Нормализуем миллисекунды (может быть 1-3 цифры)
    ms = ms.ljust(3, '0')[:3]
    return int(h) * 3600000 + int(m) * 60000 + int(s) * 1000 + int(ms)


def ms_to_time(ms: int) -> str:
    """Конвертирует миллисекунды в SRT таймкод."""
    if ms < 0:
        ms = 0
    h = ms // 3600000
    ms %= 3600000
    m = ms // 60000
    ms %= 60000
    s = ms // 1000
    ms %= 1000
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def parse_srt(content: str) -> List[Dict[str, Any]]:
    """Парсит SRT файл."""
    content = content.replace('\r\n', '\n').replace('\r', '\n')
    blocks = re.split(r'\n\s*\n', content.strip())
    subtitles = []

    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) < 2:
            continue

        # Ищем строку с таймкодом
        timecode_line = None
        text_start = 0

        for i, line in enumerate(lines):
            if '-->' in line:
                timecode_line = line
                text_start = i + 1
                break

        if not timecode_line:
            continue

        parts = timecode_line.strip().split('-->')
        if len(parts) != 2:
            continue

        start_ms = time_to_ms(parts[0])
        end_ms = time_to_ms(parts[1])

        text = ' '.join(line.strip() for line in lines[text_start:] if line.strip())
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'\{[^}]+\}', '', text)
        text = re.sub(r'\([^)]*\)', '', text)  # Убираем (звуки)
        text = text.strip()

        if text and end_ms > start_ms:
            subtitles.append({
                'start_ms': start_ms,
                'end_ms': end_ms,
                'text': text
            })

    return subtitles


def parse_numbered_text(content: str) -> List[str]:
    """Парсит нумерованный текст (Penis.txt)."""
    content = content.replace('\r\n', '\n').replace('\r', '\n')
    lines = []

    for line in content.split('\n'):
        line = line.strip()
        if not line:
            continue
        match = re.match(r'^\d+[\.\):]?\s*(.+)$', line)
        if match:
            lines.append(match.group(1).strip())

    return lines


def get_video_info(video_path: Path) -> Dict[str, float]:
    """Получает информацию о видео."""
    cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
           '-of', 'default=noprint_wrappers=1:nokey=1', str(video_path)]
    try:
        duration = float(subprocess.run(cmd, capture_output=True, text=True).stdout.strip())
    except:
        safe_print("❌ Не удалось получить длительность видео")
        sys.exit(1)

    cmd = ['ffprobe', '-v', 'error', '-select_streams', 'v:0',
           '-show_entries', 'stream=r_frame_rate',
           '-of', 'default=noprint_wrappers=1:nokey=1', str(video_path)]
    fps_str = subprocess.run(cmd, capture_output=True, text=True).stdout.strip()

    if '/' in fps_str:
        num, den = fps_str.split('/')
        fps = int(num) / int(den) if int(den) != 0 else 30.0
    else:
        fps = float(fps_str) if fps_str else 30.0

    return {'duration': duration, 'fps': fps}


def test_encoder(encoder: str) -> bool:
    """Проверяет работоспособность энкодера."""
    try:
        cmd = ['ffmpeg', '-hide_banner', '-y', '-f', 'lavfi',
               '-i', 'color=black:s=256x256:d=0.1', '-c:v', encoder, '-f', 'null', '-']
        return subprocess.run(cmd, capture_output=True, timeout=10).returncode == 0
    except:
        return False


def detect_gpu_encoder() -> Tuple[str, List[str], str]:
    """Определяет лучший доступный энкодер."""
    try:
        result = subprocess.run(['ffmpeg', '-hide_banner', '-encoders'],
                               capture_output=True, text=True)
        encoders = result.stdout
    except FileNotFoundError:
        print("❌ ffmpeg не найден!")
        sys.exit(1)

    if 'h264_nvenc' in encoders and test_encoder('h264_nvenc'):
        return 'h264_nvenc', ['-preset', 'p1', '-rc', 'vbr', '-cq', '22'], 'NVIDIA NVENC 🚀'

    if 'h264_amf' in encoders and test_encoder('h264_amf'):
        return 'h264_amf', ['-quality', 'speed', '-rc', 'vbr_peak', '-qp_i', '22', '-qp_p', '22'], 'AMD AMF ⚡'

    if 'h264_qsv' in encoders and test_encoder('h264_qsv'):
        return 'h264_qsv', ['-preset', 'veryfast', '-global_quality', '22'], 'Intel QSV 🔵'

    return 'libx264', ['-preset', 'fast', '-crf', '20'], 'CPU 🐢'


def count_words(text: str) -> int:
    """Считает количество слов в тексте."""
    # Разбиваем по пробелам и пунктуации
    words = re.findall(r'\b\w+\b', text, re.UNICODE)
    return len(words)


def calculate_speed(orig_text: str, trans_text: str, duration_ms: int = 0) -> float:
    """
    Вычисляет коэффициент скорости на основе CPS и WPS.

    Учитывает ОБА фактора:
    - CPS (Characters Per Second) - для Aegisub лимита
    - WPS (Words Per Second) - для комфортного проговаривания

    Если любой из параметров превышен - замедляем видео.
    """
    trans_text = trans_text.strip()
    trans_len = len(trans_text)
    word_count = count_words(trans_text)

    if trans_len == 0 or word_count == 0:
        return 1.0

    if CPS_MODE and duration_ms > 0:
        duration_sec = duration_ms / 1000.0

        # Current metrics
        current_cps = trans_len / duration_sec if duration_sec > 0 else TARGET_CPS
        current_wps = word_count / duration_sec if duration_sec > 0 else TARGET_WPS

        # Check if we need to slow down (either CPS or WPS exceeded)
        need_slowdown_cps = current_cps > MAX_CPS
        need_slowdown_wps = current_wps > MAX_WPS

        if not need_slowdown_cps and not need_slowdown_wps:
            # Already within limits, no change needed
            return 1.0

        # Calculate required duration for both metrics
        required_duration_cps = trans_len / TARGET_CPS
        required_duration_wps = word_count / TARGET_WPS

        # Use the LONGER required duration (slower speed = more time)
        # This ensures BOTH CPS and WPS are satisfied
        required_duration = max(required_duration_cps, required_duration_wps)

        # Speed factor (>1 = slow down = video plays longer)
        speed = required_duration / duration_sec

        # Calculate resulting metrics for logging
        result_cps = trans_len / required_duration
        result_wps = word_count / required_duration

        reason = "CPS" if required_duration_cps >= required_duration_wps else "WPS"
        safe_print(f"    {reason}: CPS {current_cps:.1f}→{result_cps:.1f} | WPS {current_wps:.1f}→{result_wps:.1f} | Speed: {speed:.2f}x | \"{trans_text[:25]}...\"")

        return max(MIN_SPEED, min(MAX_SPEED, speed))

    else:
        # Legacy ratio-based calculation
        orig_len = len(orig_text.strip())
        if orig_len == 0:
            return 1.0

        ratio = trans_len / orig_len
        return max(MIN_SPEED, min(MAX_SPEED, ratio))


def build_segments(eng_subs: List[Dict], rus_texts: List[str], video_duration_ms: int) -> List[Dict]:
    """
    Строит список сегментов с гарантией отсутствия перекрытий.

    ВАЖНО: Каждый сегмент — это диапазон [start_ms, end_ms) в ИСХОДНОМ видео.
    Сегменты идут последовательно и НЕ перекрываются.
    """
    segments = []
    count = min(len(eng_subs), len(rus_texts))

    # Сортируем субтитры по времени начала
    sorted_subs = sorted(enumerate(eng_subs[:count]), key=lambda x: x[1]['start_ms'])

    current_pos = 0  # Текущая позиция в исходном видео (мс)

    for orig_idx, sub in sorted_subs:
        orig_start = sub['start_ms']
        orig_end = sub['end_ms']
        eng_text = sub['text']
        rus_text = rus_texts[orig_idx]

        # Gap перед субтитром (если есть)
        if orig_start > current_pos:
            segments.append({
                'type': 'gap',
                'orig_start_ms': current_pos,
                'orig_end_ms': orig_start,
                'speed': 1.0,
                'eng_text': '',
                'rus_text': '',
                'sub_index': None
            })
            current_pos = orig_start

        # Если субтитры перекрываются с предыдущим — корректируем
        if orig_start < current_pos:
            orig_start = current_pos
            if orig_start >= orig_end:
                continue  # Пропускаем полностью перекрытый субтитр

        # Вычисляем скорость на основе CPS
        duration_ms = orig_end - orig_start
        speed = calculate_speed(eng_text, rus_text, duration_ms)

        segments.append({
            'type': 'subtitle',
            'orig_start_ms': orig_start,
            'orig_end_ms': orig_end,
            'speed': speed,
            'eng_text': eng_text,
            'rus_text': rus_text,
            'sub_index': orig_idx + 1
        })

        current_pos = orig_end

    # Хвост видео
    if current_pos < video_duration_ms:
        segments.append({
            'type': 'gap',
            'orig_start_ms': current_pos,
            'orig_end_ms': video_duration_ms,
            'speed': 1.0,
            'eng_text': '',
            'rus_text': '',
            'sub_index': None
        })

    return segments


def merge_segments(segments: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
    """
    Объединяет соседние сегменты с похожей скоростью.
    Возвращает (merged_segments, subtitle_info для SRT).
    """
    if not segments:
        return [], []

    # Сохраняем информацию о субтитрах ДО слияния
    subtitle_info = []
    for seg in segments:
        if seg['type'] == 'subtitle':
            subtitle_info.append({
                'sub_index': seg['sub_index'],
                'orig_start_ms': seg['orig_start_ms'],
                'orig_end_ms': seg['orig_end_ms'],
                'speed': seg['speed'],
                'text': seg['rus_text']
            })

    # Слияние сегментов
    merged = []
    current = segments[0].copy()
    merge_count = 0

    for next_seg in segments[1:]:
        # Сливаем если скорости почти одинаковые
        if abs(current['speed'] - next_seg['speed']) < MERGE_THRESHOLD:
            current['orig_end_ms'] = next_seg['orig_end_ms']
            merge_count += 1
        else:
            merged.append(current)
            current = next_seg.copy()

    merged.append(current)

    safe_print(f"  ✨ Оптимизация: {len(segments)} → {len(merged)} сегментов (слито: {merge_count})")

    return merged, subtitle_info


def process_segment(args: tuple) -> Optional[Dict]:
    """
    Рендерит один сегмент с использованием ТОЧНОГО trim.

    Используем фильтр trim вместо -ss/-t для гарантии точности.
    Гибридный подход: быстрый seek близко к началу + точный trim.
    """
    idx, seg, input_video, temp_dir, encoder, enc_opts, fps = args

    orig_start_sec = seg['orig_start_ms'] / 1000.0
    orig_end_sec = seg['orig_end_ms'] / 1000.0
    orig_duration_sec = orig_end_sec - orig_start_sec

    if orig_duration_sec < 0.04:
        return None

    temp_file = temp_dir / f"seg_{idx:04d}.mp4"
    speed = seg['speed']

    # Быстрый seek на 1 секунду раньше (для скорости)
    seek_sec = max(0, orig_start_sec - 1.0)

    # Относительные позиции после seek
    rel_start = orig_start_sec - seek_sec
    rel_end = orig_end_sec - seek_sec

    # Фильтры с ТОЧНЫМ trim
    # trim обрезает по ИСХОДНЫМ таймкодам потока
    # setpts сбрасывает таймштампы и применяет скорость
    video_filter = (
        f"trim=start={rel_start:.4f}:end={rel_end:.4f},"
        f"setpts={speed:.4f}*(PTS-STARTPTS)"
    )

    # Аудио: atempo работает наоборот (0.5 = замедление в 2 раза)
    audio_speed = 1.0 / speed if speed > 0 else 1.0

    # Цепочка atempo (ограничение 0.5-2.0)
    atempo_parts = []
    temp_speed = audio_speed
    while temp_speed < 0.5:
        atempo_parts.append("atempo=0.5")
        temp_speed /= 0.5
    while temp_speed > 2.0:
        atempo_parts.append("atempo=2.0")
        temp_speed /= 2.0
    atempo_parts.append(f"atempo={temp_speed:.4f}")

    audio_filter = (
        f"atrim=start={rel_start:.4f}:end={rel_end:.4f},"
        f"asetpts=PTS-STARTPTS,"
        f"{','.join(atempo_parts)}"
    )

    cmd = [
        'ffmpeg', '-hide_banner', '-y',
        '-ss', f'{seek_sec:.3f}',  # Быстрый seek
        '-i', str(input_video),
        '-filter_complex', f'[0:v]{video_filter}[v];[0:a]{audio_filter}[a]',
        '-map', '[v]', '-map', '[a]',
        '-c:v', encoder, *enc_opts,
        '-c:a', 'aac', '-b:a', '128k',
        '-r', str(fps),
        '-avoid_negative_ts', 'make_zero',
        '-fflags', '+genpts',
        '-loglevel', 'error',
        str(temp_file)
    ]

    start_t = time.time()
    res = subprocess.run(cmd, capture_output=True, text=True)
    proc_time = time.time() - start_t

    if res.returncode != 0:
        safe_print(f"  ❌ Сег {idx}: {res.stderr[:150] if res.stderr else 'unknown error'}")
        return None

    if temp_file.exists() and temp_file.stat().st_size > 0:
        # Выходная длительность = исходная * speed
        output_duration_ms = int(orig_duration_sec * speed * 1000)

        speed_label = "SLOW" if speed > 1.01 else "FAST" if speed < 0.99 else "NORM"
        safe_print(
            f"  ✅ Seg {idx:03d} | {speed_label:>4} {speed:.2f}x | "
            f"{orig_duration_sec:.1f}s → {output_duration_ms/1000:.1f}s | {proc_time:.1f}s"
        )

        return {
            'idx': idx,
            'file': temp_file,
            'output_duration_ms': output_duration_ms,
            'orig_start_ms': seg['orig_start_ms'],
            'orig_end_ms': seg['orig_end_ms'],
            'speed': speed
        }

    safe_print(f"  ❌ Сег {idx}: файл пуст или не создан")
    return None


def calculate_new_subtitle_times(results: List[Dict], subtitle_info: List[Dict]) -> List[Dict]:
    """Пересчитывает тайминги субтитров для выходного видео."""

    # Строим временную карту: orig_time → new_time
    time_map = []
    new_pos = 0

    for r in sorted(results, key=lambda x: x['idx']):
        time_map.append({
            'orig_start': r['orig_start_ms'],
            'orig_end': r['orig_end_ms'],
            'new_start': new_pos,
            'new_end': new_pos + r['output_duration_ms'],
            'speed': r['speed']
        })
        new_pos += r['output_duration_ms']

    # Пересчитываем позиции субтитров
    new_subs = []

    for sub in subtitle_info:
        orig_start = sub['orig_start_ms']
        orig_end = sub['orig_end_ms']

        # Ищем сегмент, содержащий начало субтитра
        for tm in time_map:
            if tm['orig_start'] <= orig_start < tm['orig_end']:
                # Интерполируем позицию
                offset_orig = orig_start - tm['orig_start']
                offset_new = int(offset_orig * tm['speed'])
                new_start = tm['new_start'] + offset_new

                # Длительность масштабируется по скорости субтитра
                orig_duration = orig_end - orig_start
                new_duration = int(orig_duration * sub['speed'])
                new_end = new_start + new_duration

                new_subs.append({
                    'index': sub['sub_index'],
                    'start_ms': new_start,
                    'end_ms': new_end,
                    'text': sub['text']
                })
                break

    return new_subs


def read_file_safe(path: Path) -> Optional[str]:
    """Читает файл с автоопределением кодировки."""
    encodings = ['utf-8', 'utf-8-sig', 'windows-1251', 'cp1252', 'latin-1']
    for enc in encodings:
        try:
            return path.read_text(encoding=enc)
        except:
            continue
    return None


def main():
    script_dir = Path(__file__).parent.resolve()

    # Support paths from environment variables (set by GUI)
    input_video = Path(os.environ.get('VST_VIDEO_INPUT', script_dir / 'input.mp4'))
    eng_srt_file = Path(os.environ.get('VST_SRT_INPUT', script_dir / 'output.srt'))
    rus_srt_file = Path(os.environ.get('VST_TRANSLATION', script_dir / 'russian.srt'))
    rus_txt_file = Path(os.environ.get('VST_TRANSLATION', script_dir / 'Penis.txt'))

    # Output directory from environment or default to input video's parent
    output_dir_env = os.environ.get('VST_OUTPUT_DIR', '')
    output_dir = Path(output_dir_env) if output_dir_env else input_video.parent
    output_video = output_dir / 'output_adjusted.mp4'
    output_srt = output_dir / 'adjusted.srt'
    temp_dir = output_dir / 'temp_segments'

    print("\n" + "=" * 65)
    print("  🎬 VIDEO SPEED ADJUSTER v4.1 (CPS + WPS Based)")
    print("=" * 65)
    print(f"  📊 Target CPS: {TARGET_CPS} (max {MAX_CPS} for Aegisub)")
    print(f"  🗣️ Target WPS: {TARGET_WPS} (max {MAX_WPS} words/sec)")
    print(f"  ⚡ Speed range: {MIN_SPEED}x - {MAX_SPEED}x")
    print(f"  📂 Output dir: {output_dir}")
    print("=" * 65)

    # Проверка входного видео
    if not input_video.exists():
        print(f"❌ Не найден видео файл: {input_video}")
        sys.exit(1)

    if not eng_srt_file.exists():
        print(f"❌ Не найден SRT файл: {eng_srt_file}")
        sys.exit(1)

    # Ищем русские субтитры (SRT или TXT)
    rus_content = None
    rus_is_srt = False

    if rus_srt_file.exists():
        rus_content = read_file_safe(rus_srt_file)
        rus_is_srt = True
        print(f"📄 Русские субтитры: russian.srt")
    elif rus_txt_file.exists():
        rus_content = read_file_safe(rus_txt_file)
        rus_is_srt = False
        print(f"📄 Русский текст: Penis.txt")
    else:
        print(f"❌ Не найден файл перевода: {rus_txt_file}")
        sys.exit(1)

    # Читаем английские субтитры
    eng_content = read_file_safe(eng_srt_file)
    if not eng_content:
        print("❌ Не удалось прочитать output.srt")
        sys.exit(1)

    eng_subs = parse_srt(eng_content)
    print(f"📝 Английских субтитров: {len(eng_subs)}")

    # Читаем русский текст
    if rus_is_srt:
        rus_subs = parse_srt(rus_content)
        rus_texts = [s['text'] for s in rus_subs]
    else:
        rus_texts = parse_numbered_text(rus_content)

    print(f"📝 Русских фраз: {len(rus_texts)}")

    if len(eng_subs) != len(rus_texts):
        print(f"⚠️ Внимание: количество не совпадает! Будет использовано: {min(len(eng_subs), len(rus_texts))}")

    # Определяем энкодер
    encoder, enc_opts, encoder_name = detect_gpu_encoder()
    print(f"🔧 Энкодер: {encoder_name}")

    # Информация о видео
    info = get_video_info(input_video)
    fps = max(24, min(60, round(info['fps'])))
    duration_ms = int(info['duration'] * 1000)
    print(f"📼 Видео: {ms_to_time(duration_ms)} | {fps} FPS")

    # Строим сегменты
    print("\n🔍 Анализ субтитров...")
    raw_segments = build_segments(eng_subs, rus_texts, duration_ms)

    # Статистика скоростей
    speeds = [s['speed'] for s in raw_segments if s['type'] == 'subtitle']
    if speeds:
        slow_count = sum(1 for s in speeds if s > 1.01)
        fast_count = sum(1 for s in speeds if s < 0.99)
        norm_count = len(speeds) - slow_count - fast_count
        print(f"  📊 Замедлений: {slow_count} | Ускорений: {fast_count} | Без изменений: {norm_count}")

    # Оптимизация (слияние)
    merged_segments, subtitle_info = merge_segments(raw_segments)

    # Подготовка временной папки
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir()

    # Рендер
    max_workers = 3 if encoder != 'libx264' else max(2, os.cpu_count() - 1)
    print(f"\n🚀 Рендер в {max_workers} потока...")

    tasks = [(i, seg, input_video, temp_dir, encoder, enc_opts, fps)
             for i, seg in enumerate(merged_segments)]

    results = []
    start_time = time.time()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_segment, t): t[0] for t in tasks}
        for future in as_completed(futures):
            res = future.result()
            if res:
                results.append(res)

    results.sort(key=lambda x: x['idx'])

    if not results:
        print("❌ Нет обработанных сегментов!")
        sys.exit(1)

    elapsed = time.time() - start_time
    print(f"\n⏱️ Рендер завершён: {elapsed:.1f} сек")

    # Склейка
    print("🔗 Склеивание...")
    concat_file = temp_dir / 'concat.txt'
    with open(concat_file, 'w', encoding='utf-8') as f:
        for r in results:
            safe_path = str(r['file'].absolute()).replace('\\', '/').replace("'", "'\\''")
            f.write(f"file '{safe_path}'\n")

    cmd = [
        'ffmpeg', '-hide_banner', '-y',
        '-f', 'concat', '-safe', '0',
        '-i', str(concat_file),
        '-c', 'copy',
        '-movflags', '+faststart',
        str(output_video)
    ]
    subprocess.run(cmd, capture_output=True)

    # Генерация субтитров
    print("✍️ Генерация субтитров...")
    new_subs = calculate_new_subtitle_times(results, subtitle_info)

    srt_blocks = []
    for s in sorted(new_subs, key=lambda x: x['index']):
        srt_blocks.append(f"{s['index']}\n{ms_to_time(s['start_ms'])} --> {ms_to_time(s['end_ms'])}\n{s['text']}")

    output_srt.write_text('\n\n'.join(srt_blocks), encoding='utf-8')

    # Очистка
    print("🧹 Очистка...")
    shutil.rmtree(temp_dir, ignore_errors=True)

    # Итоговая информация
    total_output_ms = sum(r['output_duration_ms'] for r in results)

    # Calculate final CPS and WPS stats
    total_chars = sum(len(s['text']) for s in new_subs)
    total_words = sum(count_words(s['text']) for s in new_subs)
    final_total_duration = total_output_ms / 1000.0
    avg_cps = total_chars / final_total_duration if final_total_duration > 0 else 0
    avg_wps = total_words / final_total_duration if final_total_duration > 0 else 0

    print(f"\n{'='*65}")
    print(f"✅ Готово!")
    print(f"   📁 Видео: {output_video.name}")
    print(f"   📁 Субтитры: {output_srt.name}")
    print(f"   ⏱️ Исходная длительность: {ms_to_time(duration_ms)}")
    print(f"   ⏱️ Новая длительность: {ms_to_time(total_output_ms)}")
    print(f"   📊 Средний CPS: {avg_cps:.1f} (цель: {TARGET_CPS})")
    print(f"   🗣️ Средний WPS: {avg_wps:.1f} (цель: {TARGET_WPS})")
    print(f"{'='*65}\n")


if __name__ == '__main__':
    main()
