#!/usr/bin/env python3
"""
Video Speed Adjuster v6.0 - ЕДИНЫЙ FILTER_COMPLEX

Замедляет видео чтобы CPS был комфортным для озвучки.
Один проход FFmpeg, без промежуточных файлов, точная синхронизация.
"""

import re
import sys
import subprocess
import os
from pathlib import Path

# === НАСТРОЙКИ ===
TARGET_CPS = 17.0   # Целевой CPS (символов в секунду)
MAX_SLOWDOWN = 3.0  # Максимальное замедление (3x = в 3 раза медленнее)


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
        text = re.sub(r'<[^>]+>', '', text)
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
    """Вычисляет коэффициент замедления"""
    if not text or duration_ms <= 0:
        return 1.0

    chars = len(text)
    duration_sec = duration_ms / 1000.0
    current_cps = chars / duration_sec

    if current_cps <= TARGET_CPS:
        return 1.0

    needed_duration = chars / TARGET_CPS
    slowdown = needed_duration / duration_sec

    # Ослабляем эффект замедления на 35%
    slowdown = 1.0 + (slowdown - 1.0) * 0.65

    slowdown = min(slowdown, MAX_SLOWDOWN)
    return slowdown


def build_atempo_chain(slowdown):
    """Строит цепочку atempo фильтров для замедления аудио"""
    tempo = 1.0 / slowdown
    chain = []
    t = tempo
    while t < 0.5:
        chain.append("atempo=0.5")
        t /= 0.5
    while t > 2.0:
        chain.append("atempo=2.0")
        t /= 2.0
    chain.append(f"atempo={t:.6f}")
    return ','.join(chain)


def main():
    script_dir = Path(__file__).parent.resolve()

    # Пути
    input_video = Path(os.environ.get('VST_VIDEO_INPUT', script_dir / 'input.mp4'))
    eng_srt = Path(os.environ.get('VST_SRT_INPUT', script_dir / 'output.srt'))
    rus_srt = Path(os.environ.get('VST_TRANSLATION', script_dir / 'russian.srt'))
    rus_txt = Path(os.environ.get('VST_TRANSLATION', script_dir / 'Penis.txt'))

    output_dir = Path(os.environ.get('VST_OUTPUT_DIR', '')) or input_video.parent
    output_video = output_dir / 'output_adjusted.mp4'
    output_srt = output_dir / 'adjusted.srt'

    print("\n" + "=" * 60)
    print("  🎬 VIDEO SPEED ADJUSTER v6.0 (Single Filter)")
    print("=" * 60)
    print(f"  Target CPS: {TARGET_CPS}")
    print(f"  Max slowdown: {MAX_SLOWDOWN}x")
    print("=" * 60)

    # Проверки
    if not input_video.exists():
        print(f"❌ Видео не найдено: {input_video}")
        sys.exit(1)

    if not eng_srt.exists():
        print(f"❌ SRT не найден: {eng_srt}")
        sys.exit(1)

    # Читаем субтитры
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
    print("\n🔍 Анализ сегментов...")

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

        if slowdown > 1.01:
            chars = len(rus_text)
            duration_sec = duration / 1000.0
            current_cps = chars / duration_sec
            result_cps = chars / (duration_sec * slowdown)
            print(f"  [{chars} симв] CPS: {current_cps:.1f} → {result_cps:.1f} | x{slowdown:.2f}")

        segments.append({
            'start_ms': start,
            'end_ms': end,
            'slowdown': slowdown,
            'sub_index': i + 1,
            'text': rus_text
        })

        current_pos = end

    # Хвост видео
    if current_pos < video_duration:
        segments.append({
            'start_ms': current_pos,
            'end_ms': video_duration,
            'slowdown': 1.0,
            'sub_index': None,
            'text': ''
        })

    # Фильтруем пустые сегменты
    segments = [s for s in segments if s['end_ms'] > s['start_ms'] + 10]

    sub_segments = [s for s in segments if s['sub_index'] is not None]
    slow_count = sum(1 for s in sub_segments if s['slowdown'] > 1.01)
    print(f"\n📊 Всего сегментов: {len(segments)} | С субтитрами: {len(sub_segments)} | Замедлений: {slow_count}")

    # === СТРОИМ FILTER_COMPLEX ===
    print("\n🔧 Построение filter_complex...")

    video_filters = []
    audio_filters = []
    video_labels = []
    audio_labels = []

    for idx, seg in enumerate(segments):
        start_sec = seg['start_ms'] / 1000.0
        end_sec = seg['end_ms'] / 1000.0
        slowdown = seg['slowdown']

        v_label = f"v{idx}"
        a_label = f"a{idx}"

        # Видео: trim + setpts для замедления
        vf = f"[0:v]trim=start={start_sec:.4f}:end={end_sec:.4f},setpts={slowdown:.6f}*(PTS-STARTPTS)[{v_label}]"
        video_filters.append(vf)
        video_labels.append(f"[{v_label}]")

        # Аудио: atrim + atempo для замедления
        atempo = build_atempo_chain(slowdown)
        af = f"[0:a]atrim=start={start_sec:.4f}:end={end_sec:.4f},asetpts=PTS-STARTPTS,{atempo}[{a_label}]"
        audio_filters.append(af)
        audio_labels.append(f"[{a_label}]")

    # Concat всех сегментов
    n = len(segments)
    video_concat = f"{''.join(video_labels)}concat=n={n}:v=1:a=0[vout]"
    audio_concat = f"{''.join(audio_labels)}concat=n={n}:v=0:a=1[aout]"

    filter_complex = ';'.join(video_filters + audio_filters + [video_concat, audio_concat])

    print(f"  📐 Filter complex: {len(filter_complex)} символов")

    # Записываем filter в файл (обход лимита командной строки Windows)
    filter_file = output_dir / 'filter_complex.txt'
    filter_file.write_text(filter_complex, encoding='utf-8')

    # === РЕНДЕР ===
    print("\n🚀 Рендер (один проход)...")

    # Ожидаемая длительность выходного видео
    expected_duration_sec = sum((s['end_ms'] - s['start_ms']) * s['slowdown'] for s in segments) / 1000.0

    cmd = [
        'ffmpeg', '-hide_banner', '-y',
        '-i', str(input_video),
        '-filter_complex_script', str(filter_file),
        '-map', '[vout]', '-map', '[aout]',
        '-c:v', encoder, *enc_opts,
        '-c:a', 'aac', '-b:a', '128k',
        '-r', str(fps),
        '-movflags', '+faststart',
        '-progress', 'pipe:1',
        str(output_video)
    ]

    import time
    t0 = time.time()

    # Запускаем FFmpeg с отслеживанием прогресса
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                universal_newlines=True, bufsize=1)

    current_time = 0
    while True:
        line = process.stdout.readline()
        if not line and process.poll() is not None:
            break

        if line.startswith('out_time_ms='):
            try:
                time_ms = int(line.split('=')[1].strip())
                current_time = time_ms / 1000000.0  # микросекунды -> секунды
                if expected_duration_sec > 0:
                    percent = min(100, (current_time / expected_duration_sec) * 100)
                    bar_len = 30
                    filled = int(bar_len * percent / 100)
                    bar = '█' * filled + '░' * (bar_len - filled)
                    elapsed = time.time() - t0
                    print(f"\r  [{bar}] {percent:5.1f}% | {current_time:.1f}s / {expected_duration_sec:.1f}s | ⏱ {elapsed:.0f}s", end='', flush=True)
            except:
                pass

    process.wait()
    elapsed = time.time() - t0
    print()  # Новая строка после прогресс-бара

    # Удаляем временный файл фильтра
    filter_file.unlink(missing_ok=True)

    if process.returncode != 0:
        print(f"❌ FFmpeg ошибка:")
        stderr = process.stderr.read()
        print(stderr[-1000:] if stderr else "Unknown error")
        input("Нажмите Enter для выхода...")
        sys.exit(1)

    print(f"  ✅ Рендер завершён за {elapsed:.1f}s")

    # === СУБТИТРЫ ===
    print("\n✍️ Генерация субтитров...")

    # Вычисляем позиции на основе slowdown
    new_pos = 0.0
    srt_lines = []

    for seg in segments:
        orig_duration = seg['end_ms'] - seg['start_ms']
        new_duration = orig_duration * seg['slowdown']

        if seg['sub_index'] is not None and seg['text']:
            start_time = ms_to_time(int(new_pos))
            end_time = ms_to_time(int(new_pos + new_duration))
            srt_lines.append(f"{seg['sub_index']}\n{start_time} --> {end_time}\n{seg['text']}")

        new_pos += new_duration

    output_srt.write_text('\n\n'.join(srt_lines), encoding='utf-8')

    # === ИТОГ ===
    real_duration = get_video_duration(output_video)
    total_chars = sum(len(s['text']) for s in segments if s['text'])
    avg_cps = total_chars / (real_duration / 1000) if real_duration > 0 else 0

    print(f"\n{'=' * 60}")
    print(f"✅ ГОТОВО!")
    print(f"   Видео: {output_video.name}")
    print(f"   Субтитры: {output_srt.name}")
    print(f"   Было: {ms_to_time(video_duration)}")
    print(f"   Стало: {ms_to_time(real_duration)}")
    print(f"   Средний CPS: {avg_cps:.1f} (цель: {TARGET_CPS})")
    print(f"   Время рендера: {elapsed:.1f}s")
    print(f"{'=' * 60}\n")

    input("Нажмите Enter для выхода...")


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        input("Нажмите Enter для выхода...")
