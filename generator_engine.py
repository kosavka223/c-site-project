import json  # Чтение JSON-файлов: templates.json и phrases.json.
import random  # Случайный выбор шаблонов и фраз, а также работа с seed.
import re  # Регулярные выражения для очистки итогового текста.
from pathlib import Path  # Удобная работа с путями к файлам.
from typing import Any, Dict, Tuple, Union  # Подсказки типов для читаемости кода.


class SafeDict(dict):
    """Словарь для безопасной подстановки значений в строковый шаблон.

    В обычном dict, если template.format_map(...) встретит отсутствующий ключ,
    будет ошибка KeyError. Здесь отсутствующий ключ заменяется пустой строкой,
    поэтому генерация не падает, даже если какой-то блок описания не был создан.
    """

    def __missing__(self, key: str) -> str:
        # Например, если в шаблоне есть {camera_phrase}, но для товара камера не указана,
        # вместо ошибки подставится пустая строка.
        return ""


def _load_json(path: Union[str, Path]) -> Any:
    """Загружает JSON-файл и возвращает его как Python-объект.

    path может быть строкой или объектом Path.
    В проекте функция используется для загрузки шаблонов и словарей фраз.
    """
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _clean_text(text: str) -> str:
    """Очищает итоговое описание после сборки по шаблону.

    При генерации часть фраз может быть пустой, поэтому в тексте могут появиться
    двойные пробелы, двойные точки или пробелы перед знаками препинания.
    Эта функция приводит описание к аккуратному виду.
    """
    # Любые пробелы, табы и переносы строк заменяются одним пробелом.
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    # Убирает пробел перед пунктуацией: "товар ." -> "товар."
    text = re.sub(r"\s+([.,!?;:])", r"\1", text)
    # Убирает двойные точки: "товар.." -> "товар."
    text = re.sub(r"\.\s*\.", ".", text)
    # Убирает двойные запятые.
    text = re.sub(r"\s*,\s*,", ",", text)
    # Убирает ситуацию, когда после длинного тире сразу стоит точка.
    text = re.sub(r"\s+—\s*\.", ".", text)
    # Убирает пробел перед точкой.
    text = re.sub(r"\s+\.", ".", text)
    return text.strip()


def _fmt(x: Any) -> str:
    """Форматирует значение перед вставкой в описание.

    Нужна, чтобы не выводить None, красиво показывать bool и дробные числа.
    Например: 6.60 -> "6.6", True -> "да", None -> "".
    """
    if x is None:
        return ""
    if isinstance(x, bool):
        return "да" if x else "нет"
    if isinstance(x, int):
        return str(x)
    if isinstance(x, float):
        # Оставляет максимум 2 знака после запятой и убирает лишние нули.
        s = f"{x:.2f}".rstrip("0").rstrip(".")
        return s
    return str(x)


def _as_num(x: Any) -> Union[int, float, None]:
    """Пытается привести значение к числу.

    Из frontend значения часто приходят строками. Эта функция умеет обрабатывать
    строки вроде "8", "6.5", "6,5", "16 ГБ", "1800 MHz".
    Если число получить нельзя, возвращается None.
    """
    if isinstance(x, (int, float)):
        return x
    if isinstance(x, str):
        # Приведение к нижнему регистру, замена запятой на точку.
        s = x.strip().lower().replace(",", ".")
        # Удаление распространенных единиц измерения.
        s = s.replace("gb", "").replace("гб", "")
        s = s.replace("mhz", "").replace("мгц", "")
        try:
            # Если в строке есть точка, возвращаем float, иначе int.
            return float(s) if "." in s else int(s)
        except Exception:
            return None
    return None


def _purpose_phrase(v: Any) -> str:
    """Формирует фразу назначения для кроссовок.

    Примеры:
    "город" -> "для города. "
    "бег" -> "для бега. "
    "для спорта" -> "для спорта. "
    "зал" -> "для тренировок. "
    """
    if not isinstance(v, str):
        return ""
    s = v.strip()
    if not s:
        return ""

    low = s.lower()

    # Словарь нормализации частых вариантов ввода.
    direct_map = {
        "город": "для города",
        "города": "для города",
        "бег": "для бега",
        "бега": "для бега",
        "тренировки": "для тренировок",
        "тренировок": "для тренировок",
        "спорт": "для спорта",
        "спорта": "для спорта",
        "повседневные": "для повседневной носки",
        "повседневная носка": "для повседневной носки",
        "повседневной носки": "для повседневной носки",
        "зал": "для тренировок",
    }

    if low.startswith("для "):
        # Если пользователь уже написал "для ...", ничего не добавляем.
        phrase = s
    elif low in direct_map:
        # Если значение известно, берем красивую готовую фразу.
        phrase = direct_map[low]
    else:
        # Для неизвестного значения просто добавляем "для".
        phrase = f"для {s}"

    # Гарантируем точку в конце фразы.
    if not phrase.endswith("."):
        phrase += "."

    # Пробел в конце нужен, чтобы фраза нормально склеивалась с остальным текстом.
    return phrase + " "


def _platform_phrase(v: Any) -> str:
    """Формирует фразу о платформе видеокарты."""
    if not isinstance(v, str):
        return ""
    s = v.strip().lower()
    if not s:
        return ""
    if s in {"pc", "пк", "desktop"}:
        return "Версия для ПК. "
    if s in {"laptop", "ноутбук", "notebook"}:
        return "Версия для ноутбука. "
    # Если платформа нестандартная, выводим ее как есть.
    return f"Версия: {v.strip()}. "


def _gpu_is_old(attrs: Dict[str, Any]) -> bool:
    """Определяет, старая видеокарта или современная.

    Это влияет на выбор фраз. Для старых карт используются более осторожные
    формулировки, а для современных — более сильные рекламные фразы.
    """
    manufacturer = str(attrs.get("manufacturer", "")).strip().lower()
    version = str(attrs.get("version", "")).strip().lower()

    # В одну строку объединяются производитель и версия, чтобы искать маркеры.
    text = f"{manufacturer} {version}"

    # Маркеры очень старых или слабых серий.
    old_markers = [
        "gtx 4", "gtx 5", "gtx 6", "gtx 7", "gtx 8", "gtx 9",
        "gt ", "gts ", "9800", "8800", "hd 4", "hd 5", "hd 6", "hd 7",
        "r7 ", "r9 2", "r9 3", "rx 4", "rx 5", "quadro 2000", "quadro 4000"
    ]
    # Маркеры карт, которые не совсем древние, но уже считаются устаревающими.
    mid_old_markers = [
        "gtx 10", "gtx 1050", "gtx 1060", "gtx 1070", "gtx 1080",
        "rx 560", "rx 570", "rx 580"
    ]

    # Если в названии есть один из маркеров, карта считается старой.
    for m in old_markers:
        if m in text:
            return True
    for m in mid_old_markers:
        if m in text:
            return True

    return False


def _get_adjective_for_category(category: str, adj: str) -> str:
    """Склоняет прилагательное под категорию товара.

    Нужно, потому что категории имеют разный род и число:
    смартфон — мужской род: "современный";
    кроссовки — множественное число: "современные";
    видеокарта — женский род: "современная".
    """
    if not adj:
        return ""

    # Для каждой категории задается замена окончаний.
    endings = {
        "smartphone": {
            "ый": "ый",
            "ий": "ий",
            "ой": "ой",
            "ский": "ский",
            "цкий": "цкий",
            "ной": "ной",
        },
        "sneakers": {
            "ый": "ые",
            "ий": "ие",
            "ой": "ые",
            "ский": "ские",
            "цкий": "цкие",
            "ной": "ные",
        },
        "gpu": {
            "ый": "ая",
            "ий": "яя",
            "ой": "ая",
            "ский": "ская",
            "цкий": "цкая",
            "ной": "ная",
        }
    }

    category_endings = endings.get(category, endings["smartphone"])

    # Берем первое подходящее окончание и заменяем его.
    for old_end, new_end in category_endings.items():
        if adj.endswith(old_end):
            return adj[:-len(old_end)] + new_end

    return adj


def _build_smartphone(attrs: Dict[str, Any], phrases: dict, rng: random.Random) -> Dict[str, str]:
    """Собирает текстовые блоки для смартфона.

    Возвращает словарь с готовыми кусками текста: название, фраза про экран,
    память, батарею, камеру, особенность и т.д. Потом эти куски вставляются
    в шаблон из templates.json.
    """
    out: Dict[str, str] = {}

    # Название товара собирается из бренда и модели.
    brand = attrs.get("brand", "")
    model = attrs.get("model", "")

    if brand and model:
        out["title"] = f"{brand} {model}"
    elif brand:
        out["title"] = brand
    elif model:
        out["title"] = model
    else:
        out["title"] = "Смартфон"

    # Сценарий использования берется случайно из словаря use_case_smartphone.
    use_cases = phrases.get("use_case_smartphone", [])
    use_case = rng.choice(use_cases).strip() if use_cases else ""
    out["use_case_phrase"] = f" — {use_case}. " if use_case else ". "

    # Фраза про диагональ экрана.
    screen = _as_num(attrs.get("screen_size_in"))
    out["screen_phrase"] = f"Экран {_fmt(screen)} дюйма удобен для контента. " if isinstance(screen, (int,
                                                                                                      float)) and screen > 0 else ""

    # Фраза про RAM и встроенную память.
    ram = _as_num(attrs.get("ram_gb"))
    storage = _as_num(attrs.get("storage_gb"))
    if isinstance(ram, (int, float)) and ram > 0 and isinstance(storage, (int, float)) and storage > 0:
        out["perf_phrase"] = f"{_fmt(ram)} ГБ RAM и {_fmt(storage)} ГБ памяти подходят для приложений и файлов. "
    elif isinstance(storage, (int, float)) and storage > 0:
        out["perf_phrase"] = f"{_fmt(storage)} ГБ памяти хватит для фото, файлов и приложений. "
    elif isinstance(ram, (int, float)) and ram > 0:
        out["perf_phrase"] = f"{_fmt(ram)} ГБ RAM помогают в многозадачности. "
    else:
        out["perf_phrase"] = ""

    # Фраза про аккумулятор.
    battery = _as_num(attrs.get("battery_mah"))
    out["battery_phrase"] = f"Аккумулятор {_fmt(battery)} мА·ч помогает дольше оставаться на связи. " if isinstance(
        battery, (int, float)) and battery > 0 else ""

    # Фраза про камеру.
    camera = _as_num(attrs.get("camera_mp"))
    out["camera_phrase"] = f"Камера {_fmt(camera)} Мп пригодится для фото и видео. " if isinstance(camera, (int,
                                                                                                            float)) and camera > 0 else ""

    # Дополнительная случайная фраза для смартфона.
    extra_pool = phrases.get("smartphone_extra", [])
    out["extra_phrase"] = (rng.choice(extra_pool).strip() + ". ") if extra_pool else ""

    # Особенность, которую вводит пользователь.
    feat = attrs.get("key_feature")
    fs = feat.strip() if isinstance(feat, str) else ""
    out["feature_phrase"] = f"Дополнительное преимущество — {fs}. " if fs else ""

    return out


def _build_sneakers(attrs: Dict[str, Any], phrases: dict, rng: random.Random) -> Dict[str, str]:
    """Собирает текстовые блоки для кроссовок."""
    out: Dict[str, str] = {}

    # Название товара собирается из бренда и модели.
    brand = attrs.get("brand", "")
    model = attrs.get("model", "")

    if brand and model:
        out["title"] = f"{brand} {model}"
    elif brand:
        out["title"] = brand
    elif model:
        out["title"] = model
    else:
        out["title"] = "Кроссовки"

    # Назначение кроссовок: для города, для бега, для тренировок.
    out["purpose_phrase"] = _purpose_phrase(attrs.get("purpose"))

    # Размер в EU.
    size = _as_num(attrs.get("size_eu"))
    out["size_phrase"] = f"Размер {_fmt(size)} EU. " if isinstance(size, (int, float)) and size > 0 else ""

    # Материал верха.
    material = attrs.get("material_upper")
    ms = material.strip() if isinstance(material, str) else ""
    out["material_phrase"] = f"Верх из материала «{ms}» обеспечивает комфорт. " if ms else ""

    # Сезон.
    season = attrs.get("season")
    ss = season.strip() if isinstance(season, str) else ""
    out["season_phrase"] = f"Подойдут на сезон: {ss}. " if ss else ""

    # Цвет.
    color = attrs.get("color")
    cs = color.strip() if isinstance(color, str) else ""
    out["color_phrase"] = f"Цвет: {cs}. " if cs else ""

    # Случайная фраза про комфорт.
    comfort_pool = phrases.get("sneakers_comfort", [])
    out["comfort_phrase"] = (rng.choice(comfort_pool).strip() + ". ") if comfort_pool else ""

    # Пользовательская особенность.
    feat = attrs.get("key_feature")
    fs = feat.strip() if isinstance(feat, str) else ""
    out["feature_phrase"] = f"Особенность — {fs}. " if fs else ""

    return out


def _build_gpu(attrs: Dict[str, Any], phrases: dict, rng: random.Random) -> Dict[str, str]:
    """Собирает текстовые блоки для видеокарты."""
    out: Dict[str, str] = {}

    # Название видеокарты собирается из производителя и версии.
    manufacturer = attrs.get("manufacturer", "")
    version = attrs.get("version", "")

    if manufacturer and version:
        out["title"] = f"{manufacturer} {version}"
    elif manufacturer:
        out["title"] = manufacturer
    elif version:
        out["title"] = version
    else:
        out["title"] = "Видеокарта"

    # Платформа: ПК, ноутбук или другое значение.
    out["platform_phrase"] = _platform_phrase(attrs.get("platform"))

    # Охлаждение.
    cooling = attrs.get("cooling")
    cs = cooling.strip() if isinstance(cooling, str) else ""
    out["cooling_phrase"] = f"Охлаждение: {cs}. " if cs else ""

    # Объем видеопамяти.
    mem = _as_num(attrs.get("memory_gb"))
    out["memory_phrase"] = f"Память: {_fmt(mem)} ГБ. " if isinstance(mem, (int, float)) and mem > 0 else ""

    # Частота GPU.
    clock = _as_num(attrs.get("clock_mhz"))
    out["clock_phrase"] = f"Частота: {_fmt(clock)} МГц. " if isinstance(clock, (int, float)) and clock > 0 else ""

    # Определяем, старая видеокарта или современная.
    old_gpu = _gpu_is_old(attrs)

    if old_gpu:
        # Для старых моделей берутся отдельные фразы и прилагательные.
        values = phrases.get("gpu_use_case_old", [])
        feats = phrases.get("gpu_features_old", [])
        adjs = phrases.get("adj_gpu_old", [])
    else:
        # Для современных моделей берутся более сильные фразы.
        values = phrases.get("gpu_use_case", [])
        feats = phrases.get("gpu_features", [])
        adjs = phrases.get("adj_gpu_modern", [])

    # Случайно выбираем фразы из нужного набора.
    out["gpu_use_case_phrase"] = (rng.choice(values).strip() + ". ") if values else ""
    out["gpu_feature_phrase"] = (rng.choice(feats).strip() + ". ") if feats else ""
    out["gpu_adj"] = rng.choice(adjs).strip() if adjs else ""

    # Пользовательская особенность.
    feat = attrs.get("key_feature")
    fs = feat.strip() if isinstance(feat, str) else ""
    out["feature_phrase"] = f"Особенность — {fs}. " if fs else ""

    return out


# Список категорий, которые генератор умеет обрабатывать.
SUPPORTED_CATEGORIES = {"smartphone", "sneakers", "gpu"}


def load_assets(base_dir: Union[str, Path, None] = None) -> Tuple[dict, dict]:
    """Загружает шаблоны и фразы из папки templates."""
    if base_dir is None:
        # Если base_dir не передан, берем папку, где лежит generator_engine.py.
        base_dir = Path(__file__).parent
    base_dir = Path(base_dir)

    # templates.json содержит шаблоны описаний.
    templates = _load_json(base_dir / "templates" / "templates.json")
    # phrases.json содержит словари фраз и прилагательных.
    phrases = _load_json(base_dir / "templates" / "phrases.json")
    return templates, phrases


def normalize_input(payload: dict) -> dict:
    """Приводит входные данные API к стандартному формату.

    На вход может прийти JSON вида:
    {"category": "smartphone", "brand": "Samsung", ...}

    Или вида:
    {"category": "smartphone", "attributes": {"brand": "Samsung", ...}}

    На выходе всегда будет:
    {"category": "smartphone", "attributes": {...}}
    """
    if not isinstance(payload, dict):
        raise ValueError("Неверный формат запроса")

    # Категория обязательна.
    category = (payload.get("category") or "").strip()
    if not category:
        raise ValueError("Не указана category")

    # Проверяем, что категория входит в список поддерживаемых.
    if category not in SUPPORTED_CATEGORIES:
        raise ValueError(f"Неподдерживаемая категория: {category}")

    # Если есть вложенный attributes, используем его.
    if isinstance(payload.get("attributes"), dict):
        attrs = payload["attributes"] or {}
    else:
        # Иначе все поля, кроме category и seed, считаются характеристиками товара.
        attrs = {k: v for k, v in payload.items() if k not in {"category", "seed"}}

    # Поля, которые должны быть числами.
    numeric_fields = ["ram_gb", "storage_gb", "screen_size_in", "battery_mah",
                      "camera_mp", "size_eu", "memory_gb", "clock_mhz"]
    for k in numeric_fields:
        if k in attrs:
            n = _as_num(attrs[k])
            if n is not None:
                attrs[k] = n

    return {"category": category, "attributes": attrs}


def generate_description(item: dict, templates: dict, phrases: dict, seed: Union[int, None] = None) -> str:
    """Главная функция генерации описания товара.

    Алгоритм:
    1. Создать генератор случайности с seed.
    2. Получить category и attributes.
    3. Выбрать случайный шаблон для категории.
    4. Сформировать словарь values для подстановки.
    5. Для конкретной категории собрать дополнительные текстовые блоки.
    6. Добавить CTA-фразу.
    7. Подставить values в шаблон.
    8. Очистить текст и вернуть результат.
    """
    # seed нужен, чтобы при одном и том же seed результат повторялся.
    rng = random.Random(seed)

    category = (item.get("category") or "").strip()
    attrs: Dict[str, Any] = item.get("attributes", {}) or {}

    # Если шаблонов для категории нет, генерация невозможна.
    if category not in templates:
        raise ValueError("Unknown category: " + category)

    # Выбираем один шаблон из списка шаблонов данной категории.
    template = rng.choice(templates[category])

    # values — все переменные, которые будут доступны в шаблоне.
    values: Dict[str, Any] = {}
    for k, v in attrs.items():
        values[k] = _fmt(v)

    # Категория определяет, какую функцию сборки текстовых блоков вызвать.
    if category == "gpu":
        gpu_block = _build_gpu(attrs, phrases, rng)
        values.update(gpu_block)
        values["adj"] = _get_adjective_for_category("gpu", gpu_block.get("gpu_adj", ""))
    elif category == "smartphone":
        smartphone_block = _build_smartphone(attrs, phrases, rng)
        values.update(smartphone_block)
        raw_adj = rng.choice(phrases.get("adj", ["Современный"]))
        values["adj"] = _get_adjective_for_category("smartphone", raw_adj)
    elif category == "sneakers":
        sneakers_block = _build_sneakers(attrs, phrases, rng)
        values.update(sneakers_block)
        raw_adj = rng.choice(phrases.get("adj", ["Современные"]))
        values["adj"] = _get_adjective_for_category("sneakers", raw_adj)

    # CTA — финальный призыв к действию, например "Закажите онлайн с доставкой."
    cta_list = phrases.get("cta", [])
    values["cta"] = (rng.choice(cta_list).strip() if cta_list else "")

    # Подставляем values в шаблон. SafeDict защищает от отсутствующих ключей.
    text = template.format_map(SafeDict(values))

    # Возвращаем очищенный текст.
    return _clean_text(text)

