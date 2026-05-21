"""
Модуль для определения моделей базы данных.

Содержит SQLAlchemy ORM модели для работы с историей генераций описаний.
"""

from __future__ import annotations

from datetime import datetime
from flask_sqlalchemy import SQLAlchemy


# Инициализация расширения SQLAlchemy без привязки к приложению
# Экземпляр db будет связан с Flask-приложением позже через вызов db.init_app(app)
db = SQLAlchemy()


class GenerationHistory(db.Model):
    """
    Модель для хранения истории генераций описаний.
    
    Сохраняет входные параметры, сгенерированный текст и метаданные
    о каждой операции генерации.
    
    Attributes:
        id: Уникальный идентификатор записи (первичный ключ)
        category: Категория генерации (beer, wine, cheese и т.д.)
        input_data: JSON-строка с входными параметрами
        generated_text: Сгенерированный текст описания
        created_at: Временная метка создания записи (UTC)
    """
    
    # Имя таблицы в базе данных
    __tablename__ = "generation_history"

    # Первичный ключ - автоинкрементируемый идентификатор
    id = db.Column(db.Integer, primary_key=True)
    
    # Категория генерации: строка до 64 символов, обязательное поле,
    # с индексов для ускорения поиска и фильтрации
    category = db.Column(db.String(64), nullable=False, index=True)
    
    # Входные данные в формате JSON: текстовое поле, обязательное
    # Хранит сериализованный словарь с параметрами генерации
    input_data = db.Column(db.Text, nullable=False)
    
    # Сгенерированный текст: текстовое поле, обязательное
    generated_text = db.Column(db.Text, nullable=False)
    
    # Временная метка создания: автоматически устанавливается в момент создания записи
    # Используется UTC время, имеет индекс для сортировки по времени
    created_at = db.Column(
        db.DateTime, 
        default=datetime.utcnow,  # функция, вызываемая при создании записи
        nullable=False, 
        index=True  # индекс для быстрой сортировки и фильтрации по дате
    )

    def to_dict(self) -> dict:
        """
        Преобразует ORM-объект в словарь для JSON-сериализации.
        
        Этот метод используется для подготовки данных перед отправкой
        в ответе API или для логирования.
        
        Returns:
            dict: Словарь со всеми полями записи, где created_at форматируется
                  как ISO 8601 строка с суффиксом 'Z' (UTC).
                  
        Пример:
            >>> record = GenerationHistory(...)
            >>> record.to_dict()
            {
                "id": 1,
                "category": "beer",
                "input_data": '{"name": "IPA"}',
                "generated_text": "Тропическое пиво...",
                "created_at": "2024-01-15T10:30:00Z"
            }
        """
        return {
            "id": self.id,
            "category": self.category,
            "input_data": self.input_data,
            "generated_text": self.generated_text,
            # Форматируем datetime в ISO 8601 и добавляем 'Z' для обозначения UTC
            # isoformat() даёт формат "YYYY-MM-DDTHH:MM:SS.mmmmmm"
            # Конвертация в UTC предполагается на уровне приложения
            "created_at": self.created_at.isoformat() + "Z",
        }
