# Сборка карточек к тренингу 4: python academy/plans/build_cards_4.py out.html, затем печать в PDF через Chrome.
# Шрифты подключаются вместо плейсхолдера FONTS (Google Fonts или локальный CSS).
import html, sys
out = sys.argv[1]
E = html.escape

MIME = [
 ("Влетает с телефоном у уха, кивает на меню, постукивает картой по стойке", "Решительный"),
 ("Смотрит на часы, сразу идёт к кассе, не смотрит на витрину", "Решительный"),
 ("Улыбается, фотографирует витрину, зовёт подругу посмотреть", "Эмоциональный"),
 ("Разглядывает интерьер, машет бариста, восхищённо показывает на десерт", "Эмоциональный"),
 ("Долго стоит у витрины, отходит, возвращается, неуверенно поднимает палец", "Осторожный"),
 ("Тихо пропускает других вперёд, смотрит в пол, теребит кошелёк", "Осторожный"),
 ("Берёт карточку меню, внимательно читает, водит пальцем по строчкам", "Аналитик"),
 ("Наклоняется к ценнику, щурится, что-то считает в телефоне", "Аналитик"),
]
MYSTERY = [
 ("Решительный", "Спорт и белок", "Утро, на бегу", "«Мне что-то с белком, с собой, быстро»", "Говорите коротко, смотрите на часы. Длинный ответ вас раздражает."),
 ("Аналитик", "Ограничения", "Один", "«А в этом точно нет лактозы? А подсластитель какой?»", "Уточняйте состав, переспрашивайте. «Вкусно» вас не убеждает."),
 ("Эмоциональный", "Красота и эстетика", "С подругой", "«Хотим что-нибудь красивое и необычное!»", "Улыбайтесь, восхищайтесь витриной, достаньте телефон для фото."),
 ("Осторожный", "Первый раз у нас", "Один", "«Я не знаю… а что такое матча?»", "Говорите тихо, сомневайтесь. Если предложат много вариантов — растеряйтесь."),
 ("Аналитик", "Контроль веса", "Обед", "«Сколько калорий в боуле? А что легче?»", "Спрашивайте цифры. Если цифр нет — отказывайтесь."),
 ("Эмоциональный", "Порадовать себя", "Свидание", "«Хотим десерт, что-нибудь особенное»", "Говорите с партнёром, переглядывайтесь, не любите, когда вас часто отвлекают."),
 ("Решительный", "Энергия и продуктивность", "Деловая встреча", "«Два кофе и что-нибудь перекусить, у нас 20 минут»", "Продолжайте разговор с коллегой, отвечайте коротко."),
 ("Осторожный", "Постоянный гость", "Один", "«Как в прошлый раз… не помню, что брал»", "Вы были здесь много раз. Обрадуйтесь, если вас узнают."),
 ("Аналитик", "Спорт и белок", "После тренировки", "«Где больше всего белка? Сколько грамм?»", "Сравнивайте позиции, просите точные цифры."),
 ("Эмоциональный", "Порадовать себя", "Один", "«Тяжёлая неделя, хочу чего-то вкусного!»", "Рассказывайте про неделю, ждите сочувствия и тёплого совета."),
 ("Осторожный", "Ограничения", "Мама с ребёнком", "«А ребёнку что-нибудь можно? Только без кофе»", "Отвлекайтесь на ребёнка, волнуйтесь, что ему можно."),
 ("Решительный", "Ограничения", "Утро", "«Латте без коровьего молока. С собой»", "Говорите быстро. Не хотите слушать про все виды молока подряд."),
]
ITEMS = [
 ("Брауни", "Миндальная мука, тёмный шоколад без сахара, без глютена · аллерген: орехи"),
 ("Матча манго", "Корейская матча, кокосовое молоко, пюре манго · без лактозы"),
 ("Сэндвич с лососем", "Хлеб из гречневой муки, лосось, авокадо · без глютена"),
 ("Протеиновый чизкейк", "Творог, сироп агавы, ягоды · 16 г белка"),
 ("Матча тоник", "Японская матча, тоник, ананас, лемонграсс, мята · около 55 ккал"),
 ("Тирамису", "Безглютеновая мука, маскарпоне · на стевии, без сахара"),
 ("Боул с тунцом", "Тунец, киноа, авокадо, эдамаме, перепелиные яйца · 45 г белка"),
 ("Матча клубника", "Корейская матча, клубника, сироп агавы, безлактозное молоко"),
]

def page(cards, title, note):
    return (f'<section class="sheet"><div class="ph"><b>{E(title)}</b><span>{E(note)}</span></div>'
            f'<div class="grid">{"".join(cards)}</div></section>')

def chunks(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i+n]

mime = [f'<div class="card mime"><div class="lab">Покажи гостя · пантомима</div>'
        f'<div class="main">{E(t)}</div><div class="hint">Показывать только поведением, без слов · 30 секунд</div>'
        f'<div class="secret">Тип: <b>{E(k)}</b></div></div>' for t, k in MIME]
myst = [f'<div class="card myst"><div class="lab">Гость-загадка · №{i}</div>'
        f'<div class="tags"><span class="t1">{E(a)}</span><span class="t2">{E(b)}</span><span class="t3">{E(c)}</span></div>'
        f'<div class="main q">{E(p)}</div><div class="hint">Как играть: {E(h)}</div>'
        f'<div class="secret">Карточку сотруднику не показывать до конца раунда</div></div>'
        for i, (a, b, c, p, h) in enumerate(MYSTERY, 1)]
myst += ['<div class="card myst"><div class="lab">Гость-загадка · свой сценарий</div>'
         '<div class="blank">Тип: ______________________</div><div class="blank">Мотив: ____________________</div>'
         '<div class="blank">Ситуация: _________________</div><div class="blank">Фраза: ____________________</div>'
         '<div class="secret">Заполните по реальному гостю из своей смены</div></div>'] * 4
items = [f'<div class="card item"><div class="lab">Одна позиция — четыре подачи</div>'
         f'<div class="main big">{E(n)}</div><div class="hint">{E(d)}</div>'
         f'<div class="four"><span>Решительному</span><span>Эмоциональному</span><span>Осторожному</span><span>Аналитику</span></div></div>'
         for n, d in ITEMS]

pages = []
for c in chunks(mime, 8): pages.append(page(c, "Карточки «Покажи гостя»", "Разминка · 8 карточек · тип внизу видит только показывающий"))
for c in chunks(myst, 8): pages.append(page(c, "Карточки «Гость-загадка»", "Ролевки в тройках · 12 карточек + 4 пустых"))
for c in chunks(items, 8): pages.append(page(c, "Карточки «Одна позиция — четыре подачи»", "Игра к модулю «Четыре психотипа» · 8 карточек"))

CSS = """
:root{--brand:#454C7F;--ink:#292D4C;--cream:#FFF9E9;--paper:#FFFDF6;--matcha:#6F8F4E;--matcha-soft:#E9EEDB;--brand-soft:#E6E7F1;--line:#E6DEC6;--muted:#6C6F8C;--red:#A5483F;--red-soft:#F6E4DF}
@page{size:A4;margin:9mm}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Manrope',Arial,sans-serif;color:var(--ink);-webkit-print-color-adjust:exact;print-color-adjust:exact}
.sheet{break-after:page;height:279mm;display:flex;flex-direction:column}
.sheet:last-child{break-after:auto}
.ph{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:3mm;font-size:7pt;color:var(--muted)}
.ph b{font-family:'Cormorant Garamond',Georgia,serif;font-size:14pt;color:var(--brand)}
.grid{flex:1;display:grid;grid-template-columns:1fr 1fr;grid-template-rows:repeat(4,1fr);border-top:1px dashed #A9A08A;border-left:1px dashed #A9A08A}
.card{border-right:1px dashed #A9A08A;border-bottom:1px dashed #A9A08A;padding:5mm 6mm;display:flex;flex-direction:column;gap:2.5mm;position:relative;background:var(--paper)}
.lab{font-size:6.5pt;letter-spacing:.18em;text-transform:uppercase;font-weight:700;color:var(--matcha)}
.myst .lab{color:var(--brand)}.item .lab{color:var(--red)}
.main{font-size:11.5pt;font-weight:600;line-height:1.35;flex:1;display:flex;align-items:center}
.main.q{font-family:'Cormorant Garamond',Georgia,serif;font-size:15pt;font-style:italic;font-weight:600;color:var(--brand)}
.main.big{font-family:'Cormorant Garamond',Georgia,serif;font-size:22pt;font-weight:700;color:var(--brand)}
.hint{font-size:7.6pt;color:var(--muted);line-height:1.4}
.secret{font-size:7pt;color:var(--muted);border-top:1px solid var(--line);padding-top:1.5mm}
.secret b{color:var(--red);font-size:8.5pt}
.blank{font-size:9pt;color:var(--muted);flex:1;display:flex;align-items:center}
.tags{display:flex;flex-wrap:wrap;gap:1.5mm}
.tags span{font-size:7.5pt;font-weight:700;border-radius:10mm;padding:.8mm 2.5mm}
.t1{background:var(--brand);color:var(--cream)}.t2{background:var(--matcha-soft);color:#34462a}.t3{background:var(--brand-soft);color:var(--brand)}
.four{display:grid;grid-template-columns:1fr 1fr;gap:1.2mm}
.four span{font-size:6.8pt;border:1px solid var(--line);border-radius:1.5mm;padding:1mm 1.5mm;color:var(--muted);min-height:7mm}
"""
doc = (f"<!DOCTYPE html><html lang='ru'><head><meta charset='utf-8'><title>Карточки — Психотипы гостей</title>"
       f"<link rel='stylesheet' href='FONTS'><style>{CSS}</style></head><body>{''.join(pages)}</body></html>")
open(out, "w", encoding="utf-8").write(doc)
