#!/usr/bin/env python3
"""
Video Speed Adjuster v5.0 - ПРОСТОЙ И НАДЁЖНЫЙ

Замедляет видео чтобы CPS был комфортным для озвучки.
Каждый субтитр = отдельный сегмент видео. Без магии.
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

# === НАСТРОЙКИ ===
TARGET_CPS = 16.0       # Целевой CPS (символов в секунду) после замедления
SOFT_THRESHOLD = 16.0   # Ниже этого - не трогаем
HARD_THRESHOLD = 20.0   # Выше этого - полное замедление
MAX_SLOWDOWN = 3.0      # Максимальное замедление (3x = в 3 раза медленнее)

print_lock = threading.Lock()

def log(msg):
    with print_lock:
        print(msg)


def time_to_ms(time_str):
    """00:01:23,456 -> миллисекунды"""
    match = re.match(r'(\d+):(\d+):(\d+)[,.](\d+)', time_str.strip())
    if not match:
        return 0
    h, m, s, ms = match.groups()
    ms = ms.ljust(3, '0')[:3]
    return int(h) * 3600000 + int(m) * 60000 + int(s) * 1000 + int(ms)


def ms_to_time(ms):
    """миллисекунды -> 00:01:23,456"""
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
    """Парсит SRT файл"""
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
        text = re.sub(r'<[^>]+>', '', text)  # убираем теги
        text = re.sub(r'\{[^}]+\}', '', text)
        text = re.sub(r'\([^)]*\)', '', text)
        text = text.strip()

        if text and end > start:
            subs.append({'start': start, 'end': end, 'text': text})

    return subs


def parse_txt(content):
    """Парсит нумерованный текст"""
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
    """Читает файл с автоопределением кодировки"""
    for enc in ['utf-8', 'utf-8-sig', 'windows-1251', 'cp1252', 'latin-1']:
        try:
            return path.read_text(encoding=enc)
        except:
            pass
    return None


def get_video_duration(video_path):
    """Длительность видео в мс"""
    cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
           '-of', 'default=noprint_wrappers=1:nokey=1', str(video_path)]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        return int(float(result.stdout.strip()) * 1000)
    except:
        return 0


def get_video_fps(video_path):
    """FPS видео"""
    cmd = ['ffprobe', '-v', 'error', '-select_streams', 'v:0',
           '-show_entries', 'stream=r_frame_rate',
           '-of', 'default=noprint_wrappers=1:nokey=1', str(video_path)]
    try:
        fps_str = subprocess.run(cmd, capture_output=True, text=True).stdout.strip()
        if '/' in fps_str:
            num, den = fps_str.split('/')
            return int(num) / int(den) if int(den) != 0 else 30.0
        return float(fps_str) if fps_str else 30.0
    except:
        return 30.0


def get_encoder():
    """Определяет лучший энкодер"""
    try:
        result = subprocess.run(['ffmpeg', '-hide_banner', '-encoders'],
                               capture_output=True, text=True)
        encoders = result.stdout
    except:
        return 'libx264', ['-preset', 'fast', '-crf', '20']

    # Тест энкодера
    def test(enc):
        try:
            cmd = ['ffmpeg', '-hide_banner', '-y', '-f', 'lavfi',
                   '-i', 'color=black:s=64x64:d=0.1', '-c:v', enc, '-f', 'null', '-']
            return subprocess.run(cmd, capture_output=True, timeout=10).returncode == 0
        except:
            return False

    if 'h264_nvenc' in encoders and test('h264_nvenc'):
        return 'h264_nvenc', ['-preset', 'p1', '-rc', 'vbr', '-cq', '22']
    if 'h264_amf' in encoders and test('h264_amf'):
        return 'h264_amf', ['-quality', 'speed', '-rc', 'vbr_peak', '-qp_i', '22', '-qp_p', '22']
    if 'h264_qsv' in encoders and test('h264_qsv'):
        return 'h264_qsv', ['-preset', 'veryfast', '-global_quality', '22']

    return 'libx264', ['-preset', 'fast', '-crf', '20']


def calculate_slowdown(text, duration_ms):
    """
    Вычисляет на сколько замедлить видео с ПЛАВНЫМ переходом.

    CPS <= 16: без замедления
    CPS 16-20: плавное нарастание замедления
    CPS >= 20: полное замедление до TARGET_CPS (16)

    Возвращает коэффициент замедления (1.0 = без изменений, 2.0 = в 2 раза медленнее)
    """
    if not text or duration_ms <= 0:
        return 1.0

    chars = len(text)
    duration_sec = duration_ms / 1000.0
    current_cps = chars / duration_sec

    # Ниже мягкого порога - не трогаем
    if current_cps <= SOFT_THRESHOLD:
        return 1.0

    # Полное замедление (сколько нужно для TARGET_CPS)
    full_slowdown = current_cps / TARGET_CPS

    # Плавный переход между SOFT и HARD threshold
    if current_cps < HARD_THRESHOLD:
        # Линейная интерполяция: 0 при SOFT, 1 при HARD
        blend = (current_cps - SOFT_THRESHOLD) / (HARD_THRESHOLD - SOFT_THRESHOLD)
        # Плавнее через smoothstep: 3x² - 2x³
        blend = blend * blend * (3 - 2 * blend)
        slowdown = 1.0 + (full_slowdown - 1.0) * blend
    else:
        # Выше жёсткого порога - полное замедление
        slowdown = full_slowdown

    # Ограничиваем максимальное замедление
    slowdown = min(slowdown, MAX_SLOWDOWN)

    result_cps = chars / (duration_sec * slowdown)
    zone = "SOFT" if current_cps < HARD_THRESHOLD else "FULL"
    log(f"    [{chars} симв] CPS: {current_cps:.1f} → {result_cps:.1f} | x{slowdown:.2f} ({zone})")

    return slowdown


def get_real_duration_ms(video_path, fallback_ms=None):
    """Получает РЕАЛЬНУЮ длительность видео в мс через ffprobe"""
    cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
           '-of', 'default=noprint_wrappers=1:nokey=1', str(video_path)]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        duration = float(result.stdout.strip())
        if duration > 0:
            return int(duration * 1000)
    except:
        pass
    # Fallback на теоретическую длительность если ffprobe не сработал
    return fallback_ms if fallback_ms else 0


def render_segment(idx, start_ms, end_ms, slowdown, input_video, temp_dir, encoder, enc_opts, fps):
    """Рендерит один сегмент видео"""

    start_sec = start_ms / 1000.0
    end_sec = end_ms / 1000.0
    duration_sec = end_sec - start_sec

    if duration_sec < 0.04:
        return None

    output_file = temp_dir / f"seg_{idx:04d}.mp4"

    # Seek чуть раньше для точности
    seek = max(0, start_sec - 1.0)
    rel_start = start_sec - seek
    rel_end = end_sec - seek

    # Видео фильтр: trim + замедление через setpts
    # setpts=2.0*PTS = в 2 раза медленнее
    vf = f"trim=start={rel_start:.4f}:end={rel_end:.4f},setpts={slowdown:.4f}*(PTS-STARTPTS)"

    # Аудио: atempo работает наоборот (0.5 = замедление в 2 раза)
    tempo = 1.0 / slowdown
    atempo_chain = []
    t = tempo
    while t < 0.5:
        atempo_chain.append("atempo=0.5")
        t /= 0.5
    while t > 2.0:
        atempo_chain.append("atempo=2.0")
        t /= 2.0
    atempo_chain.append(f"atempo={t:.4f}")

    af = f"atrim=start={rel_start:.4f}:end={rel_end:.4f},asetpts=PTS-STARTPTS,{','.join(atempo_chain)}"

    cmd = [
        'ffmpeg', '-hide_banner', '-y',
        '-ss', f'{seek:.3f}',
        '-i', str(input_video),
        '-filter_complex', f'[0:v]{vf}[v];[0:a]{af}[a]',
        '-map', '[v]', '-map', '[a]',
        '-c:v', encoder, *enc_opts,
        '-c:a', 'aac', '-b:a', '128k',
        '-r', str(int(fps)),
        '-avoid_negative_ts', 'make_zero',
        '-fflags', '+genpts',
        '-loglevel', 'error',
        str(output_file)
    ]

    t0 = time.time()
    result = subprocess.run(cmd, capture_output=True, text=True)
    elapsed = time.time() - t0

    if result.returncode != 0:
        log(f"  ❌ Seg {idx}: {result.stderr[:100] if result.stderr else 'error'}")
        return None

    if output_file.exists() and output_file.stat().st_size > 0:
        # РЕАЛЬНАЯ длительность вместо теоретической - избегаем рассинхрона!
        theoretical_ms = int(duration_sec * slowdown * 1000)
        real_duration_ms = get_real_duration_ms(output_file, fallback_ms=theoretical_ms)
        drift = real_duration_ms - theoretical_ms

        label = "SLOW" if slowdown > 1.01 else "NORM"
        drift_str = f" drift:{drift:+d}ms" if abs(drift) > 10 else ""
        log(f"  ✅ Seg {idx:03d} | {label} x{slowdown:.2f} | {duration_sec:.1f}s → {real_duration_ms/1000:.1f}s | {elapsed:.1f}s{drift_str}")

        return {
            'idx': idx,
            'file': output_file,
            'duration_ms': real_duration_ms  # РЕАЛЬНАЯ длительность!
        }

    return None


def main():
    script_dir = Path(__file__).parent.resolve()

    # Пути из переменных окружения или дефолтные
    input_video = Path(os.environ.get('VST_VIDEO_INPUT', script_dir / 'input.mp4'))
    eng_srt = Path(os.environ.get('VST_SRT_INPUT', script_dir / 'output.srt'))
    rus_srt = Path(os.environ.get('VST_TRANSLATION', script_dir / 'russian.srt'))
    rus_txt = Path(os.environ.get('VST_TRANSLATION', script_dir / 'Penis.txt'))

    output_dir = Path(os.environ.get('VST_OUTPUT_DIR', '')) or input_video.parent
    output_video = output_dir / 'output_adjusted.mp4'
    output_srt = output_dir / 'adjusted.srt'
    temp_dir = output_dir / 'temp_segments'

    print("\n" + "=" * 60)
    print("  🎬 VIDEO SPEED ADJUSTER v5.2 (real duration sync)")
    print("=" * 60)
    print(f"  Target CPS: {TARGET_CPS}")
    print(f"  Soft threshold: {SOFT_THRESHOLD} (no slowdown below)")
    print(f"  Hard threshold: {HARD_THRESHOLD} (full slowdown above)")
    print(f"  Max slowdown: {MAX_SLOWDOWN}x")
    print("=" * 60)

    # Проверки
    if not input_video.exists():
        print(f"❌ Видео не найдено: {input_video}")
        sys.exit(1)

    if not eng_srt.exists():
        print(f"❌ SRT не найден: {eng_srt}")
        sys.exit(1)

    # Читаем английские субтитры
    eng_content = read_file(eng_srt)
    if not eng_content:
        print("❌ Не удалось прочитать SRT")
        sys.exit(1)
    eng_subs = parse_srt(eng_content)
    print(f"📝 Английских субтитров: {len(eng_subs)}")

    # Читаем русский перевод
    rus_texts = []
    if rus_srt.exists():
        content = read_file(rus_srt)
        rus_texts = [s['text'] for s in parse_srt(content)]
        print(f"📝 Русский SRT: {len(rus_texts)} строк")
    elif rus_txt.exists():
        content = read_file(rus_txt)
        rus_texts = parse_txt(content)
        print(f"📝 Русский TXT: {len(rus_texts)} строк")
    else:
        print("❌ Русский перевод не найден")
        sys.exit(1)

    if len(eng_subs) != len(rus_texts):
        print(f"⚠️ Количество не совпадает! Используем: {min(len(eng_subs), len(rus_texts))}")

    # Инфо о видео
    video_duration = get_video_duration(input_video)
    fps = get_video_fps(input_video)
    fps = max(24, min(60, round(fps)))
    print(f"📼 Видео: {ms_to_time(video_duration)} @ {fps} FPS")

    encoder, enc_opts = get_encoder()
    print(f"🔧 Энкодер: {encoder}")

    # === СТРОИМ СЕГМЕНТЫ ===
    print("\n🔍 Анализ...")

    segments = []  # список: (start_ms, end_ms, slowdown, sub_index, rus_text)
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
                'start': current_pos,
                'end': start,
                'slowdown': 1.0,
                'sub_index': None,
                'text': ''
            })

        # Сам субтитр
        if start < current_pos:
            start = current_pos
        if start >= end:
            continue

        duration = end - start
        slowdown = calculate_slowdown(rus_text, duration)

        segments.append({
            'start': start,
            'end': end,
            'slowdown': slowdown,
            'sub_index': i + 1,
            'text': rus_text
        })

        current_pos = end

    # Хвост видео
    if current_pos < video_duration:
        segments.append({
            'start': current_pos,
            'end': video_duration,
            'slowdown': 1.0,
            'sub_index': None,
            'text': ''
        })

    # Статистика
    sub_segments = [s for s in segments if s['sub_index'] is not None]
    slow_count = sum(1 for s in sub_segments if s['slowdown'] > 1.01)
    print(f"  📊 Субтитров: {len(sub_segments)} | Замедлений: {slow_count}")

    # === РЕНДЕР ===
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir()

    print(f"\n🚀 Рендер ({len(segments)} сегментов)...")

    results = []
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {}
        for idx, seg in enumerate(segments):
            future = executor.submit(
                render_segment,
                idx, seg['start'], seg['end'], seg['slowdown'],
                input_video, temp_dir, encoder, enc_opts, fps
            )
            futures[future] = (idx, seg)

        for future in as_completed(futures):
            idx, seg = futures[future]
            result = future.result()
            if result:
                result['sub_index'] = seg['sub_index']
                result['text'] = seg['text']
                results.append(result)

    results.sort(key=lambda x: x['idx'])

    if not results:
        print("❌ Ничего не отрендерилось!")
        sys.exit(1)

    # === СКЛЕЙКА ===
    print("🔗 Склеивание...")

    concat_file = temp_dir / 'concat.txt'
    with open(concat_file, 'w') as f:
        for r in results:
            path = str(r['file'].absolute()).replace("'", "'\\''")
            f.write(f"file '{path}'\n")

    cmd = [
        'ffmpeg', '-hide_banner', '-y',
        '-f', 'concat', '-safe', '0',
        '-i', str(concat_file),
        '-c', 'copy',
        '-movflags', '+faststart',
        str(output_video)
    ]
    subprocess.run(cmd, capture_output=True)

    # === СУБТИТРЫ ===
    print("✍️ Генерация субтитров...")

    # Позиции в выходном видео
    new_pos = 0
    srt_lines = []

    for r in results:
        duration = r['duration_ms']
        sub_index = r['sub_index']
        text = r['text']

        if sub_index is not None and text:
            start_time = ms_to_time(new_pos)
            end_time = ms_to_time(new_pos + duration)
            srt_lines.append(f"{sub_index}\n{start_time} --> {end_time}\n{text}")

        new_pos += duration

    output_srt.write_text('\n\n'.join(srt_lines), encoding='utf-8')

    # === ОЧИСТКА ===
    print("🧹 Очистка...")
    shutil.rmtree(temp_dir, ignore_errors=True)

    # === ИТОГ ===
    total_duration = sum(r['duration_ms'] for r in results)
    total_chars = sum(len(r['text']) for r in results if r['text'])
    avg_cps = total_chars / (total_duration / 1000) if total_duration > 0 else 0

    print(f"\n{'=' * 60}")
    print(f"✅ ГОТОВО!")
    print(f"   Видео: {output_video.name}")
    print(f"   Субтитры: {output_srt.name}")
    print(f"   Было: {ms_to_time(video_duration)}")
    print(f"   Стало: {ms_to_time(total_duration)}")
    print(f"   Средний CPS: {avg_cps:.1f} (цель: {TARGET_CPS})")
    print(f"{'=' * 60}\n")


if __name__ == '__main__':
    main()
