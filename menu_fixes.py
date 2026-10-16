"""Разовые исправления меню (data/menu.json на сервере).

Каждый набор правок применяется один раз при запуске бота — отметка хранится
в data/menu_fixes_applied.json. Поэтому правки, сделанные потом через админку,
не затираются. Новый набор правок — новый элемент FIX_SETS с новым id.
"""
import json
import os
import re

# Опечатки, которые правим во всех блюдах (состав, описание, аллергены)
_TYPOS = [
    (r'молоко без лактоза', 'безлактозное молоко'),
    (r'молоком без лактоза', 'безлактозным молоком'),
    (r'сливки кокосвые', 'кокосовые сливки'),
    (r'\bананс\b', 'ананас'),
    (r'\bцикини\b', 'цукини'),
    (r'гвакуамоле', 'гвакамоле'),
    (r'запеченых', 'запечённых'),
    (r'запеченые', 'запечённые'),
    (r'\bросбиф\b', 'ростбиф'),
    (r'клоу слоу без заправка', 'коул-слоу без заправки'),
    (r'халапенью', 'халапеньо'),
    (r'подается с орехами грецких и ягодами', 'подаётся с грецкими орехами и ягодами'),
    (r'густой густой', 'густой'),
    (r'\bсгущенку\b', 'сгущёнка'),
    (r',\s*и мак\s*,', ', мак,'),
]

FIX_SETS = [
    {
        "id": "2026-10-16-guest-menu",
        "typos": _TYPOS,
        "items": {
            "Гречка с белыми грибами в сливочном соусе": {
                "ingredients": "Зелёная гречка, сливочный соус, белые грибы, пармезан",
            },
            "Боул с тунцом": {
                "ingredients": "Тунец консервированный, киноа, бобы эдамаме, авокадо, перепелиные яйца, черри, "
                               "огурцы, брокколи, цветная капуста, лимон, редис, кунжутный соус, кунжут",
            },
            "Сэндвич с тунцом": {
                "ingredients": "Тунец консервированный, рисовый хлеб, помидоры, красный лук, руккола, соус цезарь",
            },
            "Поке-боул с лососем": {
                "description": "Сочный запечённый лосось в сочетании со спелым манго, бобами эдамаме, "
                               "свежими огурцами и авокадо. Соус терияки добавляет яркий азиатский акцент.",
                "ingredients": "Запечённый лосось, булгур, бобы эдамаме, свежие огурцы, кунжут, манго, редис, "
                               "зелёный лук, соус терияки, маринованный красный лук, авокадо",
                "allergens": "Глютен, бобы",
            },
            "Фреш-ролл с курицей": {
                "description": "Освежающий ролл в тонком рисовом тесте с нежным куриным филе и хрустящим яблоком. "
                               "Соус цезарь и медово-горчичная заправка создают сочный контраст.",
                "allergens": "Лактоза, мёд, горчица",
            },
            "Авокадо-тост с яйцом пашот и сыром халуми": {
                "description": "Хрустящий тост с авокадо, нежным яйцом пашот и сыром халуми.",
                "ingredients": "Авокадо, яйцо пашот, сыр халуми",
                "price": 115000,
            },
        },
    },
]


def _norm(name):
    return (name or '').strip().rstrip('.').lower().replace('ё', 'е')


def _fix_typos(text, typos):
    if not isinstance(text, str):
        return text
    for pat, repl in typos:
        def sub(m, repl=repl):
            # сохраняем заглавную первую букву
            return repl[0].upper() + repl[1:] if m.group(0)[:1].isupper() else repl
        text = re.sub(pat, sub, text, flags=re.I)
    # висящая запятая в конце состава
    return re.sub(r'[\s,]+$', '', text) if text.rstrip().endswith(',') else text


def apply_fix_set(menu, fix):
    """Применяет набор правок к menu (dict). Возвращает список изменённых блюд."""
    changed = []
    by_name = {_norm(k): v for k, v in fix.get("items", {}).items()}
    for cat in menu.get('categories', []):
        for item in cat.get('items', []):
            before = json.dumps(item, ensure_ascii=False, sort_keys=True)
            for field in ('ingredients', 'description', 'allergens'):
                if field in item:
                    item[field] = _fix_typos(item[field], fix.get("typos", []))
            for field, value in by_name.get(_norm(item.get('name')), {}).items():
                item[field] = value
            if json.dumps(item, ensure_ascii=False, sort_keys=True) != before:
                changed.append(item.get('name'))
    return changed


def apply_pending(data_dir):
    """Применяет ещё не применённые наборы правок к data/menu.json. Возвращает список id применённых."""
    menu_path = os.path.join(data_dir, 'menu.json')
    log_path = os.path.join(data_dir, 'menu_fixes_applied.json')
    try:
        with open(log_path, encoding='utf-8') as f:
            applied = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        applied = []
    pending = [f for f in FIX_SETS if f["id"] not in applied]
    if not pending or not os.path.exists(menu_path):
        return []
    with open(menu_path, encoding='utf-8') as f:
        menu = json.load(f)
    for fix in pending:
        apply_fix_set(menu, fix)
        applied.append(fix["id"])
    with open(menu_path, 'w', encoding='utf-8') as f:
        json.dump(menu, f, ensure_ascii=False, indent=4)
    with open(log_path, 'w', encoding='utf-8') as f:
        json.dump(applied, f, ensure_ascii=False, indent=2)
    return [f["id"] for f in pending]
