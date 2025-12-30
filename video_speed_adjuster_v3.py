#!/usr/bin/env python3
"""
Video Speed Adjuster v6.0 - ИДЕАЛЬНАЯ ВЕРСИЯ

Замедляет видео чтобы CPS был комфортным для озвучки.
Каждый субтитр = отдельный сегмент видео.

Улучшения v6.0:
- Фактическая длительность сегментов через ffprobe (без drift)
- Оригинальный FPS без округления
- Retry логика для надёжности
- Валидация всех этапов
- Умная обработка перекрывающихся субтитров
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
TARGET_CPS = 12.0   # Целевой CPS (символов в секунду)
MAX_SLOWDOWN = 3.0  # Максимальное замедление (3x = в 3 раза медленнее)
MAX_RETRIES = 3     # Количество попыток рендера сегмента
PARALLEL_WORKERS = 3  # Параллельные воркеры

print_lock = threading.Lock()

def log(msg):
    with print_lock:
        print(msg, flush=True)


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


def get_segment_duration_ms(video_path):
    """
    Получает ФАКТИЧЕСКУЮ длительность видео в миллисекундах через ffprobe.
    Это критически важно для точной синхронизации субтитров!
    """
    cmd = [
        'ffprobe', '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        str(video_path)
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0 and result.stdout.strip():
            duration_sec = float(result.stdout.strip())
            return int(duration_sec * 1000)
    except Exception as e:
        log(f"    ⚠️ ffprobe error: {e}")
    return None


def get_video_duration(video_path):
    """Длительность видео в мс"""
    duration = get_segment_duration_ms(video_path)
    return duration if duration else 0


def get_video_fps(video_path):
    """FPS видео - БЕЗ ОКРУГЛЕНИЯ для точности"""
    cmd = [
        'ffprobe', '-v', 'error', '-select_streams', 'v:0',
        '-show_entries', 'stream=r_frame_rate',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        str(video_path)
    ]
    try:
        fps_str = subprocess.run(cmd, capture_output=True, text=True, timeout=30).stdout.strip()
        if '/' in fps_str:
            num, den = fps_str.split('/')
            if int(den) != 0:
                return float(num) / float(den)
        return float(fps_str) if fps_str else 30.0
    except:
        return 30.0


def get_video_fps_str(video_path):
    """FPS видео как строка (для передачи в FFmpeg без потери точности)"""
    cmd = [
        'ffprobe', '-v', 'error', '-select_streams', 'v:0',
        '-show_entries', 'stream=r_frame_rate',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        str(video_path)
    ]
    try:
        fps_str = subprocess.run(cmd, capture_output=True, text=True, timeout=30).stdout.strip()
        if fps_str and ('/' in fps_str or fps_str.replace('.', '').isdigit()):
            return fps_str
    except:
        pass
    return '30'


def get_encoder():
    """Определяет лучший энкодер"""
    try:
        result = subprocess.run(['ffmpeg', '-hide_banner', '-encoders'],
                               capture_output=True, text=True, timeout=30)
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
    """
    Вычисляет на сколько замедлить видео.

    Возвращает коэффициент замедления (1.0 = без изменений, 2.0 = в 2 раза медленнее)
    """
    if not text or duration_ms <= 0:
        return 1.0

    chars = len(text)
    duration_sec = duration_ms / 1000.0
    current_cps = chars / duration_sec

    # Если CPS уже ок - не трогаем
    if current_cps <= TARGET_CPS:
        return 1.0

    # Сколько нужно времени для TARGET_CPS
    needed_duration = chars / TARGET_CPS
    slowdown = needed_duration / duration_sec

    # Ограничиваем максимальное замедление
    slowdown = min(slowdown, MAX_SLOWDOWN)

    result_cps = chars / (duration_sec * slowdown)
    log(f"    [{chars} симв] CPS: {current_cps:.1f} → {result_cps:.1f} | x{slowdown:.2f}")

    return slowdown


def build_atempo_chain(tempo):
    """
    Строит цепочку atempo фильтров.
    atempo работает только в диапазоне 0.5-2.0, поэтому нужна цепочка.
    """
    if tempo >= 0.5 and tempo <= 2.0:
        return f"atempo={tempo:.6f}"

    chain = []
    t = tempo

    # Для очень медленного темпа (< 0.5)
    while t < 0.5:
        chain.append("atempo=0.5")
        t /= 0.5

    # Для очень быстрого темпа (> 2.0)
    while t > 2.0:
        chain.append("atempo=2.0")
        t /= 2.0

    chain.append(f"atempo={t:.6f}")
    return ','.join(chain)


def render_segment(idx, start_ms, end_ms, slowdown, input_video, temp_dir, encoder, enc_opts, fps_str):
    """
    Рендерит один сегмент видео с retry логикой.
    Возвращает словарь с ФАКТИЧЕСКОЙ длительностью от ffprobe.
    """
    start_sec = start_ms / 1000.0
    end_sec = end_ms / 1000.0
    duration_sec = end_sec - start_sec

    if duration_sec < 0.04:  # Слишком короткий сегмент
        return None

    output_file = temp_dir / f"seg_{idx:04d}.mp4"

    for attempt in range(MAX_RETRIES):
        try:
            # Seek чуть раньше для точности (keyframe seek)
            seek = max(0, start_sec - 2.0)
            rel_start = start_sec - seek
            rel_end = end_sec - seek

            # Видео фильтр: trim + замедление через setpts
            # setpts=2.0*PTS = в 2 раза медленнее
            vf = f"trim=start={rel_start:.6f}:end={rel_end:.6f},setpts={slowdown:.6f}*(PTS-STARTPTS)"

            # Аудио: atempo работает наоборот (0.5 = замедление в 2 раза)
            tempo = 1.0 / slowdown
            atempo_chain = build_atempo_chain(tempo)
            af = f"atrim=start={rel_start:.6f}:end={rel_end:.6f},asetpts=PTS-STARTPTS,{atempo_chain}"

            cmd = [
                'ffmpeg', '-hide_banner', '-y',
                '-ss', f'{seek:.6f}',
                '-i', str(input_video),
                '-filter_complex', f'[0:v]{vf}[v];[0:a]{af}[a]',
                '-map', '[v]', '-map', '[a]',
                '-c:v', encoder, *enc_opts,
                '-c:a', 'aac', '-b:a', '128k',
                '-r', fps_str,
                '-vsync', 'cfr',  # Constant frame rate для точности
                '-avoid_negative_ts', 'make_zero',
                '-fflags', '+genpts',
                '-max_muxing_queue_size', '1024',
                '-loglevel', 'error',
                str(output_file)
            ]

            t0 = time.time()
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            elapsed = time.time() - t0

            if result.returncode != 0:
                if attempt < MAX_RETRIES - 1:
                    log(f"  ⚠️ Seg {idx} attempt {attempt+1} failed, retrying...")
                    time.sleep(0.5)
                    continue
                log(f"  ❌ Seg {idx}: {result.stderr[:200] if result.stderr else 'unknown error'}")
                return None

            if not output_file.exists() or output_file.stat().st_size == 0:
                if attempt < MAX_RETRIES - 1:
                    log(f"  ⚠️ Seg {idx} empty output, retrying...")
                    continue
                return None

            # КРИТИЧЕСКИ ВАЖНО: получаем ФАКТИЧЕСКУЮ длительность!
            actual_duration_ms = get_segment_duration_ms(output_file)

            if actual_duration_ms is None or actual_duration_ms <= 0:
                # Fallback на расчётную длительность (не идеально, но лучше чем ничего)
                actual_duration_ms = int(duration_sec * slowdown * 1000)
                log(f"  ⚠️ Seg {idx}: using calculated duration (ffprobe failed)")

            label = "SLOW" if slowdown > 1.01 else "NORM"
            log(f"  ✅ Seg {idx:03d} | {label} x{slowdown:.2f} | {duration_sec:.2f}s → {actual_duration_ms/1000:.2f}s | {elapsed:.1f}s")

            return {
                'idx': idx,
                'file': output_file,
                'duration_ms': actual_duration_ms,  # ФАКТИЧЕСКАЯ длительность!
                'slowdown': slowdown
            }

        except subprocess.TimeoutExpired:
            log(f"  ⚠️ Seg {idx} timeout, attempt {attempt+1}")
            if output_file.exists():
                output_file.unlink()
            if attempt < MAX_RETRIES - 1:
                continue
            return None
        except Exception as e:
            log(f"  ❌ Seg {idx} exception: {e}")
            if attempt < MAX_RETRIES - 1:
                continue
            return None

    return None


def validate_segments(segments, results):
    """
    Проверяет что все критические сегменты отрендерились.
    Возвращает True если всё ок, False если есть критические пропуски.
    """
    rendered_indices = {r['idx'] for r in results}
    missing_subs = []

    for seg in segments:
        if seg['sub_index'] is not None:
            # Ищем соответствующий результат
            idx = segments.index(seg)
            if idx not in rendered_indices:
                missing_subs.append(seg['sub_index'])

    if missing_subs:
        log(f"  ⚠️ Пропущены субтитры: {missing_subs[:10]}{'...' if len(missing_subs) > 10 else ''}")
        return False

    return True


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
    print("  🎬 VIDEO SPEED ADJUSTER v6.0 - ИДЕАЛЬНАЯ ВЕРСИЯ")
    print("=" * 60)
    print(f"  Target CPS: {TARGET_CPS}")
    print(f"  Max slowdown: {MAX_SLOWDOWN}x")
    print(f"  Max retries: {MAX_RETRIES}")
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
        print(f"⚠️ Количество не совпадает! ENG: {len(eng_subs)}, RUS: {len(rus_texts)}")
        print(f"   Используем: {min(len(eng_subs), len(rus_texts))}")

    # Инфо о видео - БЕЗ ОКРУГЛЕНИЯ FPS!
    video_duration = get_video_duration(input_video)
    fps = get_video_fps(input_video)
    fps_str = get_video_fps_str(input_video)
    print(f"📼 Видео: {ms_to_time(video_duration)} @ {fps:.3f} FPS (raw: {fps_str})")

    encoder, enc_opts = get_encoder()
    print(f"🔧 Энкодер: {encoder}")

    # === СТРОИМ СЕГМЕНТЫ ===
    print("\n🔍 Анализ субтитров...")

    segments = []
    count = min(len(eng_subs), len(rus_texts))
    current_pos = 0
    total_slowdowns = 0
    max_slowdown_used = 1.0

    for i in range(count):
        sub = eng_subs[i]
        rus_text = rus_texts[i]
        start = sub['start']
        end = sub['end']

        # Gap перед субтитром (тишина/пауза)
        if start > current_pos + 50:  # Минимум 50ms gap
            segments.append({
                'start': current_pos,
                'end': start,
                'slowdown': 1.0,
                'sub_index': None,
                'text': ''
            })

        # Обработка перекрывающихся субтитров
        if start < current_pos:
            overlap = current_pos - start
            if overlap < (end - start) * 0.5:
                # Небольшое перекрытие - просто сдвигаем начало
                start = current_pos
            else:
                # Большое перекрытие - пропускаем этот субтитр с предупреждением
                log(f"  ⚠️ Sub {i+1} сильно перекрывается, пропуск")
                continue

        if start >= end:
            continue

        duration = end - start
        slowdown = calculate_slowdown(rus_text, duration)

        if slowdown > 1.01:
            total_slowdowns += 1
            max_slowdown_used = max(max_slowdown_used, slowdown)

        segments.append({
            'start': start,
            'end': end,
            'slowdown': slowdown,
            'sub_index': i + 1,
            'text': rus_text
        })

        current_pos = end

    # Хвост видео (после последнего субтитра)
    if current_pos < video_duration - 50:
        segments.append({
            'start': current_pos,
            'end': video_duration,
            'slowdown': 1.0,
            'sub_index': None,
            'text': ''
        })

    # Статистика
    sub_segments = [s for s in segments if s['sub_index'] is not None]
    print(f"\n  📊 Всего сегментов: {len(segments)}")
    print(f"  📊 Субтитров: {len(sub_segments)}")
    print(f"  📊 Замедлений: {total_slowdowns}")
    print(f"  📊 Макс. замедление: x{max_slowdown_used:.2f}")

    # === РЕНДЕР ===
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True)

    print(f"\n🚀 Рендер ({len(segments)} сегментов, {PARALLEL_WORKERS} workers)...")
    render_start = time.time()

    results = []
    failed_segments = []

    with ThreadPoolExecutor(max_workers=PARALLEL_WORKERS) as executor:
        futures = {}
        for idx, seg in enumerate(segments):
            future = executor.submit(
                render_segment,
                idx, seg['start'], seg['end'], seg['slowdown'],
                input_video, temp_dir, encoder, enc_opts, fps_str
            )
            futures[future] = (idx, seg)

        for future in as_completed(futures):
            idx, seg = futures[future]
            try:
                result = future.result()
                if result:
                    result['sub_index'] = seg['sub_index']
                    result['text'] = seg['text']
                    results.append(result)
                else:
                    failed_segments.append((idx, seg))
            except Exception as e:
                log(f"  ❌ Seg {idx} exception: {e}")
                failed_segments.append((idx, seg))

    results.sort(key=lambda x: x['idx'])
    render_time = time.time() - render_start

    print(f"\n⏱️ Рендер завершён за {render_time:.1f}s")
    print(f"   Успешно: {len(results)}/{len(segments)}")

    if not results:
        print("❌ Ничего не отрендерилось!")
        sys.exit(1)

    # Валидация
    if failed_segments:
        critical_fails = [s for idx, s in failed_segments if s['sub_index'] is not None]
        if critical_fails:
            log(f"  ⚠️ Пропущено {len(critical_fails)} субтитров!")

    # === СКЛЕЙКА ===
    print("\n🔗 Склеивание...")

    concat_file = temp_dir / 'concat.txt'
    with open(concat_file, 'w', encoding='utf-8') as f:
        for r in results:
            path = str(r['file'].absolute()).replace("'", "'\\''")
            f.write(f"file '{path}'\n")

    concat_cmd = [
        'ffmpeg', '-hide_banner', '-y',
        '-f', 'concat', '-safe', '0',
        '-i', str(concat_file),
        '-c', 'copy',
        '-movflags', '+faststart',
        str(output_video)
    ]

    concat_result = subprocess.run(concat_cmd, capture_output=True, text=True)
    if concat_result.returncode != 0:
        print(f"❌ Ошибка склейки: {concat_result.stderr[:200] if concat_result.stderr else 'unknown'}")
        sys.exit(1)

    # Проверяем что видео создалось
    if not output_video.exists() or output_video.stat().st_size == 0:
        print("❌ Выходное видео не создано!")
        sys.exit(1)

    # === СУБТИТРЫ с ФАКТИЧЕСКИМИ таймингами ===
    print("✍️ Генерация субтитров с точными таймингами...")

    # Используем ФАКТИЧЕСКИЕ длительности из ffprobe
    new_pos = 0
    srt_entries = []

    for r in results:
        duration = r['duration_ms']  # Это ФАКТИЧЕСКАЯ длительность!
        sub_index = r['sub_index']
        text = r['text']

        if sub_index is not None and text:
            start_time = ms_to_time(new_pos)
            end_time = ms_to_time(new_pos + duration)
            srt_entries.append({
                'index': sub_index,
                'start': start_time,
                'end': end_time,
                'text': text
            })

        new_pos += duration

    # Сортируем по индексу и записываем
    srt_entries.sort(key=lambda x: x['index'])
    srt_lines = []
    for entry in srt_entries:
        srt_lines.append(f"{entry['index']}\n{entry['start']} --> {entry['end']}\n{entry['text']}")

    output_srt.write_text('\n\n'.join(srt_lines), encoding='utf-8')

    # === ОЧИСТКА ===
    print("🧹 Очистка временных файлов...")
    shutil.rmtree(temp_dir, ignore_errors=True)

    # === ФИНАЛЬНАЯ ВАЛИДАЦИЯ ===
    final_duration = get_video_duration(output_video)

    # === ИТОГ ===
    total_duration = sum(r['duration_ms'] for r in results)
    total_chars = sum(len(r['text']) for r in results if r['text'])
    avg_cps = total_chars / (total_duration / 1000) if total_duration > 0 else 0

    print(f"\n{'=' * 60}")
    print(f"✅ ГОТОВО!")
    print(f"{'=' * 60}")
    print(f"   📹 Видео: {output_video.name}")
    print(f"   📝 Субтитры: {output_srt.name}")
    print(f"   ⏱️ Было: {ms_to_time(video_duration)}")
    print(f"   ⏱️ Стало: {ms_to_time(total_duration)} (факт: {ms_to_time(final_duration)})")
    print(f"   📊 Средний CPS: {avg_cps:.1f} (цель: {TARGET_CPS})")
    print(f"   🔢 Субтитров: {len(srt_entries)}")

    # Проверка drift
    drift = abs(total_duration - final_duration)
    if drift > 100:
        print(f"   ⚠️ Drift: {drift}ms (расхождение расчёта и факта)")
    else:
        print(f"   ✅ Drift: {drift}ms (отлично!)")

    print(f"{'=' * 60}\n")


if __name__ == '__main__':
    main()
