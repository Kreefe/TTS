# Импорт необходимых библиотек
import asyncio  # Асинхронное программирование
import sys  # Системные функции (для запуска других скриптов)
import os  # Работа с файловой системой
import argparse  # Парсинг аргументов командной строки
from playwright.async_api import async_playwright  # Автоматизация браузера

# --- КОНФИГ ПО УМОЛЧАНИЮ ---
DEFAULT_ID = "163577--pekchakkaii-manna-mweota"  # ID ранобэ на сайте по умолчанию
DEFAULT_BID = "18938"  # ID закладки (bookmark ID) по умолчанию
# ---------------------------

async def grab_chapter(browser, base_url, bid, chapter_num):
    """
    Загружает главу с сайта Ranobelib (упрощенная версия без повторных попыток).
    
    Args:
        browser: Экземпляр браузера Playwright
        base_url: Базовый URL ранобэ
        bid: Bookmark ID (ID закладки)
        chapter_num: Номер главы для загрузки
    
    Returns:
        str: Текст главы с заголовком или None при ошибке
    """
    page = await browser.new_page()  # Создаем новую вкладку браузера
    url = f"{base_url}/read/v1/c{chapter_num}?bid={bid}"  # Формируем URL главы
    
    try:
        # Загружаем страницу (ждем загрузки DOM)
        await page.goto(url, wait_until="domcontentloaded", timeout=5000)
        
        # Ждем появления текста главы на странице
        await page.wait_for_selector('p.node-paragraph', timeout=3000)
        
        # Извлечение заголовка главы
        # Пробуем достать название из header (на Ranobelib это обычно номер + название)
        try:
            chapter_title = await page.inner_text('.reader-header-action__text')
            chapter_title = chapter_title.strip()
        except:
            # Если заголовок не найден, используем стандартный формат
            chapter_title = f"Глава {chapter_num}"

        print(f"📖 Качаю: {chapter_title}...")

        # Извлекаем все параграфы текста главы
        paragraphs = await page.eval_on_selector_all(
            'p.node-paragraph',  # CSS селектор параграфов
            "nodes => nodes.map(n => n.innerText)"  # JavaScript для извлечения текста
        )
        
        await page.close()  # Закрываем вкладку
        
        # Формируем текст главы с заголовком в начале
        header = f"\n=== {chapter_title} ===\n\n"
        return header + "\n\n".join(paragraphs)

    except Exception as e:
        print(f"❌ Ошибка на главе {chapter_num}: {e}")
        await page.close()
        return None

async def main():
    """
    Главная асинхронная функция программы (упрощенная версия).
    Парсит главы с Ranobelib и опционально запускает озвучку.
    """
    # Настройка парсера аргументов
    parser = argparse.ArgumentParser(description='Ranobe Grabber Pro')
    parser.add_argument('start', type=int, help='Начальная глава')
    parser.add_argument('end', type=int, help='Конечная глава')
    parser.add_argument('--id', type=str, default=DEFAULT_ID, help='ID ранобэ на сайте')
    parser.add_argument('--bid', type=str, default=DEFAULT_BID, help='ID закладки (bid)')
    parser.add_argument('--clean', action='store_true', help='Только скачать текст, без озвучки')
    
    args = parser.parse_args()
    BASE_URL = f"https://ranobelib.me/ru/{args.id}"  # Формируем базовый URL
    
    # Запускаем Playwright для автоматизации браузера
    async with async_playwright() as p:
        # Запускаем браузер в headless режиме (без GUI) для скорости
        browser = await p.chromium.launch(headless=True)
        all_chapters_text = []  # Список для накопления текста всех глав
        
        # Загружаем главы в указанном диапазоне
        for ch in range(args.start, args.end + 1):
            text = await grab_chapter(browser, BASE_URL, args.bid, ch)
            if text:
                all_chapters_text.append(text)
                # Добавляем разделитель между главами для читаемости
                all_chapters_text.append("\n\n" + "-"*30 + "\n\n")
            
            # Небольшая пауза между загрузками глав (чтобы не перегружать сервер)
            await asyncio.sleep(0.3)
            
        await browser.close()  # Закрываем браузер

        # Если удалось скачать хотя бы одну главу
        if all_chapters_text:
            # Сохраняем весь текст в файл
            with open("ranobe.txt", "w", encoding="utf-8") as f:
                f.write("".join(all_chapters_text))
            
            print(f"\n✅ Текст готов!")
            
            # Автоматически запускаем озвучку, если не указан флаг --clean
            if not args.clean:
                print("Запускаю озвучку...")
                # Формируем команду для запуска скрипта озвучки
                cmd = f'"{sys.executable}" ttsp.py --input ranobe.txt --start {args.start} --end {args.end}'
                os.system(cmd)  # Выполняем команду
            else:
                print("🔇 Озвучка пропущена (флаг --clean)")
        else:
            print("❌ Ничего не скачалось.")

# Точка входа в программу
if __name__ == "__main__":
    asyncio.run(main())  # Запускаем асинхронную главную функцию
