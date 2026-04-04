# Импорт необходимых библиотек
import os  # Работа с файловой системой
import torch  # PyTorch для работы с нейросетями
import argparse  # Парсинг аргументов командной строки
import time  # Измерение времени выполнения
import asyncio  # Асинхронное программирование
from pydub import AudioSegment  # Обработка аудио файлов
from silero import silero_tts  # Модель синтеза речи Silero
from pyrogram import Client  # Telegram клиент Pyrogram
import socks  # Поддержка SOCKS прокси

# ================= НАСТРОЙКИ (Твои данные) =================
API_ID = 22539624  # ID приложения Telegram API
API_HASH = 'edaefad085cceec2bc935abe4f739235'  # Хеш приложения Telegram API

# Настройка прокси для Kurigram (SOCKS5 прокси на локальном хосте)
proxy_settings = {
    "scheme": "socks5",  # Тип прокси
    "hostname": "127.0.0.1",  # Адрес прокси-сервера
    "port": 10808  # Порт прокси-сервера
}
# ===========================================================

# Настройка парсера аргументов командной строки
parser = argparse.ArgumentParser(description='Silero TTS + Kurigram Speed Edition')
parser.add_argument('--name', type=str, default='final_book', help='Имя выходного MP3 файла')
args = parser.parse_args()

# Константы и настройки для генерации аудио
INPUT_FILE = "ranobe.txt"  # Входной текстовый файл
OUTPUT_MP3 = f"{args.name}.mp3"  # Имя выходного MP3 файла
language = 'ru'  # Язык синтеза речи
model_id = 'v5_ru'  # ID модели Silero для русского языка
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')  # Использовать GPU если доступен, иначе CPU
speaker = 'kseniya'  # Голос диктора
sample_rate = 48000  # Частота дискретизации аудио (48 кГц)
AudioSegment.converter = os.path.join(os.getcwd(), "ffmpeg.exe")  # Путь к ffmpeg для конвертации аудио

async def progress_callback(current, total, *args):
    """
    Callback-функция для отображения прогресса загрузки файла в Telegram.
    
    Args:
        current: Количество уже загруженных байт
        total: Общий размер файла в байтах
        *args: Дополнительные аргументы (не используются)
    """
    if total > 0:
        percent = (current / total) * 100  # Вычисляем процент загрузки
        print(f"\r🚀 Скоростная отгрузка Kurigram: {percent:.1f}%", end="")

async def send_via_kurigram(file_path):
    """
    Отправляет файл в Telegram через Pyrogram (Kurigram) в "Избранное" (Saved Messages).
    
    Args:
        file_path: Путь к файлу для отправки
    """
    print(f"\n📦 Подключаюсь к Telegram...")
    try:
        # Создаем асинхронный контекст клиента Pyrogram с сохраненной сессией
        async with Client("kurigram_session", API_ID, API_HASH, proxy=proxy_settings) as app:
            print(f"📡 Заливаю файл: {os.path.basename(file_path)}")
            
            # Отправляем документ в "Избранное" ("me" = сам себе)
            await app.send_document(
                "me",  # Отправка самому себе (Избранное)
                file_path,  # Путь к файлу
                caption=f"🎧 Озвучка готова: {os.path.basename(file_path)} #KurigramSpeed",  # Подпись к файлу
                progress=progress_callback  # Функция отображения прогресса
            )
            print("\n✅ Файл успешно доставлен в твоё 'Избранное'!")
    except Exception as e:
        print(f"\n❌ Ошибка Kurigram: {e}")

def generate_audio():
    """
    Генерирует аудиофайл из текстового файла с помощью Silero TTS.
    
    Returns:
        bool: True если генерация успешна, False если файл не найден
    """
    print(f"🚀 Инициализация Silero на {device}...")
    # Загружаем модель Silero TTS
    model, _ = silero_tts(language=language, speaker=model_id)
    model.to(device)  # Переносим модель на выбранное устройство (GPU/CPU)

    combined_audio = AudioSegment.empty()  # Создаем пустой аудио сегмент для накопления

    # Проверяем существование входного файла
    if not os.path.exists(INPUT_FILE):
        print(f"❌ Файл {INPUT_FILE} не найден!")
        return False

    # Читаем текстовый файл и фильтруем пустые строки
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    total = len(lines)
    print(f"📖 Озвучка {total} строк...")
    start_time = time.time()

    # Режим inference без вычисления градиентов (экономия памяти)
    with torch.inference_mode():
        for i, text in enumerate(lines):
            try:
                # Генерируем аудио для текущей строки
                audio_tensor = model.apply_tts(text=text, speaker=speaker, sample_rate=sample_rate)
                # Конвертируем тензор в 16-битный PCM формат
                audio_data = (audio_tensor * 32767).numpy().astype('int16')
                
                # Создаем аудио сегмент из сырых данных
                segment = AudioSegment(
                    audio_data.tobytes(),  # Байтовое представление аудио
                    frame_rate=sample_rate,  # Частота дискретизации
                    sample_width=2,  # 2 байта = 16 бит
                    channels=1  # Моно
                )
                # Добавляем сегмент к общему аудио + 0.5 сек паузы между строками
                combined_audio += segment + AudioSegment.silent(duration=500)
                
                # Каждые 50 строк выводим статистику прогресса
                if (i + 1) % 50 == 0:
                    elapsed = time.time() - start_time
                    speed = (i + 1) / elapsed  # Скорость обработки (строк/сек)
                    print(f"✅ Обработано: {i+1}/{total} | {speed:.1f} стр/сек")
            except Exception:
                # Пропускаем строки с ошибками без остановки процесса
                pass

    # Экспортируем финальный аудиофайл в MP3 с битрейтом 128 кбит/с
    print(f"\n📦 Рендер финального MP3 (128k)...")
    combined_audio.export(OUTPUT_MP3, format="mp3", bitrate="128k")
    print(f"✨ Рендер завершен!")
    return True

async def main():
    """
    Главная асинхронная функция программы.
    Проверяет наличие готового файла, генерирует аудио если нужно,
    и отправляет результат в Telegram.
    """
    print(f"--- ЗАВОД СТАРТОВАЛ (Файл: {OUTPUT_MP3}) ---")
    
    # ПРОВЕРКА: Если файл уже существует, пропускаем генерацию
    if os.path.exists(OUTPUT_MP3):
        print(f"♻️ Нашел готовый файл '{OUTPUT_MP3}'. Пропускаю генерацию...")
        await send_via_kurigram(OUTPUT_MP3)
        print("--- ЗАВОД ЗАКОНЧИЛ РАБОТУ ---")
        return

    # Если файла нет — генерируем аудио и отправляем
    if generate_audio():
        await send_via_kurigram(OUTPUT_MP3)
    
    print("--- ЗАВОД ЗАКОНЧИЛ РАБОТУ ---")

# Точка входа в программу
if __name__ == "__main__":
    asyncio.run(main())  # Запускаем асинхронную главную функцию
