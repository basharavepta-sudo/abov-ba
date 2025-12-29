#!/usr/bin/env python3
"""
Parakeet TDT 0.6B v2 - State-of-the-art English ASR
V4: Fixed duplicate words, minimum duration, orphan word merging
"""

import sys
import os
import subprocess
import warnings
import tempfile
import argparse
from pathlib import Path

# === TEMP FIX ===
SCRIPT_DIR = Path(__file__).parent.absolute()
CUSTOM_TEMP = SCRIPT_DIR / "_nemo_temp"
CUSTOM_TEMP.mkdir(exist_ok=True)

os.environ["TEMP"] = str(CUSTOM_TEMP)
os.environ["TMP"] = str(CUSTOM_TEMP)
os.environ["TMPDIR"] = str(CUSTOM_TEMP)
tempfile.tempdir = str(CUSTOM_TEMP)

warnings.filterwarnings("ignore")
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

import torch
import numpy as np
import soundfile as sf
import nemo.collections.asr as nemo_asr


def format_time(seconds):
    seconds = max(0, seconds)
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def cleanup_temp():
    if CUSTOM_TEMP.exists():
        for f in CUSTOM_TEMP.glob("*"):
            try:
                if f.is_file():
                    f.unlink()
                elif f.is_dir():
                    import shutil
                    shutil.rmtree(f, ignore_errors=True)
            except:
                pass


def normalize_word(word):
    """Нормализуем слово для сравнения"""
    return word.lower().strip('.,!?;:"\'-…')


def is_sentence_end(word):
    word = word.strip()
    return word.endswith('.') or word.endswith('!') or word.endswith('?')


def aggressive_dedup(words, time_window=0.5):
    """
    Агрессивная дедупликация: ищем повторяющиеся последовательности слов
    на границах чанков и удаляем дубликаты.
    """
    if len(words) < 2:
        return words

    # Сортируем по времени
    words = sorted(words, key=lambda w: w['start'])

    # Ищем дубликаты - одинаковые слова в близком временном окне
    result = []
    i = 0

    while i < len(words):
        current = words[i]

        # Смотрим вперёд - есть ли дубликаты этого слова
        duplicates = [current]
        j = i + 1

        while j < len(words) and words[j]['start'] - current['start'] < time_window:
            if normalize_word(words[j]['word']) == normalize_word(current['word']):
                duplicates.append(words[j])
            j += 1

        if len(duplicates) > 1:
            # Есть дубликаты - берём тот что посередине по времени
            duplicates.sort(key=lambda w: w['start'])
            best = duplicates[len(duplicates) // 2]
            result.append(best)

            # Пропускаем все дубликаты
            skip_until = duplicates[-1]['start'] + 0.1
            i += 1
            while i < len(words) and words[i]['start'] < skip_until:
                if normalize_word(words[i]['word']) != normalize_word(current['word']):
                    # Это другое слово - не пропускаем
                    break
                i += 1
        else:
            result.append(current)
            i += 1

    return result


def remove_sequence_duplicates(words, seq_len=3, time_window=1.0):
    """
    Удаляем дублирующиеся последовательности слов.
    Например: "a habit" + "a habit of" -> оставляем только "a habit of"
    """
    if len(words) < seq_len * 2:
        return words

    words = sorted(words, key=lambda w: w['start'])

    # Ищем повторяющиеся последовательности
    to_remove = set()

    for i in range(len(words) - seq_len):
        seq1 = [normalize_word(words[i + k]['word']) for k in range(seq_len)]

        for j in range(i + 1, min(i + 20, len(words) - seq_len + 1)):
            # Проверяем временное окно
            if words[j]['start'] - words[i]['start'] > time_window:
                break

            seq2 = [normalize_word(words[j + k]['word']) for k in range(seq_len)]

            if seq1 == seq2:
                # Нашли дубликат последовательности
                # Удаляем первую (она из предыдущего чанка, менее точная)
                for k in range(seq_len):
                    to_remove.add(i + k)

    return [w for idx, w in enumerate(words) if idx not in to_remove]


def create_subtitles(words, min_duration=1.2, max_duration=5.0, max_words=12):
    """
    Создаём субтитры с жёсткими правилами:
    - Минимальная длительность 1.2 сек (иначе присоединяем к следующему)
    - Разбиваем по точкам/вопросам
    - Длинные предложения режем по запятым или по количеству слов
    """
    if not words:
        return []

    subtitles = []
    buffer = []  # Слова текущего субтитра

    i = 0
    while i < len(words):
        w = words[i]
        buffer.append(w)

        # Определяем, нужно ли завершить субтитр
        should_end = False
        reason = None

        # 1. Конец предложения
        if is_sentence_end(w['word']):
            should_end = True
            reason = "sentence_end"

        # 2. Слишком много слов
        if len(buffer) >= max_words:
            should_end = True
            reason = "max_words"

        # 3. Слишком долго по времени
        if len(buffer) >= 2:
            duration = buffer[-1]['end'] - buffer[0]['start']
            if duration >= max_duration:
                should_end = True
                reason = "max_duration"

        # 4. Запятая + достаточно слов
        if w['word'].strip().endswith(',') and len(buffer) >= 5:
            should_end = True
            reason = "comma"

        if should_end and buffer:
            start_time = buffer[0]['start']
            end_time = buffer[-1]['end']
            duration = end_time - start_time
            text = ' '.join(x['word'] for x in buffer)

            # Проверяем минимальную длительность
            if duration < min_duration:
                # Слишком короткий - смотрим можно ли присоединить к следующим словам
                if i + 1 < len(words):
                    # Не завершаем, продолжаем собирать
                    i += 1
                    continue
                else:
                    # Это последние слова - присоединяем к предыдущему субтитру
                    if subtitles:
                        subtitles[-1]['text'] += ' ' + text
                        subtitles[-1]['end'] = end_time
                        buffer = []
                        i += 1
                        continue
                    else:
                        # Первый субтитр - расширяем время
                        end_time = start_time + min_duration

            subtitles.append({
                'start': start_time,
                'end': end_time,
                'text': text
            })
            buffer = []

        i += 1

    # Остаток
    if buffer:
        start_time = buffer[0]['start']
        end_time = buffer[-1]['end']
        duration = end_time - start_time
        text = ' '.join(x['word'] for x in buffer)

        if duration < min_duration:
            if subtitles:
                # Присоединяем к последнему
                subtitles[-1]['text'] += ' ' + text
                subtitles[-1]['end'] = max(subtitles[-1]['end'], end_time)
            else:
                end_time = start_time + min_duration
                subtitles.append({
                    'start': start_time,
                    'end': end_time,
                    'text': text
                })
        else:
            subtitles.append({
                'start': start_time,
                'end': end_time,
                'text': text
            })

    return subtitles


def fix_timings(subtitles, min_gap=0.08, min_duration=1.0):
    """
    Финальная корректировка таймингов:
    - Убираем перекрытия
    - Гарантируем минимальную длительность
    - Добавляем зазоры между субтитрами
    """
    if not subtitles:
        return subtitles

    fixed = []

    for i, sub in enumerate(subtitles):
        s = {
            'start': sub['start'],
            'end': sub['end'],
            'text': sub['text']
        }

        # Минимальная длительность
        if s['end'] - s['start'] < min_duration:
            s['end'] = s['start'] + min_duration

        # Убираем перекрытие с предыдущим
        if fixed:
            last = fixed[-1]
            if s['start'] < last['end'] + min_gap:
                # Вариант 1: сдвинуть текущий
                new_start = last['end'] + min_gap

                # Но не слишком сильно
                if new_start < s['end'] - 0.5:
                    s['start'] = new_start
                else:
                    # Вариант 2: обрезать предыдущий
                    last['end'] = s['start'] - min_gap
                    if last['end'] - last['start'] < 0.5:
                        last['end'] = last['start'] + 0.5
                        s['start'] = last['end'] + min_gap

        # Финальная проверка
        if s['end'] <= s['start']:
            s['end'] = s['start'] + min_duration

        fixed.append(s)

    return fixed


def main():
    parser = argparse.ArgumentParser(description="Parakeet TDT Transcription")
    parser.add_argument("--input", "-i", type=str, default="input.mp3", help="Input audio file")
    parser.add_argument("--output", "-o", type=str, default="output.srt", help="Output SRT file")
    args = parser.parse_args()

    # === SETTINGS ===
    INPUT_FILE = args.input
    OUTPUT_FILE = args.output
    CHUNK_SECONDS = 25
    OVERLAP_SECONDS = 2
    MIN_SUBTITLE_DURATION = 1.2  # Минимум секунд на субтитр
    MAX_SUBTITLE_DURATION = 5.0
    MAX_WORDS = 12

    print("=" * 60)
    print("  NVIDIA Parakeet TDT 0.6B v2")
    print("  V4: Fixed duplicates & timing")
    print("=" * 60)

    if not Path(INPUT_FILE).exists():
        print(f"\n❌ File not found: {INPUT_FILE}")
        return 1

    cleanup_temp()

    # Convert to WAV
    wav_path = SCRIPT_DIR / "_temp_audio.wav"
    print(f"\n⏳ Converting to WAV...")
    result = subprocess.run([
        "ffmpeg", "-y", "-i", INPUT_FILE,
        "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le",
        str(wav_path)
    ], capture_output=True, text=True)

    if result.returncode != 0:
        print(f"❌ FFmpeg error: {result.stderr}")
        return 1

    audio, sr = sf.read(str(wav_path))
    duration = len(audio) / sr
    print(f"✓ Duration: {duration:.1f} sec")

    # Load model
    print(f"\n⏳ Loading model...")
    model = nemo_asr.models.ASRModel.from_pretrained("nvidia/parakeet-tdt-0.6b-v2")
    model = model.cuda()
    model.eval()
    print(f"✓ GPU: {torch.cuda.get_device_name()}")

    # Chunks
    chunk_samples = int(CHUNK_SECONDS * sr)
    overlap_samples = int(OVERLAP_SECONDS * sr)
    step_samples = chunk_samples - overlap_samples

    chunk_positions = []
    pos = 0
    while pos < len(audio):
        end_pos = min(pos + chunk_samples, len(audio))
        chunk_positions.append((pos, end_pos))
        pos += step_samples
        if end_pos >= len(audio):
            break

    print(f"\n⏳ Transcribing {len(chunk_positions)} chunks...")

    all_words = []

    for i, (start_sample, end_sample) in enumerate(chunk_positions):
        chunk = audio[start_sample:end_sample]
        if len(chunk) < sr * 0.3:
            continue

        chunk_start_time = start_sample / sr
        chunk_path = CUSTOM_TEMP / f"chunk_{i}.wav"
        sf.write(str(chunk_path), chunk, sr)

        print(f"  [{i+1}/{len(chunk_positions)}] {chunk_start_time:.1f}s ... ", end="", flush=True)

        try:
            with torch.no_grad():
                hypotheses = model.transcribe(
                    [str(chunk_path)],
                    batch_size=1,
                    timestamps=True,
                    verbose=False,
                    num_workers=0
                )

            words_found = 0

            if hypotheses and len(hypotheses) > 0:
                hyp = hypotheses[0]
                word_list = None

                if hasattr(hyp, 'timestep') and hyp.timestep:
                    word_list = hyp.timestep.get('word', [])
                elif hasattr(hyp, 'timestamp') and hyp.timestamp:
                    word_list = hyp.timestamp.get('word', [])

                if word_list:
                    for w in word_list:
                        if isinstance(w, dict):
                            word = w.get('word', '')
                            start = float(w.get('start', 0))
                            end = float(w.get('end', start + 0.2))
                        elif isinstance(w, (list, tuple)) and len(w) >= 3:
                            word, start, end = str(w[0]), float(w[1]), float(w[2])
                        else:
                            continue

                        word = str(word).strip()
                        if not word:
                            continue

                        # Валидация
                        if end <= start:
                            end = start + 0.2
                        if end - start > 2.0:
                            end = start + 0.3

                        all_words.append({
                            'word': word,
                            'start': chunk_start_time + start,
                            'end': chunk_start_time + end,
                            'chunk': i  # Запоминаем из какого чанка
                        })
                        words_found += 1

                # Fallback
                if words_found == 0 and hasattr(hyp, 'text') and hyp.text:
                    text = hyp.text.strip()
                    words = text.split()
                    if words:
                        chunk_dur = len(chunk) / sr
                        word_dur = min(0.35, chunk_dur * 0.8 / len(words))
                        t = chunk_start_time + 0.1
                        for word in words:
                            all_words.append({
                                'word': word,
                                'start': t,
                                'end': t + word_dur,
                                'chunk': i
                            })
                            t += word_dur + 0.05
                            words_found += 1

            print(f"✓ {words_found}")
            del hypotheses

        except Exception as e:
            print(f"✗ {e}")

        torch.cuda.empty_cache()
        try:
            chunk_path.unlink()
        except:
            pass

    cleanup_temp()
    try:
        wav_path.unlink()
    except:
        pass

    if not all_words:
        print("\n❌ No words!")
        return 1

    # === ОБРАБОТКА ===
    print(f"\n⏳ Processing {len(all_words)} words...")

    # 1. Сортируем
    all_words = sorted(all_words, key=lambda w: w['start'])

    # 2. Агрессивная дедупликация одиночных слов
    all_words = aggressive_dedup(all_words, time_window=0.6)
    print(f"  After word dedup: {len(all_words)}")

    # 3. Удаляем дублирующиеся последовательности (2-3 слова)
    all_words = remove_sequence_duplicates(all_words, seq_len=2, time_window=1.5)
    all_words = remove_sequence_duplicates(all_words, seq_len=3, time_window=2.0)
    print(f"  After seq dedup: {len(all_words)}")

    # 4. Создаём субтитры
    subtitles = create_subtitles(
        all_words,
        min_duration=MIN_SUBTITLE_DURATION,
        max_duration=MAX_SUBTITLE_DURATION,
        max_words=MAX_WORDS
    )
    print(f"  Subtitles created: {len(subtitles)}")

    # 5. Финальная корректировка таймингов
    subtitles = fix_timings(subtitles, min_gap=0.08, min_duration=1.0)

    # Записываем SRT
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        for i, sub in enumerate(subtitles, 1):
            f.write(f"{i}\n")
            f.write(f"{format_time(sub['start'])} --> {format_time(sub['end'])}\n")
            f.write(f"{sub['text']}\n\n")

    # Статистика
    durations = [s['end'] - s['start'] for s in subtitles]

    print(f"\n{'=' * 60}")
    print(f"✓ {OUTPUT_FILE}")
    print(f"  {len(subtitles)} subtitles")
    print(f"  Duration: {min(durations):.1f}s - {max(durations):.1f}s (avg {sum(durations)/len(durations):.1f}s)")
    print(f"{'=' * 60}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
