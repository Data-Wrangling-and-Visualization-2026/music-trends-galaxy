from parsers import *
from storage_database import LyricDatabase
from pipeman import DataPipelineContext
import pandas as pd
import ast
import threading
import os
import numpy as np
import tqdm

 
def contains_artist(artists_str):
    """
    Parse the artists string and return True if any artist in the list
    (case‑insensitive) matches one of the target artists.
    Handles NaN/None values by returning False.
    """
    target_artists = ["linkin park", "bad omens", "radiohead", "slipknot", "bring me the horizon", "architecs", "evanescence", "korn", "limp bizkit", "asking alexandria", "panchiko", "afi", "amira elfeky", "violent vira", "cloudyfield", "muse", 'ally nicholas' ,'paramore', 'i see starts', 'tool', 'bones', 'sleep token', 'jutes', 'too close to touch', 'health', 'system of a down', 'alice in chains', 'deftones', 'audioslave', 'aurora', 'holding absence', 'my chemical romance', 'papa roach', 'the plot in you', 'skillet', 'spiritbox', 'thousand foot krutch', 'three days grace', 'while she sleeps', 'wilt', 'казённый унитаз', 'дора']
    
    if pd.isna(artists_str):
        return False
    try:
        # Convert string like "['A', 'B']" to an actual list
        artist_list = ast.literal_eval(artists_str)
    except (SyntaxError, ValueError):
        # If parsing fails, treat as no match
        return False
 
    # Convert each artist to lower case for case‑insensitive comparison
    artist_list_lower = [a.lower() for a in artist_list]
 
    # Check if any target artist is present
    return any(target in artist_list_lower for target in target_artists)
 
 

# Глобальные счётчики
lock = threading.Lock()
total_succeed = 0
total_failed = 0
next_report_threshold = 30  # для вывода прогресса каждые 3000 строк
next_report_threshold_step = 30  # для вывода прогресса каждые 3000 строк

def process_lyrics(db_path: str, df: pd.DataFrame, thid: int):
    """Обрабатывает свою часть DataFrame, обновляет глобальные счётчики."""
    db = LyricDatabase(db_path)
    parser = ChainParser(parser_types=get_all_parsers())
    counter = 0
    succeed = 0
    failed = 0

    with lock:
        print(f'Thread #{thid} is started, df size={len(df)}')

    for i, row in df.iterrows():
        counter += 1
        track_id, track_name, artist_name = row['id'], row['name'], ast.literal_eval(row['artists'])[0]

        try:
            lyric_object = parser.get_lyrics(track_name=track_name, artist_name=artist_name)
            db.insert_or_update(track_id, lyric_object)
            succeed += 1
        except Exception:
            failed += 1

        # Каждые 1000 строк синхронизируем счётчики
        if counter % (next_report_threshold//3) == 0:
            _update_global_and_report(succeed, failed)
            succeed, failed = 0, 0

    # Остатки (менее 1000 строк)
    if succeed > 0 or failed > 0:
        _update_global_and_report(succeed, failed)

def _update_global_and_report(succeed_inc: int, failed_inc: int):
    """Безопасно увеличивает глобальные счётчики и выводит прогресс."""
    global total_succeed, total_failed, next_report_threshold
    with lock:
        total_succeed += succeed_inc
        total_failed += failed_inc
        total_processed = total_succeed + total_failed

        if total_processed >= next_report_threshold:
            print(f"Обработано {total_processed} строк (успешно: {total_succeed}, ошибок: {total_failed})")
            while next_report_threshold <= total_processed:
                next_report_threshold += next_report_threshold_step 


def main(cxt: DataPipelineContext) -> None:
    db_path = cxt.get_file_path('lyrics.db')

    df = pd.read_csv(cxt.get_previous_stage_output_file_path())
    df = df.sample(frac=1, random_state=898).reset_index(drop=True)

    print('Filtering processed entries')

    df = df[df['id'].apply(lambda x: not db.exists(x))]
    # df = df[df['artists'].apply(contains_artist)]

    # Количество потоков (по числу CPU)
    num_threads = os.cpu_count() or 6
    num_threads //= 2
    n = len(df)

    print('Loaded df, rows:', len(df), ',\tCPUs:', num_threads)

    if n == 0:
        print("DataFrame пуст, нечего обрабатывать")
        return

    # Разбиваем DataFrame на примерно равные части (последняя может быть меньше)
    chunk_size = n // num_threads
    remainder = n % num_threads
    df_parts = []
    start = 0
    for i in range(num_threads):
        end = start + chunk_size + (1 if i < remainder else 0)
        df_parts.append(df.iloc[start:end])
        start = end

    print('Starting threads')

    # Запускаем потоки
    threads = []
    for i, part in enumerate(df_parts):
        if part.empty:
            continue
        t = threading.Thread(target=process_lyrics, args=(db_path, part, i))
        t.start()
        threads.append(t)

    # Ждём завершения
    for t in threads:
        t.join()

    # Финальный отчёт
    with lock:
        total = total_succeed + total_failed
        print(f"\nОбработка завершена. Всего строк: {total}, успешно: {total_succeed}, ошибок: {total_failed}")