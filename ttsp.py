# Импорт необходимых библиотек
import os  # Работа с файловой системой
import warnings  # Подавление предупреждений
warnings.filterwarnings('ignore', category=UserWarning, message='.*TypedStorage is deprecated.*')
import torch  # PyTorch для работы с нейросетями
import argparse  # Парсинг аргументов командной строки
import time  # Измерение времени выполнения
import asyncio  # Асинхронное программирование
import shutil  # Операции с файлами и директориями (копирование, удаление)
from pydub import AudioSegment  # Обработка аудио файлов
from silero import silero_tts  # Модель синтеза речи Silero
from telethon import TelegramClient  # Telegram клиент Telethon
import socks  # Поддержка SOCKS прокси
from dotenv import load_dotenv  # Загрузка переменных окружения из .env
from tqdm import tqdm  # Прогресс-бары
from concurrent.futures import ThreadPoolExecutor, as_completed  # Многопоточность
import threading  # Для thread-safe операций

# Загружаем переменные окружения из .env файла
load_dotenv()

# ============================================================
# НАСТРОЙКИ
# ============================================================

# Telegram API
API_ID = int(os.getenv('API_ID'))  # ID приложения Telegram API из .env
API_HASH = os.getenv('API_HASH')  # Хеш приложения Telegram API из .env
PROXY = (socks.SOCKS5, '127.0.0.1', 10808, True)  # Настройка SOCKS5 прокси для Telethon

# Настройки модели TTS
LANGUAGE = 'ru'  # Язык синтеза речи
MODEL_ID = 'v5_ru'  # ID модели Silero для русского языка
SPEAKER = 'kseniya'  # Голос диктора
SAMPLE_RATE = 48000  # Частота дискретизации аудио (48 кГц)
DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')  # Использовать GPU если доступен

# Настройки обработки
TEMP_DIR = "tts_chunks"  # Папка для временных аудио-кусков (для экономии памяти)
CHUNK_SIZE = 512  # Каждые 512 строк сбрасываем аудио на диск для освобождения RAM

# Настройки многопоточности
MAX_WORKERS = 4  # Количество параллельных потоков для генерации аудио

# Путь к ffmpeg
AudioSegment.converter = os.path.join(os.getcwd(), "ffmpeg.exe")

# ============================================================

# Настройка парсера аргументов командной строки
parser = argparse.ArgumentParser(description='Silero TTS + Telethon Memory Optimized + Multithreading')
parser.add_argument('--name', type=str, default='final_book', help='Имя выходного MP3 файла')
parser.add_argument('--input', type=str, default='ranobe.txt', help='Входной txt файл')
parser.add_argument('--start', type=int, help='Начальная глава')
parser.add_argument('--end', type=int, help='Конечная глава')
parser.add_argument('--workers', type=int, default=MAX_WORKERS, help='Количество потоков для генерации')
args = parser.parse_args()

# Константы на основе аргументов
INPUT_FILE = args.input  # Входной текстовый файл
OUTPUT_MP3 = f"{args.name}.mp3"  # Имя выходного MP3 файла
OUTPUT_DIR = f"{args.start}-{args.end}" if args.start and args.end else None  # Папка для глав (если указан диапазон)
MAX_WORKERS = args.workers  # Обновляем количество потоков из аргументов

def progress_callback(current, total):
    """
    Callback-функция для отображения прогресса загрузки файла в Telegram.
    
    Args:
        current: Количество уже загруженных байт
        total: Общий размер файла в байтах
    """
    percent = (current / total) * 100  # Вычисляем процент загрузки
    print(f"\r📤 Загрузка в Telegram: {percent:.1f}%", end="")

async def send_via_telethon(file_path):
    """
    Отправляет файл в Telegram через Telethon в "Избранное".
    
    Args:
        file_path: Путь к файлу для отправки
    """
    print(f"\n🚀 Подключаюсь к Telegram...")
    try:
        # Создаем асинхронный контекст клиента Telethon с сохраненной сессией
        async with TelegramClient('my_session', API_ID, API_HASH, proxy=PROXY) as client:
            await client.send_file(
                'me',  # Отправка самому себе (Избранное)
                file_path,  # Путь к файлу
                caption=f"📖 Озвучка готова: {os.path.basename(file_path)} #Telethon",  # Подпись
                progress_callback=progress_callback  # Функция отображения прогресса
            )
            print("\n✅ Файл успешно доставлен!")
    except Exception as e:
        print(f"\n❌ Ошибка Telethon: {e}")

def split_chapters(text, start_chapter, end_chapter):
    """
    Разбивает текст на отдельные главы по разделителю.
    
    Args:
        text: Полный текст книги
        start_chapter: Номер начальной главы
        end_chapter: Номер конечной главы
    
    Returns:
        dict: Словарь {номер_главы: текст_главы}
    """
    chapters = {}
    # Разделяем текст по маркеру конца главы
    parts = text.split("========== КОНЕЦ ГЛАВЫ ==========")
    
    # Нумеруем главы начиная с start_chapter
    for i, part in enumerate(parts):
        chapter_num = start_chapter + i
        if chapter_num <= end_chapter and part.strip():
            chapters[chapter_num] = part.strip()
    
    return chapters

def generate_audio_for_lines(model, lines, start_idx, end_idx, chunk_id, temp_dir, pbar=None):
    """
    Генерирует аудио для диапазона строк (используется в многопоточности).
    
    Args:
        model: Загруженная модель Silero TTS
        lines: Список всех строк текста
        start_idx: Начальный индекс строки
        end_idx: Конечный индекс строки
        chunk_id: ID чанка для именования файла
        temp_dir: Директория для временных файлов
        pbar: Прогресс-бар tqdm (опционально)
    
    Returns:
        str: Путь к созданному WAV файлу
    """
    combined_audio = AudioSegment.empty()
    
    # Режим inference без вычисления градиентов
    with torch.inference_mode():
        for i in range(start_idx, end_idx):
            if i >= len(lines):
                break
            
            line = lines[i]
            try:
                # Генерируем аудио для строки
                audio_tensor = model.apply_tts(text=line, speaker=SPEAKER, sample_rate=SAMPLE_RATE)
                audio_data = (audio_tensor * 32767).numpy().astype('int16')
                segment = AudioSegment(audio_data.tobytes(), frame_rate=SAMPLE_RATE, sample_width=2, channels=1)
                combined_audio += segment + AudioSegment.silent(duration=500)  # Добавляем паузу
                
                # Обновляем прогресс-бар
                if pbar:
                    pbar.update(1)
                    
            except Exception as e:
                # Пропускаем ошибки, но обновляем прогресс
                if pbar:
                    pbar.update(1)
    
    # Сохраняем чанк на диск
    chunk_name = os.path.join(temp_dir, f"chunk_{chunk_id:04d}.wav")
    combined_audio.export(chunk_name, format="wav")
    
    return chunk_name

def generate_audio_for_chapter(model, text, chapter_num, output_dir):
    """
    Генерирует MP3 файл для одной главы с оптимизацией памяти и многопоточностью.
    
    Args:
        model: Загруженная модель Silero TTS
        text: Текст главы
        chapter_num: Номер главы
        output_dir: Директория для сохранения MP3
    
    Returns:
        str: Путь к созданному MP3 файлу
    """
    print(f"\n🎙️ Озвучиваю главу {chapter_num}...")
    
    # Разбиваем текст на строки
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    total = len(lines)
    
    # Создаем временную папку для чанков этой главы
    temp_chapter_dir = os.path.join(TEMP_DIR, f"chapter_{chapter_num}")
    if os.path.exists(temp_chapter_dir):
        shutil.rmtree(temp_chapter_dir)  # Удаляем если существует
    os.makedirs(temp_chapter_dir)
    
    start_time = time.time()
    
    # Разбиваем строки на чанки для параллельной обработки
    chunk_ranges = []
    for i in range(0, total, CHUNK_SIZE):
        chunk_ranges.append((i, min(i + CHUNK_SIZE, total)))
    
    chunk_files = []
    
    # Создаем прогресс-бар для главы
    with tqdm(total=total, desc=f"  Глава {chapter_num}", unit="строк", 
              bar_format='{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]') as pbar:
        
        # Многопоточная генерация аудио
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = []
            for chunk_id, (start_idx, end_idx) in enumerate(chunk_ranges):
                future = executor.submit(
                    generate_audio_for_lines,
                    model, lines, start_idx, end_idx, chunk_id, temp_chapter_dir, pbar
                )
                futures.append(future)
            
            # Собираем результаты по мере завершения
            for future in as_completed(futures):
                try:
                    chunk_file = future.result()
                    chunk_files.append(chunk_file)
                except Exception as e:
                    print(f"\n⚠️ Ошибка в потоке: {e}")
    
    # Сортируем файлы по имени для правильного порядка
    chunk_files.sort()
    
    # Собираем финальный файл из всех чанков
    print(f"  📦 Собираю из {len(chunk_files)} кусков...")
    final_audio = AudioSegment.empty()
    for chunk in tqdm(chunk_files, desc="  Сборка", unit="чанк"):
        final_audio += AudioSegment.from_wav(chunk)
    
    # Экспортируем в MP3
    output_file = os.path.join(output_dir, f"{chapter_num}.mp3")
    print(f"  💾 Экспорт в {output_file}...")
    final_audio.export(output_file, format="mp3", bitrate="128k")
    
    # Удаляем временную папку главы
    shutil.rmtree(temp_chapter_dir)
    
    print(f"  ✨ Глава {chapter_num} готова! Время: {(time.time() - start_time) / 60:.1f} мин.")
    return output_file

def generate_audio():
    """
    Главная функция генерации аудио. Поддерживает два режима:
    1. Разбивка по главам (если указаны --start и --end)
    2. Один большой MP3 файл (по умолчанию)
    
    Returns:
        bool: True если генерация успешна, False при ошибке
    """
    print(f"🚀 Инициализация Silero на {DEVICE}...")
    
    # Устанавливаем директорию для кэша моделей в системную папку PyTorch
    torch.hub.set_dir(torch.hub.get_dir())
    
    # Загружаем модель Silero TTS
    model, _ = silero_tts(language=LANGUAGE, speaker=MODEL_ID)
    model.to(DEVICE)  # Переносим на GPU/CPU
    
    # Удаляем файл latest_silero_models.yml после загрузки модели
    if os.path.exists('latest_silero_models.yml'):
        os.remove('latest_silero_models.yml')

    # Проверяем существование входного файла
    if not os.path.exists(INPUT_FILE):
        print(f"❌ Файл {INPUT_FILE} не найден!")
        return False

    # РЕЖИМ 1: Если указаны start и end - разбиваем на отдельные главы
    if OUTPUT_DIR and args.start and args.end:
        # Читаем весь текст из файла
        with open(INPUT_FILE, "r", encoding="utf-8") as f:
            full_text = f.read()

        # Создаем выходную папку для глав
        if not os.path.exists(OUTPUT_DIR):
            os.makedirs(OUTPUT_DIR)
            print(f"📁 Создана папка: {OUTPUT_DIR}")
        
        # Создаем временную папку для чанков
        if os.path.exists(TEMP_DIR):
            shutil.rmtree(TEMP_DIR)
        os.makedirs(TEMP_DIR)
        
        # Разбиваем текст на главы
        chapters = split_chapters(full_text, args.start, args.end)
        print(f"📚 Найдено глав: {len(chapters)}")
        print(f"⚙️ Используется потоков: {MAX_WORKERS}")
        
        # Генерируем аудио для каждой главы отдельно
        generated_files = []
        for chapter_num in sorted(chapters.keys()):
            output_file = generate_audio_for_chapter(model, chapters[chapter_num], chapter_num, OUTPUT_DIR)
            generated_files.append(output_file)
        
        # Удаляем временную папку
        if os.path.exists(TEMP_DIR):
            shutil.rmtree(TEMP_DIR)
        
        print(f"\n🎉 Все главы готовы! Создано файлов: {len(generated_files)}")
        print(f"📂 Папка: {OUTPUT_DIR}")
        return True
    
    # РЕЖИМ 2: Один большой MP3 файл (с оптимизацией памяти и многопоточностью)
    else:
        # Читаем текстовый файл и фильтруем пустые строки
        with open(INPUT_FILE, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]

        total = len(lines)
        print(f"📖 Озвучка {total} строк (Лимит памяти: {CHUNK_SIZE} стр)")
        print(f"⚙️ Используется потоков: {MAX_WORKERS}")
        
        # Создаем временную папку для чанков
        if os.path.exists(TEMP_DIR):
            shutil.rmtree(TEMP_DIR)
        os.makedirs(TEMP_DIR)

        start_time = time.time()
        
        # Разбиваем строки на чанки для параллельной обработки
        chunk_ranges = []
        for i in range(0, total, CHUNK_SIZE):
            chunk_ranges.append((i, min(i + CHUNK_SIZE, total)))
        
        chunk_files = []
        
        # Создаем главный прогресс-бар
        print("\n🎤 Генерация аудио:")
        with tqdm(total=total, desc="Обработка", unit="строк",
                  bar_format='{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]') as pbar:
            
            # Многопоточная генерация аудио
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                futures = []
                for chunk_id, (start_idx, end_idx) in enumerate(chunk_ranges):
                    future = executor.submit(
                        generate_audio_for_lines,
                        model, lines, start_idx, end_idx, chunk_id, TEMP_DIR, pbar
                    )
                    futures.append(future)
                
                # Собираем результаты по мере завершения
                for future in as_completed(futures):
                    try:
                        chunk_file = future.result()
                        chunk_files.append(chunk_file)
                    except Exception as e:
                        print(f"\n⚠️ Ошибка в потоке: {e}")

        # Сортируем файлы по имени для правильного порядка
        chunk_files.sort()

        # Собираем финальный файл из всех чанков
        print(f"\n📦 Собираю финальный файл из {len(chunk_files)} кусков...")
        final_audio = AudioSegment.empty()
        for chunk in tqdm(chunk_files, desc="Сборка", unit="чанк"):
            final_audio += AudioSegment.from_wav(chunk)

        # Экспортируем в MP3
        print(f"💾 Экспорт в MP3 (128k)...")
        final_audio.export(OUTPUT_MP3, format="mp3", bitrate="128k")
        
        # Удаляем временную папку
        shutil.rmtree(TEMP_DIR)
        
        print(f"✨ Готово! Общее время: {(time.time() - start_time) / 60:.1f} мин.")
        return True

async def main():
    """
    Главная асинхронная функция программы с оптимизацией памяти и многопоточностью.
    Проверяет наличие готового файла или генерирует новый.
    """
    print(f"--- ЗАВОД СТАРТОВАЛ (Memory Optimized + Multithreading) ---")
    
    ready = False
    # Проверяем, существует ли уже готовый файл
    if os.path.exists(OUTPUT_MP3):
        print(f"♻️ Файл '{OUTPUT_MP3}' уже готов.")
        ready = True
    else:
        # Генерируем аудио
        if generate_audio():
            ready = True

    # Закомментированный код для отправки в Telegram (можно раскомментировать при необходимости)
    # if ready:
    #     choice = input("\n❓ Отправить файл в Telegram? (y/n): ").strip().lower()
    #     if choice == 'y':
    #         await send_via_telethon(OUTPUT_MP3)
    #     else:
    #         print(f"📁 Файл сохранен локально.")
    
    print("--- ЗАВОД ЗАКОНЧИЛ РАБОТУ ---")

# Точка входа в программу
if __name__ == "__main__":
    asyncio.run(main())  # Запускаем асинхронную главную функцию

