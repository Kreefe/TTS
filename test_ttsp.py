# Тестовый скрипт для проверки новой функциональности ttsp.py
import os
import sys

def create_test_file():
    """Создает тестовый файл с текстом для озвучки"""
    test_text = """Глава первая. Начало приключения.

Это тестовый текст для проверки работы системы озвучки.
Мы проверяем работу прогресс-баров и многопоточности.
Система должна корректно обрабатывать текст построчно.

Каждая строка будет преобразована в аудио.
Прогресс-бар покажет процент выполнения.
Многопоточность ускорит генерацию аудио.

========== КОНЕЦ ГЛАВЫ ==========

Глава вторая. Продолжение истории.

Вторая глава содержит дополнительный текст.
Проверяем разбивку на отдельные главы.
Каждая глава должна быть сохранена в отдельный файл.

Система автоматически определит границы глав.
Прогресс будет отображаться для каждой главы отдельно.

========== КОНЕЦ ГЛАВЫ ==========

Глава третья. Финал.

Завершающая глава нашего теста.
Проверяем корректность сборки всех чанков.
Финальный MP3 файл должен содержать все главы.

Спасибо за использование QwenTTS!
"""
    
    with open("test_input.txt", "w", encoding="utf-8") as f:
        f.write(test_text)
    
    print("✅ Создан тестовый файл: test_input.txt")
    return "test_input.txt"

def run_tests():
    """Запускает серию тестов"""
    print("=" * 60)
    print("🧪 ТЕСТИРОВАНИЕ QwenTTS v2.0")
    print("=" * 60)
    
    # Создаем тестовый файл
    test_file = create_test_file()
    
    print("\n📋 Доступные тесты:")
    print("1. Базовый тест (один MP3 файл, 2 потока)")
    print("2. Тест разбивки на главы (отдельные MP3, 4 потока)")
    print("3. Тест производительности (8 потоков)")
    print("4. Все тесты последовательно")
    print("5. Выход")
    
    choice = input("\nВыберите тест (1-5): ").strip()
    
    if choice == "1":
        print("\n" + "=" * 60)
        print("🧪 ТЕСТ 1: Базовая генерация (2 потока)")
        print("=" * 60)
        cmd = f'"{sys.executable}" ttsp.py --input test_input.txt --name test_basic --workers 2'
        print(f"Команда: {cmd}\n")
        os.system(cmd)
        
    elif choice == "2":
        print("\n" + "=" * 60)
        print("🧪 ТЕСТ 2: Разбивка на главы (4 потока)")
        print("=" * 60)
        cmd = f'"{sys.executable}" ttsp.py --input test_input.txt --start 1 --end 3 --workers 4'
        print(f"Команда: {cmd}\n")
        os.system(cmd)
        
    elif choice == "3":
        print("\n" + "=" * 60)
        print("🧪 ТЕСТ 3: Производительность (8 потоков)")
        print("=" * 60)
        cmd = f'"{sys.executable}" ttsp.py --input test_input.txt --name test_performance --workers 8'
        print(f"Команда: {cmd}\n")
        os.system(cmd)
        
    elif choice == "4":
        print("\n" + "=" * 60)
        print("🧪 ЗАПУСК ВСЕХ ТЕСТОВ")
        print("=" * 60)
        
        tests = [
            ("Тест 1: Базовая генерация (2 потока)", 
             f'"{sys.executable}" ttsp.py --input test_input.txt --name test_basic --workers 2'),
            ("Тест 2: Разбивка на главы (4 потока)", 
             f'"{sys.executable}" ttsp.py --input test_input.txt --start 1 --end 3 --workers 4'),
            ("Тест 3: Производительность (8 потоков)", 
             f'"{sys.executable}" ttsp.py --input test_input.txt --name test_performance --workers 8'),
        ]
        
        for i, (name, cmd) in enumerate(tests, 1):
            print(f"\n{'=' * 60}")
            print(f"🧪 {name}")
            print(f"{'=' * 60}")
            print(f"Команда: {cmd}\n")
            os.system(cmd)
            
            if i < len(tests):
                input("\nНажмите Enter для продолжения...")
        
    elif choice == "5":
        print("👋 Выход из тестирования")
        return
    
    else:
        print("❌ Неверный выбор")
        return
    
    print("\n" + "=" * 60)
    print("✅ ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
    print("=" * 60)
    print("\n📁 Созданные файлы:")
    
    # Проверяем созданные файлы
    files_to_check = [
        "test_basic.mp3",
        "test_performance.mp3",
        "1-3/1.mp3",
        "1-3/2.mp3",
        "1-3/3.mp3"
    ]
    
    for file in files_to_check:
        if os.path.exists(file):
            size = os.path.getsize(file) / 1024  # KB
            print(f"  ✅ {file} ({size:.1f} KB)")
    
    print("\n💡 Рекомендации:")
    print("  - Прослушайте созданные MP3 файлы")
    print("  - Проверьте качество озвучки")
    print("  - Убедитесь, что прогресс-бары отображались корректно")
    print("  - Сравните время генерации с разным количеством потоков")
    
    # Очистка
    cleanup = input("\n🗑️ Удалить тестовые файлы? (y/n): ").strip().lower()
    if cleanup == 'y':
        import shutil
        
        files_to_remove = ["test_input.txt", "test_basic.mp3", "test_performance.mp3"]
        dirs_to_remove = ["1-3", "tts_chunks"]
        
        for file in files_to_remove:
            if os.path.exists(file):
                os.remove(file)
                print(f"  🗑️ Удален: {file}")
        
        for dir in dirs_to_remove:
            if os.path.exists(dir):
                shutil.rmtree(dir)
                print(f"  🗑️ Удалена папка: {dir}")
        
        print("✅ Очистка завершена")
    else:
        print("📁 Тестовые файлы сохранены")

if __name__ == "__main__":
    try:
        run_tests()
    except KeyboardInterrupt:
        print("\n\n🛑 Тестирование прервано пользователем")
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
