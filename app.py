"""
Flask-приложение для API генерации описаний

Этот модуль предоставляет REST API сервис для генерации описаний на основе
входных категорий с поддержкой пакетной обработки, истории запросов и CORS.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional, Any, Union

from flask import Flask, jsonify, request
from flask_cors import CORS

from models import db, GenerationHistory
from database import save_generation, get_recent_history, get_history_by_category
from generator_engine import load_assets, normalize_input, generate_description


def create_app() -> Flask:
    """
    Фабричный паттерн для создания и конфигурации Flask-приложения.
    
    Настраивает подключение к базе данных, загружает ассеты и регистрирует все API-маршруты.
    
    Returns:
        Flask: Сконфигурированный экземпляр Flask-приложения
        
    Зависимости:
        - SQLite база данных для хранения истории генераций
        - Файлы ассетов (шаблоны и фразы) для генерации описаний
    """
    app = Flask(__name__)

    # Включаем CORS для взаимодействия фронтенда (например, на порту 8000)
    # с этим API-сервером (порт 5000) во время разработки
    CORS(app)

    # Настройка расположения SQLite базы данных
    basedir = Path(__file__).resolve().parent
    instance_path = basedir / "instance"
    instance_path.mkdir(exist_ok=True)  # Создаём директорию instance, если её нет

    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{instance_path / 'generations.db'}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False  # Отключаем избыточное логирование

    # Инициализируем базу данных с Flask-приложением
    db.init_app(app)

    # Загружаем языковые ассеты (шаблоны и фразы) однократно при старте
    # Они используются генератором и неизменяемы после загрузки
    templates, phrases = load_assets(basedir)

    # Создаём все таблицы в базе данных в контексте приложения
    with app.app_context():
        db.create_all()

    # ========================================================================
    # API МАРШРУТЫ
    # ========================================================================

    @app.get("/ping")
    def ping() -> Dict[str, str]:
        """
        Эндпоинт для проверки работоспособности сервера.
        
        Используется мониторингом и балансировщиками нагрузки.
        
        Returns:
            JSON ответ с статусом сервера
        """
        return jsonify({"status": "ok", "message": "Server is running"})

    @app.post("/api/generate")
    def api_generate() -> tuple[Dict[str, Any], int]:
        """
        Генерирует описание(я) на основе входных параметров.
        
        Поддерживает два формата ввода:
        1. Одиночный запрос: {"category": "beer", "params": {...}}
        2. Пакетный запрос: [{"category": "beer", ...}, {"category": "wine", ...}]
        
        Параметры запроса:
            seed (опционально): Базовое целочисленное зерно для воспроизводимой генерации
            
        Тело запроса (JSON):
            - Одиночный объект или массив объектов с категорией и параметрами
            
        Returns:
            JSON ответ с результатами генерации и HTTP статус кодом
            
        Пример:
            POST /api/generate?seed=42
            {"category": "beer", "name": "IPA", "style": "Hazy"}
        """
        try:
            # Парсим JSON с валидацией
            payload = request.get_json(force=True, silent=False)
            if payload is None:
                return jsonify({"success": False, "error": "Нет JSON в запросе"}), 400

            # Извлекаем seed (приоритет: query string > тело запроса)
            seed_qs = request.args.get("seed")
            seed_body = payload.get("seed") if isinstance(payload, dict) else None
            seed_raw = seed_qs if seed_qs is not None else seed_body
            seed_base = int(seed_raw) if seed_raw not in (None, "") else None

            # Приводим ввод к формату списка для единообразной обработки
            items = payload if isinstance(payload, list) else [payload]

            results = []
            for idx, item in enumerate(items):
                # Нормализуем структуру ввода в ожидаемый формат
                norm = normalize_input(item)

                # Увеличиваем seed для каждого элемента пакета для уникальности
                # при сохранении воспроизводимости для каждой позиции
                seed = None if seed_base is None else (seed_base + idx)

                # Генерируем описание, используя загруженные ассеты и опциональное зерно
                text = generate_description(norm, templates, phrases, seed=seed)
                
                # Сохраняем генерацию в базу данных для истории
                saved = save_generation(
                    category=norm["category"], 
                    input_dict=norm, 
                    generated_text=text
                )
                
                results.append({
                    "category": norm["category"],
                    "description": text,
                    "saved_to_history": saved,
                })

            return jsonify({
                "success": True,
                "count": len(results),
                "results": results,
            })

        except Exception as e:
            # Обработчик всех исключений для предотвращения падения сервера
            return jsonify({"success": False, "error": str(e)}), 500

    @app.get("/api/history")
    def api_history() -> tuple[Dict[str, Any], int]:
        """
        Получает историю генераций с опциональной фильтрацией по категории.
        
        Параметры запроса:
            category (опционально): Фильтр по категории (например, "beer", "wine")
            limit (опционально): Максимальное количество записей для возврата
                                 (по умолчанию: 50, минимум: 1, максимум: 200)
            
        Returns:
            JSON ответ со списком исторических записей и HTTP статус кодом
            
        Пример:
            GET /api/history?category=beer&limit=10
        """
        try:
            category = request.args.get("category")
            limit_raw = request.args.get("limit", "50")
            
            # Валидация и нормализация параметра limit
            try:
                limit = max(1, min(200, int(limit_raw)))
            except ValueError:
                limit = 50  # Значение по умолчанию при некорректном вводе

            # Получаем историю с фильтрацией или без
            if category:
                history_list = get_history_by_category(category, limit=limit)
            else:
                history_list = get_recent_history(limit=limit)

            return jsonify({
                "success": True,
                "count": len(history_list),
                "history": history_list,
            })
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    @app.get("/api/history/<int:record_id>")
    def api_history_record(record_id: int) -> tuple[Dict[str, Any], int]:
        """
        Получает конкретную запись из истории по её ID.
        
        Аргументы пути:
            record_id: Уникальный идентификатор записи в базе данных
            
        Returns:
            JSON ответ с деталями записи или ошибкой 404
            и HTTP статус кодом
            
        Пример:
            GET /api/history/42
        """
        try:
            # Ищем запись в базе данных
            record = GenerationHistory.query.get(record_id)
            
            if not record:
                return (
                    jsonify({"success": False, "error": f"Запись с ID {record_id} не найдена"}),
                    404,
                )
                
            return jsonify({"success": True, "record": record.to_dict()})
            
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    return app


if __name__ == "__main__":
    """
    Точка входа приложения при запуске скрипта напрямую.
    
    Создаёт экземпляр приложения и запускает встроенный сервер разработки.
    В production рекомендуется использовать WSGI-сервер (gunicorn, uWSGI и т.д.).
    """
    app = create_app()
    # debug=True включает режим отладки (автоматическая перезагрузка, подробные ошибки)
    # host="0.0.0.0" делает сервер доступным с других устройств в сети
    # port=5000 стандартный порт Flask
    app.run(debug=True, host="0.0.0.0", port=5000)
