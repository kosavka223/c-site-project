"""
Модуль для работы с базой данных генераций описаний.

Обеспечивает функции для сохранения результатов генерации и получения
истории запросов с поддержкой фильтрации по категориям.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from models import db, GenerationHistory


def save_generation(category: str, input_dict: Dict[str, Any], generated_text: str) -> bool:
    """
    Сохраняет результат генерации в базу данных.
    
    Args:
        category: Категория генерации (например, "beer", "wine")
        input_dict: Словарь с входными параметрами (нормализованными)
        generated_text: Сгенерированный текст описания
        
    Returns:
        bool: True если сохранение успешно, False в случае ошибки
    """
    from datetime import datetime

    # Создаём объект записи с явным указанием created_at
    row = GenerationHistory(
        category=category,
        input_data=json.dumps(input_dict, ensure_ascii=False),
        generated_text=generated_text,
        created_at=datetime.utcnow(),  # явно указываем время создания в UTC
    )
    try:
        # ВНИМАНИЕ: здесь происходит дублирование создания записи
        # Первая переменная row перезаписывается второй
        row = GenerationHistory(
            category=category,
            input_data=json.dumps(input_dict, ensure_ascii=False),
            generated_text=generated_text,
            # created_at не указан - будет использовано значение по умолчанию из модели
        )
        # Добавляем запись в сессию SQLAlchemy
        db.session.add(row)
        # Фиксируем транзакцию в базе данных
        db.session.commit()
        return True
    except Exception:
        # В случае ошибки откатываем транзакцию
        db.session.rollback()
        return False


def get_recent_history(limit: int = 50) -> List[dict]:
    """
    Возвращает последние записи из истории генераций.
    
    Args:
        limit: Максимальное количество записей (по умолчанию: 50)
        
    Returns:
        List[dict]: Список словарей с данными записей, отсортированный от новых к старым
    """
    # Запрашиваем все записи, сортируем по ID в обратном порядке (новые сначала)
    # и ограничиваем количество результатом limit
    rows = (
        GenerationHistory.query.order_by(GenerationHistory.id.desc()).limit(limit).all()
    )
    # Преобразуем ORM-объекты в словари для JSON-сериализации
    return [r.to_dict() for r in rows]


def get_history_by_category(category: str, limit: int = 50) -> List[dict]:
    """
    Возвращает историю генераций, отфильтрованную по категории.
    
    Args:
        category: Название категории для фильтрации
        limit: Максимальное количество записей (по умолчанию: 50)
        
    Returns:
        List[dict]: Список словарей с данными записей указанной категории,
                   отсортированный от новых к старым
    """
    # Запрашиваем записи с фильтром по категории
    rows = (
        GenerationHistory.query.filter_by(category=category)
        .order_by(GenerationHistory.id.desc())
        .limit(limit)
        .all()
    )
    # Преобразуем ORM-объекты в словари для JSON-сериализации
    return [r.to_dict() for r in rows]
