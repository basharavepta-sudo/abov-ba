#!/usr/bin/env python3
"""
Video Speed Adjuster v6.0 - MoviePy Edition

Замедляет видео на основе CPS (символов в секунду) для комфортной озвучки.
Использует MoviePy для обработки видео с поддержкой GPU (NVIDIA NVENC).

Логика:
1. Парсим SRT субтитры (получаем начало/конец каждого субтитра)
2. Парсим русский перевод (текст для расчёта CPS)
3. Для каждого субтитра вычисляем CPS = символы / длительность
4. Если CPS > порога - замедляем этот сегмент видео
5. Склеиваем все сегменты
6. Генерируем новые субтитры с новыми таймкодами

Требования:
    pip install moviepy numpy

Автор: Claude AI
"""

import re
import os
import sys
import gc
import tempfile
import shutil
import subprocess
from pathlib import Path
from typing import List, Dict, Optional

# === НАСТРОЙКИ ===
TARGET_CPS = 16.0        # Целевой CPS после замедления
SOFT_THRESHOLD = 16.0    # Ниже этого - не трогаем
HARD_THRESHOLD = 20.0    # Выше этого - полное замедление
MAX_SLOWDOWN = 3.0       # Максимальное замедления (3x = в 3 раза медленнее)
USE_GPU = True           # Использовать GPU (NVIDIA NVENC) если доступно
BATCH_SIZE = 20          # Количество сегментов в одном батче (для экономии памяти)


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
    """
    Парсит SRT файл.
    Возвращает список: [{'start': float, 'end': float, 'text': str}, ...]
    """
    content = content.replace('\r\n', '\n').replace('\r', '\n')
    blocks = re.split(r'\n\s*\n', content.strip())
    subs = []

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

        parts = timecode_line.split('-->')
        if len(parts) != 2:
            continue

        start = time_to_seconds(parts[0])
        end = time_to_seconds(parts[1])

        # Собираем текст субтитра
        text = ' '.join(line.strip() for line in lines[text_start:] if line.strip())
        # Убираем теги HTML, ASS, и текст в скобках
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'\{[^}]+\}', '', text)
        text = re.sub(r'\([^)]*\)', '', text)
        text = text.strip()

        if text and end > start:
            subs.append({'start': start, 'end': end, 'text': text})

    return subs


def parse_numbered_text(content: str) -> List[str]:
    """
    Парсит нумерованный текстовый файл.
    Формат: '1. текст' или '1) текст' или '1: текст'
    """
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
    """
    Вычисляет коэффициент замедления на основе CPS.

    CPS <= SOFT_THRESHOLD: без замедления (1.0)
    CPS в диапазоне SOFT-HARD: плавное нарастание
    CPS >= HARD_THRESHOLD: полное замедление до TARGET_CPS

    Возвращает: коэффициент замедления (1.0 = без изменений, 2.0 = в 2 раза медленнее)
    """
    if not text or duration_sec <= 0:
        return 1.0

    chars = len(text)
    current_cps = chars / duration_sec

    # Ниже мягкого порога - не трогаем
    if current_cps <= SOFT_THRESHOLD:
        return 1.0

    # Полное замедление для достижения TARGET_CPS
    full_slowdown = current_cps / TARGET_CPS

    # Плавный переход между SOFT и HARD threshold
    threshold_range = HARD_THRESHOLD - SOFT_THRESHOLD
    if threshold_range > 0 and current_cps < HARD_THRESHOLD:
        # Линейная интерполяция: 0 при SOFT, 1 при HARD
        blend = (current_cps - SOFT_THRESHOLD) / threshold_range
        # Smoothstep для более плавного перехода: 3x² - 2x³
        blend = blend * blend * (3 - 2 * blend)
        slowdown = 1.0 + (full_slowdown - 1.0) * blend
    else:
        slowdown = full_slowdown

    # Ограничиваем максимальное замедление
    slowdown = min(slowdown, MAX_SLOWDOWN)

    return slowdown


def check_nvidia_gpu() -> tuple[bool, str]:
    """
    Проверяет доступность NVIDIA GPU для NVENC.
    Возвращает (доступен, кодек)
    """
    try:
        # Проверяем наличие NVIDIA GPU через nvidia-smi
        nvidia_check = subprocess.run(
            ['nvidia-smi', '--query-gpu=name', '--format=csv,noheader'],
            capture_output=True, text=True, timeout=5
        )
        if nvidia_check.returncode != 0:
            return False, 'libx264'

        gpu_name = nvidia_check.stdout.strip()
        print(f"   Обнаружена GPU: {gpu_name}")

        # Проверяем поддержку h264_nvenc в ffmpeg
        ffmpeg_check = subprocess.run(
            ['ffmpeg', '-hide_banner', '-encoders'],
            capture_output=True, text=True, timeout=10
        )
        if 'h264_nvenc' in ffmpeg_check.stdout:
            print("   h264_nvenc найден в ffmpeg, тестируем...")
            # Тестируем кодек
            test_cmd = [
                'ffmpeg', '-hide_banner', '-y',
                '-f', 'lavfi', '-i', 'color=black:s=64x64:d=0.1',
                '-c:v', 'h264_nvenc', '-f', 'null', '-'
            ]
            test_result = subprocess.run(test_cmd, capture_output=True, text=True, timeout=10)
            if test_result.returncode == 0:
                return True, 'h264_nvenc'
            else:
                # Показываем почему не работает
                err = test_result.stderr[:200] if test_result.stderr else "unknown error"
                print(f"   NVENC тест не прошёл: {err}")
        else:
            print("   h264_nvenc не найден в ffmpeg (нужна сборка с NVENC)")

        return False, 'libx264'
    except Exception as e:
        print(f"   Ошибка проверки GPU: {e}")
        return False, 'libx264'


def get_ffmpeg_params(encoder: str) -> List[str]:
    """Возвращает параметры ffmpeg для кодирования"""
    if encoder == 'h264_nvenc':
        return [
            '-c:v', 'h264_nvenc',
            '-preset', 'p4',       # Баланс скорость/качество (p1-p7)
            '-rc', 'vbr',          # Variable bitrate
            '-cq', '20',           # Качество (ниже = лучше, 0-51)
            '-b:v', '0',           # Авто битрейт
            '-pix_fmt', 'yuv420p',
        ]
    else:
        return [
            '-c:v', 'libx264',
            '-preset', 'fast',
            '-crf', '20',
            '-pix_fmt', 'yuv420p',
        ]


def get_moviepy_version():
    """Определяет версию MoviePy и возвращает класс VideoFileClip"""
    try:
        from moviepy import VideoFileClip  # MoviePy 2.x
        return VideoFileClip, 2
    except ImportError:
        from moviepy.editor import VideoFileClip  # MoviePy 1.x
        return VideoFileClip, 1


def subclip_compat(video, start, end, version):
    """Совместимая функция для вырезки сегмента"""
    if version >= 2:
        return video.subclipped(start, end)
    else:
        return video.subclip(start, end)


def speedx_compat(clip, factor, version):
    """Совместимая функция для изменения скорости"""
    if version >= 2:
        return clip.with_speed_scaled(factor)
    else:
        from moviepy.video.fx.speedx import speedx
        return speedx(clip, factor)


def process_segment_batch(
    video_path: str,
    segments: List[Dict],
    temp_dir: Path,
    batch_idx: int,
    encoder: str,
    fps: float
) -> List[Dict]:
    """
    Обрабатывает батч сегментов и сохраняет во временные файлы.
    Возвращает информацию о сохранённых файлах.
    """
    VideoFileClip, moviepy_version = get_moviepy_version()

    results = []
    video = None

    try:
        video = VideoFileClip(video_path)

        for idx, seg in enumerate(segments):
            global_idx = batch_idx * BATCH_SIZE + idx
            start = seg['start']
            end = seg['end']
            slowdown = seg['slowdown']
            duration = end - start

            if duration < 0.04:  # Пропускаем слишком короткие
                continue

            try:
                # Вырезаем сегмент (совместимо с 1.x и 2.x)
                clip = subclip_compat(video, start, end, moviepy_version)

                # Применяем замедление если нужно
                # factor < 1 = замедление
                if slowdown > 1.01:
                    speed_factor = 1.0 / slowdown
                    clip = speedx_compat(clip, speed_factor, moviepy_version)
                    new_duration = duration * slowdown
                else:
                    new_duration = duration

                # Сохраняем сегмент
                output_file = temp_dir / f"seg_{global_idx:05d}.mp4"

                # Параметры ffmpeg
                ffmpeg_params = get_ffmpeg_params(encoder)
                ffmpeg_params.extend(['-c:a', 'aac', '-b:a', '128k'])

                clip.write_videofile(
                    str(output_file),
                    fps=fps,
                    codec=encoder if encoder == 'h264_nvenc' else 'libx264',
                    audio_codec='aac',
                    ffmpeg_params=ffmpeg_params,
                    threads=4,
                    logger=None,
                    verbose=False
                )

                clip.close()

                results.append({
                    'idx': global_idx,
                    'file': output_file,
                    'duration': new_duration,
                    'sub_index': seg['sub_index'],
                    'text': seg['text']
                })

                label = "SLOW" if slowdown > 1.01 else "NORM"
                print(f"   ✅ Seg {global_idx+1:03d} | {label} x{slowdown:.2f} | {duration:.1f}s → {new_duration:.1f}s")

            except Exception as e:
                print(f"   ❌ Seg {global_idx+1}: {str(e)[:50]}")
                continue

    except Exception as e:
        print(f"   ❌ Ошибка батча {batch_idx}: {e}")

    finally:
        if video:
            video.close()
        gc.collect()

    return results


def concatenate_with_ffmpeg(segment_files: List[Path], output_path: Path, encoder: str):
    """Склеивает сегменты через ffmpeg concat demuxer"""
    # Создаём файл списка
    concat_list = output_path.parent / 'concat_list.txt'

    with open(concat_list, 'w', encoding='utf-8') as f:
        for seg_file in segment_files:
            # Экранируем путь для ffmpeg
            escaped_path = str(seg_file.absolute()).replace("'", "'\\''")
            f.write(f"file '{escaped_path}'\n")

    # Склеиваем
    cmd = [
        'ffmpeg', '-hide_banner', '-y',
        '-f', 'concat', '-safe', '0',
        '-i', str(concat_list),
        '-c', 'copy',  # Просто копируем без перекодирования
        '-movflags', '+faststart',
        str(output_path)
    ]

    print(f"   Выполняем: ffmpeg concat...")
    result = subprocess.run(cmd, capture_output=True, text=True)

    # Удаляем список
    concat_list.unlink(missing_ok=True)

    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg concat failed: {result.stderr[:200]}")


def process_video(
    input_video: Path,
    eng_srt: Path,
    rus_translation: Path,
    output_video: Path,
    output_srt: Path
):
    """
    Основная функция обработки видео.

    1. Загружает видео через MoviePy
    2. Парсит субтитры
    3. Нарезает видео на сегменты
    4. Применяет замедление где нужно
    5. Склеивает и сохраняет
    """
    # Импорты MoviePy (поддержка 1.x и 2.x)
    try:
        VideoFileClip, MOVIEPY_VERSION = get_moviepy_version()
    except ImportError:
        print("=" * 60)
        print("❌ MoviePy не установлен!")
        print("=" * 60)
        print("\nУстановите командой:")
        print("   pip install moviepy")
        print("\nТакже рекомендуется:")
        print("   pip install numpy pillow")
        print("=" * 60)
        sys.exit(1)

    print("\n" + "=" * 60)
    print("  🎬 VIDEO SPEED ADJUSTER v6.0 (MoviePy Edition)")
    print("=" * 60)
    print(f"  MoviePy version: {MOVIEPY_VERSION}.x")
    print(f"  Target CPS: {TARGET_CPS}")
    print(f"  Soft threshold: {SOFT_THRESHOLD}")
    print(f"  Hard threshold: {HARD_THRESHOLD}")
    print(f"  Max slowdown: {MAX_SLOWDOWN}x")
    print("=" * 60)

    # === ПРОВЕРЯЕМ GPU ===
    print("\n🔍 Проверка GPU...")
    if USE_GPU:
        gpu_available, encoder = check_nvidia_gpu()
        if gpu_available:
            print("   ✅ GPU NVENC будет использоваться для кодирования")
        else:
            print("   ⚠️ GPU недоступен, используем CPU (libx264)")
    else:
        encoder = 'libx264'
        print("   GPU отключён в настройках, используем CPU")

    # === ЧИТАЕМ СУБТИТРЫ ===
    print("\n📝 Загрузка субтитров...")

    eng_content = read_file_with_encoding(eng_srt)
    if not eng_content:
        print(f"❌ Не удалось прочитать SRT: {eng_srt}")
        sys.exit(1)

    eng_subs = parse_srt(eng_content)
    if not eng_subs:
        print("❌ SRT файл пустой или повреждён!")
        sys.exit(1)
    print(f"   Английских субтитров: {len(eng_subs)}")

    # === ЧИТАЕМ ПЕРЕВОД ===
    rus_content = read_file_with_encoding(rus_translation)
    if not rus_content:
        print(f"❌ Не удалось прочитать перевод: {rus_translation}")
        sys.exit(1)

    # Определяем формат по расширению
    if rus_translation.suffix.lower() == '.srt':
        rus_texts = [s['text'] for s in parse_srt(rus_content)]
    else:
        rus_texts = parse_numbered_text(rus_content)

    if not rus_texts:
        print(f"❌ Перевод пустой: {rus_translation}")
        sys.exit(1)
    print(f"   Русских текстов: {len(rus_texts)}")

    if len(eng_subs) != len(rus_texts):
        print(f"⚠️  Количество не совпадает! Используем: {min(len(eng_subs), len(rus_texts))}")

    # === ПОЛУЧАЕМ ИНФО О ВИДЕО ===
    print("\n📼 Анализ видео...")
    video = VideoFileClip(str(input_video))
    video_duration = video.duration
    video_fps = video.fps
    video_size = video.size
    video.close()  # Закрываем сразу, чтобы не держать в памяти

    print(f"   Длительность: {seconds_to_srt_time(video_duration)}")
    print(f"   Разрешение: {video_size[0]}x{video_size[1]}")
    print(f"   FPS: {video_fps}")

    # === СТРОИМ СЕГМЕНТЫ ===
    print("\n🔍 Анализ и построение сегментов...")

    segments = []  # (start, end, slowdown, sub_index, text)
    count = min(len(eng_subs), len(rus_texts))
    current_pos = 0.0
    total_slow = 0

    for i in range(count):
        sub = eng_subs[i]
        rus_text = rus_texts[i]
        start = sub['start']
        end = sub['end']

        # Gap перед субтитром (без замедления)
        if start > current_pos + 0.05:  # минимум 50мс gap
            segments.append({
                'start': current_pos,
                'end': start,
                'slowdown': 1.0,
                'sub_index': None,
                'text': ''
            })

        # Корректируем начало если перекрытие
        if start < current_pos:
            start = current_pos

        if start >= end:
            print(f"   ⚠️ Субтитр #{i+1} пропущен (перекрытие)")
            continue

        # Вычисляем замедление
        duration = end - start
        slowdown = calculate_slowdown(rus_text, duration)

        if slowdown > 1.01:
            total_slow += 1
            orig_cps = len(rus_text) / duration
            new_cps = len(rus_text) / (duration * slowdown)
            print(f"   #{i+1:03d} [{len(rus_text)} sym] CPS: {orig_cps:.1f} → {new_cps:.1f} (x{slowdown:.2f})")

        segments.append({
            'start': start,
            'end': end,
            'slowdown': slowdown,
            'sub_index': i + 1,
            'text': rus_text
        })

        current_pos = end

    # Хвост видео
    if current_pos < video_duration - 0.05:
        segments.append({
            'start': current_pos,
            'end': video_duration,
            'slowdown': 1.0,
            'sub_index': None,
            'text': ''
        })

    print(f"\n   📊 Всего сегментов: {len(segments)}")
    print(f"   📊 Требуют замедления: {total_slow}")

    # === СОЗДАЁМ ВРЕМЕННУЮ ДИРЕКТОРИЮ ===
    temp_dir = Path(tempfile.mkdtemp(prefix='video_speed_'))
    print(f"\n📁 Временная директория: {temp_dir}")

    try:
        # === ОБРАБАТЫВАЕМ СЕГМЕНТЫ БАТЧАМИ ===
        print(f"\n🚀 Обработка сегментов (батчи по {BATCH_SIZE})...")

        all_results = []
        num_batches = (len(segments) + BATCH_SIZE - 1) // BATCH_SIZE

        for batch_idx in range(num_batches):
            start_idx = batch_idx * BATCH_SIZE
            end_idx = min(start_idx + BATCH_SIZE, len(segments))
            batch_segments = segments[start_idx:end_idx]

            print(f"\n   📦 Батч {batch_idx + 1}/{num_batches} (сегменты {start_idx + 1}-{end_idx})")

            batch_results = process_segment_batch(
                video_path=str(input_video),
                segments=batch_segments,
                temp_dir=temp_dir,
                batch_idx=batch_idx,
                encoder=encoder,
                fps=video_fps
            )

            all_results.extend(batch_results)

            # Принудительная очистка памяти между батчами
            gc.collect()

        if not all_results:
            print("❌ Нет сегментов для обработки!")
            sys.exit(1)

        # Сортируем по индексу
        all_results.sort(key=lambda x: x['idx'])

        # === СКЛЕИВАЕМ ===
        print("\n🔗 Склеивание сегментов...")

        segment_files = [r['file'] for r in all_results]
        concatenate_with_ffmpeg(segment_files, output_video, encoder)

        if not output_video.exists() or output_video.stat().st_size == 0:
            print("❌ Выходное видео не создано!")
            sys.exit(1)

        # === ГЕНЕРИРУЕМ СУБТИТРЫ ===
        print("\n✍️ Генерация субтитров...")

        new_timings = []
        current_output_time = 0.0

        for r in all_results:
            if r['sub_index'] is not None and r['text']:
                new_timings.append({
                    'index': r['sub_index'],
                    'start': current_output_time,
                    'end': current_output_time + r['duration'],
                    'text': r['text']
                })
            current_output_time += r['duration']

        srt_lines = []
        for timing in new_timings:
            start_time = seconds_to_srt_time(timing['start'])
            end_time = seconds_to_srt_time(timing['end'])
            srt_lines.append(f"{timing['index']}\n{start_time} --> {end_time}\n{timing['text']}")

        output_srt.write_text('\n\n'.join(srt_lines), encoding='utf-8')
        print(f"   Субтитров сохранено: {len(srt_lines)}")

        # === ИТОГИ ===
        total_chars = sum(len(t['text']) for t in new_timings)
        final_duration = current_output_time
        avg_cps = total_chars / final_duration if final_duration > 0 else 0

        print(f"\n{'=' * 60}")
        print("✅ ГОТОВО!")
        print(f"   📹 Видео: {output_video}")
        print(f"   📝 Субтитры: {output_srt}")
        print(f"   ⏱️  Было: {seconds_to_srt_time(video_duration)}")
        print(f"   ⏱️  Стало: {seconds_to_srt_time(final_duration)}")
        print(f"   📊 Средний CPS: {avg_cps:.1f} (цель: {TARGET_CPS})")
        print(f"   🔧 Энкодер: {encoder}")
        print(f"{'=' * 60}\n")

    finally:
        # === ОЧИСТКА ===
        print("🧹 Очистка временных файлов...")
        shutil.rmtree(temp_dir, ignore_errors=True)
        gc.collect()


def main():
    """Точка входа"""
    script_dir = Path(__file__).parent.resolve()

    # Пути из переменных окружения или дефолтные
    input_video = Path(os.environ.get('VST_VIDEO_INPUT', script_dir / 'input.mp4'))
    eng_srt = Path(os.environ.get('VST_SRT_INPUT', script_dir / 'output.srt'))

    # Перевод: сначала env, потом russian.srt, потом Penis.txt
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

    # Проверки
    if not input_video.exists():
        print(f"❌ Видео не найдено: {input_video}")
        print(f"\nОжидаемые файлы:")
        print(f"   Видео: {input_video}")
        print(f"   SRT: {eng_srt}")
        print(f"   Перевод: {rus_translation}")
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
    print(f"   Выход: {output_video}")
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
