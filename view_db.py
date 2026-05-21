"""
Скрипт для проверки и просмотра содержимого базы данных SQLite.

Используется для отладки и мониторинга состояния базы данных генераций.
Выводит список таблиц, количество записей и последние 5 записей.
"""

import sqlite3
from pathlib import Path


# Путь к файлу базы данных (относительно расположения текущего скрипта)
# instance/generations.db - стандартное расположение для Flask приложений
DB = Path(__file__).parent / "instance" / "generations.db"

# Проверяем существование файла базы данных перед подключением
# Если файл не найден - завершаем скрипт с сообщением об ошибке
if not DB.exists():
    raise SystemExit(f"DB not found: {DB}")

# Устанавливаем соединение с SQLite базой данных
conn = sqlite3.connect(DB)
# Создаём курсор для выполнения SQL запросов
cur = conn.cursor()

# Запрашиваем список всех таблиц в базе данных
# sqlite_master - системная таблица SQLite с метаданными о структуре БД
# type='table' - фильтруем только таблицы (исключая индексы, триггеры и т.д.)
cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
# Выводим имена таблиц в виде списка
print("Tables:", [r[0] for r in cur.fetchall()])

# Подсчитываем общее количество записей в таблице generation_history
cur.execute("SELECT COUNT(*) FROM generation_history;")
# Выводим количество строк (первое поле в первой строке результата)
print("Rows:", cur.fetchone()[0])

# Выводим 5 последних записей из истории генераций
# Выбираем: id, категорию, дату создания и первые 80 символов сгенерированного текста
# substr(generated_text,1,80) - обрезаем длинный текст для компактного вывода
cur.execute(
    "SELECT id, category, created_at, substr(generated_text,1,80) FROM generation_history ORDER BY id DESC LIMIT 5;"
)
print("\nLast 5:")
# Обходим все строки результата запроса
for r in cur.fetchall():
    # Выводим ID, категорию, дату и обрезанный текст
    # Если текст был обрезан (ровно 80 символов), добавляем многоточие
    print(r[0], r[1], r[2], r[3] + ("…" if len(r[3]) == 80 else ""))

# Закрываем соединение с базой данных
# Важно всегда закрывать соединение для освобождения ресурсов
conn.close()
