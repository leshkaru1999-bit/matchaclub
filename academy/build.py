# -*- coding: utf-8 -*-
"""Сборка Академии Matcha Club.

  python academy/build.py bot   — записать тренинги в data/trainings.json и вопросы в data/quiz.json
  python academy/build.py pdf   — собрать PDF-учебник из data/trainings.json
  python academy/build.py all   — и то, и другое

Тренинги из content.py заменяют одноимённые (по id) в trainings.json,
остальные тренинги (добавленные через админку бота) сохраняются.
Вопросы квиза добавляются, только если такого вопроса ещё нет.
"""
import html
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
sys.path.insert(0, HERE)
from content import ACADEMY_VERSION, TRAININGS  # noqa: E402

VERSION_FILE = os.path.join(DATA, "academy_version.txt")


def load(name):
    with open(os.path.join(DATA, name), encoding="utf-8") as f:
        return json.load(f)


def save(name, data):
    with open(os.path.join(DATA, name), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def sync_bot():
    tr = load("trainings.json")
    existing = tr.get("trainings", [])
    ours = [{k: v for k, v in t.items() if k != "quiz"} for t in TRAININGS]
    our_ids = {t["id"] for t in ours}
    others = [t for t in existing if t.get("id") not in our_ids]
    tr["trainings"] = ours + others
    save("trainings.json", tr)

    quiz = load("quiz.json")
    qs = quiz["questions"]
    seen = {q["question"].strip() for q in qs}
    next_id = max((q["id"] for q in qs), default=0) + 1
    added = 0
    for t in TRAININGS:
        for q in t.get("quiz", []):
            if q["question"].strip() in seen:
                continue
            qs.append({"id": next_id, **q})
            seen.add(q["question"].strip())
            next_id += 1
            added += 1
    save("quiz.json", quiz)
    with open(VERSION_FILE, "w", encoding="utf-8") as f:
        f.write(str(ACADEMY_VERSION))
    n_mod = sum(len(t["modules"]) for t in ours)
    print(f"Бот: {len(ours)} тренингов / {n_mod} модулей записано, всего тренингов {len(tr['trainings'])}; "
          f"квиз +{added} вопросов (всего {len(qs)})")


def sync_if_new():
    """Вызывается ботом при запуске: применяет базу, только если вышла новая версия.
    Так правки модулей через админку не затираются при каждом перезапуске."""
    try:
        with open(VERSION_FILE, encoding="utf-8") as f:
            applied = int(f.read().strip() or 0)
    except (OSError, ValueError):
        applied = 0
    if applied >= ACADEMY_VERSION:
        return False
    sync_bot()
    return True


# ---------------- PDF ----------------
CSS = r"""
:root{--brand:#454C7F;--ink:#292D4C;--cream:#FFF9E9;--paper:#FFFDF6;--matcha:#6F8F4E;--matcha-soft:#E9EEDB;
--brand-soft:#E6E7F1;--line:#E6DEC6;--muted:#6C6F8C;--red:#A5483F;--red-soft:#F6E4DF}
@page{size:A4;margin:18mm 17mm 18mm;background:#FFF9E9;
 @bottom-left{content:"Академия Matcha Club";font:7pt 'Manrope',sans-serif;color:#6C6F8C;letter-spacing:.12em;text-transform:uppercase}
 @bottom-right{content:counter(page);font:7pt 'Manrope',sans-serif;color:#6C6F8C}}
@page cover{margin:0;@bottom-left{content:none}@bottom-right{content:none}}
*{box-sizing:border-box;margin:0;padding:0}
html,body{background:var(--cream)}
body{font-family:'Manrope',Arial,sans-serif;color:var(--ink);font-size:9.6pt;line-height:1.6;-webkit-print-color-adjust:exact;print-color-adjust:exact}
h1,h2,h3{font-family:'Cormorant Garamond',Georgia,serif;font-weight:600;color:var(--brand)}
.cover{page:cover;height:297mm;background:var(--brand);color:var(--cream);display:flex;flex-direction:column;align-items:center;justify-content:space-between;text-align:center;padding:30mm 20mm 24mm;break-after:page}
.cover img{width:110mm}
.cover .t{font-family:'Cormorant Garamond',serif;font-size:44pt;font-style:italic;font-weight:500;line-height:1}
.cover .s{font-size:8pt;letter-spacing:.3em;text-transform:uppercase;opacity:.8}
.circle{width:44mm;height:44mm;border-radius:50%;border:1px solid rgba(255,249,233,.4);display:flex;align-items:center;justify-content:center}
.circle div{width:30mm;height:30mm;border-radius:50%;background:var(--matcha)}
.kicker{font-size:7.5pt;letter-spacing:.2em;text-transform:uppercase;color:var(--matcha);font-weight:700;margin-bottom:2mm}
.toc{break-after:page}
.toc h1{font-size:30pt;margin-bottom:8mm}
.toc-row{display:grid;grid-template-columns:14mm 1fr auto;align-items:baseline;padding:3.5mm 0;border-bottom:1px solid var(--line)}
.toc-row .n{font-family:'Cormorant Garamond',serif;font-weight:700;color:var(--matcha);font-size:18pt}
.toc-row .t{font-family:'Cormorant Garamond',serif;font-size:16pt;font-weight:600}
.toc-row .t small{display:block;font-family:'Manrope',sans-serif;font-size:8pt;color:var(--muted);font-weight:400}
.toc-row .m{font-size:8pt;color:var(--muted)}
.howto{margin-top:9mm;background:var(--paper);border:1px solid var(--line);border-radius:4mm;padding:5mm 6mm}
.howto h3{font-size:14pt;margin-bottom:2mm}
.training{break-before:page}
.t-head{background:var(--brand);color:var(--cream);border-radius:5mm;padding:9mm 9mm 8mm;margin-bottom:7mm;position:relative;overflow:hidden}
.t-head .big{position:absolute;right:6mm;top:-6mm;font-family:'Cormorant Garamond',serif;font-size:90pt;font-weight:600;color:rgba(255,249,233,.14);line-height:1}
.t-head h1{color:var(--cream);font-size:30pt;line-height:1.05;margin-bottom:2mm;max-width:140mm}
.t-head p{opacity:.85;max-width:135mm}
.t-head .kicker{color:#C9D8AC}
.module{margin-bottom:6mm}
.module h2{font-size:17pt;line-height:1.15;margin-bottom:2.5mm;break-after:avoid;border-top:1px solid var(--line);padding-top:4mm}
.module:first-of-type h2{border-top:0;padding-top:0}
.body p{margin-bottom:2.2mm}
.body ul{margin:0 0 2.5mm 5mm}
.body li{margin-bottom:1.2mm}
.body b{color:var(--brand)}
.formula-box{background:var(--ink);color:var(--cream);border-radius:3mm;padding:3.5mm 5mm;margin:3mm 0;font-family:'Cormorant Garamond',serif;font-size:13pt;font-weight:600;text-align:center;break-inside:avoid}
.quote-callout{border-left:3px solid var(--matcha);background:var(--matcha-soft);padding:3mm 4.5mm;border-radius:0 3mm 3mm 0;margin:3mm 0;font-style:italic;break-inside:avoid}
.compare-row{display:grid;grid-template-columns:1fr 1fr;gap:2.5mm;margin:2.5mm 0;break-inside:avoid}
.compare-bad,.compare-good{border-radius:2.5mm;padding:2.5mm 3.5mm;font-size:9pt}
.compare-bad{background:var(--red-soft);color:#6d322c}
.compare-good{background:var(--matcha-soft);color:#34462a}
.compare-row>.compare-good:only-child{grid-column:1/-1}
.compare-tag{display:none}
.compare-bad:before{content:"Так не говорим";display:block;font-size:6.5pt;letter-spacing:.12em;text-transform:uppercase;font-weight:700;color:var(--red);margin-bottom:.8mm}
.compare-good:before{content:"Так говорим";display:block;font-size:6.5pt;letter-spacing:.12em;text-transform:uppercase;font-weight:700;color:var(--matcha);margin-bottom:.8mm}
.compare-effect{grid-column:1/-1;font-size:8.3pt;color:var(--muted)}
.taboo-card{background:var(--red-soft);border:1px solid #E7C3BA;border-radius:3mm;padding:3mm 4mm;margin:2.5mm 0;break-inside:avoid}
.taboo-card b{color:var(--red)!important}
.exercise-card{background:var(--paper);border:1px solid var(--line);border-radius:3mm;padding:3.5mm 4.5mm;margin:2.5mm 0;break-inside:avoid}
.exercise-card>p:first-child{margin-bottom:1.5mm}
.reveal-btn{display:none}
.reveal-answer{border-top:1px dashed var(--line);padding-top:2mm;margin-top:1mm;color:#34462a}
.reveal-answer:before{content:"Ответ / разбор: ";font-weight:700;color:var(--matcha)}
.quiz{margin-top:6mm;background:var(--brand-soft);border-radius:4mm;padding:5mm 6mm;break-inside:auto}
.quiz h3{font-size:15pt;margin-bottom:2.5mm}
.quiz ol{margin-left:5mm}
.quiz li{margin-bottom:2.2mm;break-inside:avoid}
.quiz .opts{font-size:8.6pt;color:var(--muted)}
.keys{break-before:page}
.keys h1{font-size:26pt;margin-bottom:5mm}
.keys h3{font-size:13pt;margin:4mm 0 1.5mm}
.keys li{font-size:8.6pt;margin:0 0 1.2mm 5mm}
"""


def strip_emoji(s):
    return re.sub(r"[\U0001F300-\U0001FAFF\u2600-\u27BF\uFE0F]", "", s).strip()


def build_pdf():
    trainings = load("trainings.json")["trainings"]
    quiz_by_training = {t["id"]: t.get("quiz", []) for t in TRAININGS}
    parts = [f"<!DOCTYPE html><html lang='ru'><head><meta charset='utf-8'><title>Академия Matcha Club</title>"
             "<link href='https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,500;0,600;0,700;1,500"
             "&family=Manrope:wght@400;500;600;700&display=block' rel='stylesheet'>"
             f"<style>{CSS}</style></head><body>"]
    logo = "file:///" + os.path.join(ROOT, "welcome_book", "logo_white.png").replace("\\", "/")
    parts.append(f"<section class='cover'><div class='s'>Учебная программа сотрудника</div>"
                 f"<img src='{logo}'><div class='circle'><div></div></div>"
                 f"<div><div class='t'>Академия<br>Matcha Club</div>"
                 f"<div class='s' style='margin-top:5mm'>Стандарты · wellness-питание · матча · гости · продажи · сервис</div></div></section>")
    toc = ["<section class='toc'><div class='kicker'>Программа</div><h1>Что вы изучите</h1>"]
    for i, t in enumerate(trainings, 1):
        toc.append(f"<div class='toc-row'><span class='n'>{i:02d}</span><span class='t'>{html.escape(strip_emoji(t['title']))}"
                   f"<small>{html.escape(t.get('subtitle', ''))}</small></span><span class='m'>{len(t.get('modules', []))} мод.</span></div>")
    toc.append("<div class='howto'><h3>Как проходить Академию</h3><ul style='margin-left:5mm'>"
               "<li>Проходите тренинги по порядку — в боте Matcha Club (раздел «Тренинги») или по этому учебнику.</li>"
               "<li>После каждого тренинга отвечайте на вопросы «Проверьте себя». Ответы — в конце учебника.</li>"
               "<li>Практику отрабатывайте вслух с наставником — продажи учатся только разговором.</li>"
               "<li>Аттестация — квиз в боте. База пополняется: новые модули появляются в боте автоматически.</li></ul></div></section>")
    parts += toc
    keys = ["<section class='keys'><div class='kicker'>Для самопроверки</div><h1>Ответы на вопросы</h1>"]
    for i, t in enumerate(trainings, 1):
        parts.append(f"<section class='training'><div class='t-head'><div class='big'>{i:02d}</div>"
                     f"<div class='kicker'>Тренинг {i}</div><h1>{html.escape(strip_emoji(t['title']))}</h1>"
                     f"<p>{html.escape(t.get('subtitle', ''))}</p></div>")
        for m in t.get("modules", []):
            parts.append(f"<div class='module'><h2>{html.escape(m['title'])}</h2><div class='body'>{m.get('content', '')}</div></div>")
        qz = quiz_by_training.get(t["id"], [])
        if qz:
            parts.append("<div class='quiz'><h3>Проверьте себя</h3><ol>")
            keys.append(f"<h3>{i:02d}. {html.escape(strip_emoji(t['title']))}</h3><ol>")
            for q in qz:
                opts = " · ".join(f"{'абвг'[k]}) {html.escape(o)}" for k, o in enumerate(q["options"]))
                parts.append(f"<li><b>{html.escape(q['question'])}</b><div class='opts'>{opts}</div></li>")
                keys.append(f"<li><b>{'абвг'[q['correct']]})</b> {html.escape(q['explanation'])}</li>")
            parts.append("</ol></div>")
            keys.append("</ol>")
        parts.append("</section>")
    keys.append("</section>")
    parts += keys
    parts.append("</body></html>")

    src = os.path.join(HERE, "academy.html")
    with open(src, "w", encoding="utf-8") as f:
        f.write("".join(parts))
    out = os.path.join(HERE, "Академия Matcha Club.pdf")
    chrome = next(p for p in [r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                              r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"] if os.path.exists(p))
    subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                    "--virtual-time-budget=15000", "--allow-file-access-from-files",
                    f"--print-to-pdf={out}", "file:///" + src.replace("\\", "/")], check=True)
    print("PDF:", out)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    if cmd in ("bot", "all"):
        sync_bot()
    if cmd in ("pdf", "all"):
        build_pdf()
