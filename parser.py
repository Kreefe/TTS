# Импорт необходимых библиотек
import asyncio  # Асинхронное программирование
import sys  # Системные функции (для запуска других скриптов)
import os  # Работа с файловой системой
import argparse  # Парсинг аргументов командной строки
import re  # Регулярные выражения для обработки текста
from playwright.async_api import async_playwright  # Автоматизация браузера
from num2words import num2words  # Конвертация цифр в слова
import time  # Для замера времени выполнения

# --- КОНФИГ ПО УМОЛЧАНИЮ ---
DEFAULT_ID = "163577--pekchakkaii-manna-mweota"  # ID ранобэ на сайте по умолчанию
DEFAULT_BID = "18938"  # ID закладки (bookmark ID) по умолчанию

def clean_and_textify(text):
    """
    Очищает и обрабатывает текст для озвучки:
    1. Переводит все цифры в слова (для корректного произношения TTS)
    2. Убирает лишние пустые строки (оставляет максимум одну пустую строку между абзацами)
    
    Args:
        text: Исходный текст для обработки
    
    Returns:
        str: Обработанный текст
    """
    # Перевод всех цифр в слова на русском языке
    # Например: "123" -> "сто двадцать три"
    text = re.sub(r'\d+', lambda m: num2words(int(m.group(0)), lang='ru'), text)
    
    # Схлопываем любые последовательности переносов строк в двойной перенос (\n\n)
    # Это убирает лишние пустые строки, оставляя только одну между абзацами
    text = re.sub(r'\n\s*\n+', '\n\n', text)
    
    return text.strip()

async def grab_chapter(browser, base_url, bid, chapter_num):
    """
    Загружает главу с сайта Ranobelib с механизмом повторных попыток.
    Если загрузка не удалась — перезагружает страницу (до 3 раз).
    
    Args:
        browser: Экземпляр браузера Playwright
        base_url: Базовый URL ранобэ
        bid: Bookmark ID (ID закладки)
        chapter_num: Номер главы для загрузки
    
    Returns:
        str: Текст главы с заголовком или None при неудаче
    """
    t_start = time.time()
    
    page = await browser.new_page()  # Создаем новую вкладку браузера
    url = f"{base_url}/read/v1/c{chapter_num}?bid={bid}"  # Формируем URL главы
    
    max_retries = 10  # Максимальное количество попыток загрузки одной главы
    
    # Цикл повторных попыток
    for attempt in range(1, max_retries + 1):
        try:
            if attempt > 1:
                print(f"🔄 Попытка №{attempt} для главы {chapter_num} (перезагрузка)...")

            # Загружаем страницу (ждем только DOM, не все ресурсы для ускорения)
            await page.goto(url, wait_until="commit", timeout=2000)
            
            # Ждем появления текста главы на странице
            await page.wait_for_selector('p.node-paragraph', timeout=2000)
            
            # Если дошли сюда — страница загрузилась успешно!
            # Пытаемся извлечь заголовок главы (используем locator для скорости)
            try:
                # locator с минимальным таймаутом - если h1 есть, заберет мгновенно
                full_title = await page.locator('h1').first.text_content(timeout=100)
                full_title = full_title.strip()
                if not full_title:  # Если заголовок пустой
                    full_title = f"Глава {chapter_num}"
            except:
                # Если заголовок не найден, используем стандартный формат
                full_title = f"Глава {chapter_num}"
            
            print(f"🔗 Готово: {full_title}", end="")

            # Собираем все параграфы текста главы
            paragraphs = await page.eval_on_selector_all(
                'p.node-paragraph',  # CSS селектор параграфов
                "nodes => nodes.map(n => n.innerText)"  # JavaScript для извлечения текста
            )
            
            await page.close()  # Закрываем вкладку
            
            # Формируем финальный текст главы: заголовок + параграфы
            chapter_content = f"{full_title}.\n\n" + "\n\n".join(paragraphs)
            t_end = time.time()
            print(f" — {t_end - t_start:.2f}с")
            return chapter_content

        except Exception as e:
            print(f"⚠️ Ошибка/Таймаут на главе {chapter_num} (Попытка {attempt}/{max_retries})")
            
            # Если это была последняя попытка — останавливаем программу
            if attempt == max_retries:
                print(f"❌ Глава {chapter_num} так и не прогрузилась после {max_retries} попыток.")
                print(f"❌ КРИТИЧЕСКАЯ ОШИБКА: Остановка программы.")
                await page.close()
                raise Exception(f"Не удалось загрузить главу {chapter_num}")
            
            # Пауза перед следующей попыткой
            await asyncio.sleep(1)
            # Цикл продолжится и снова выполнит page.goto (аналог F5)

    raise Exception(f"Не удалось загрузить главу {chapter_num}")

async def main():
    """
    Главная асинхронная функция программы.
    Парсит главы с Ranobelib, обрабатывает текст и опционально запускает озвучку.
    """
    t_main_start = time.time()
    
    # Настройка парсера аргументов
    parser = argparse.ArgumentParser(description='Ranobe Grabber Pro Max')
    parser.add_argument('start', type=int, help='Начальная глава')
    parser.add_argument('end', type=int, help='Конечная глава')
    parser.add_argument('--id', type=str, default=DEFAULT_ID, help='ID ранобэ на сайте')
    parser.add_argument('--bid', type=str, default=DEFAULT_BID, help='ID закладки (bid)')
    parser.add_argument('--clean', action='store_true', help='Только скачать текст, без озвучки')
    
    args = parser.parse_args()
    BASE_URL = f"https://ranobelib.me/ru/{args.id}"  # Формируем базовый URL
    
    # Запускаем Playwright для автоматизации браузера
    async with async_playwright() as p:
        # Запускаем браузер в headless режиме (без GUI)
        browser = await p.chromium.launch(headless=True)
        
        all_chapters_text = []  # Список для накопления текста всех глав
        
        # Загружаем главы в указанном диапазоне
        for ch in range(args.start, args.end + 1):
            text = await grab_chapter(browser, BASE_URL, args.bid, ch)
            if text:
                all_chapters_text.append(text)
                # Добавляем разделитель между главами
                all_chapters_text.append("\n\n" + "="*10 + " КОНЕЦ ГЛАВЫ " + "="*10 + "\n\n")
            
            # Небольшая пауза между загрузками глав (чтобы не перегружать сервер)
            await asyncio.sleep(0.3)
            
        await browser.close()  # Закрываем браузер

        # Если удалось скачать хотя бы одну главу
        if all_chapters_text:
            final_text = "".join(all_chapters_text)  # Объединяем весь текст
            final_text = clean_and_textify(final_text)  # Обрабатываем: цифры в слова, убираем лишние переносы
            
            # Сохраняем в файл
            with open("ranobe.txt", "w", encoding="utf-8") as f:
                f.write(final_text)
            
            print(f"✅ Файл ranobe.txt готов!")
            
            t_main_end = time.time()
            print(f"⏱️ [DEBUG] ОБЩЕЕ ВРЕМЯ: {t_main_end - t_main_start:.2f}с\n")
            
            # Автоматически запускаем озвучку, если не указан флаг --clean
            if not args.clean:
                print("Запускаю TTS...")
                # Формируем команду для запуска скрипта озвучки
                cmd = f'"{sys.executable}" ttsp.py --input ranobe.txt --start {args.start} --end {args.end} --workers 6'
                os.system(cmd)  # Выполняем команду
            else:
                print("🔇 Озвучка пропущена (флаг --clean)")
        else:
            print("❌ Ни одной главы не удалось скачать.")

# Точка входа в программу
if __name__ == "__main__":
    try: 
        asyncio.run(main())  # Запускаем асинхронную главную функцию
    except KeyboardInterrupt:
        # Обработка прерывания пользователем (Ctrl+C)
        print("\n🛑 Остановка пользователем.")
