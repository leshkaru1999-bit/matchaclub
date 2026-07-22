import pandas as pd
import json
import os

# Load existing menu items
menu_path = 'data/menu.json'
existing_items = set()
with open(menu_path, 'r', encoding='utf-8') as f:
    menu_data = json.load(f)
    for cat in menu_data.get('categories', []):
        for item in cat.get('items', []):
            name = item.get('name', '').strip().lower()
            if name:
                existing_items.add(name)

files = [
    r"C:\Users\leshk\Downloads\Telegram Desktop\меню кухня и десерты корнер (5) (2).xlsx",
    r"C:\Users\leshk\OneDrive\Desktop\Бефит\меню бар кбжу.xlsx",
    r"C:\Users\leshk\Downloads\новое меню.xlsx",
    r"C:\Users\leshk\Downloads\Telegram Desktop\новыя барная карта (2).xlsx"
]

missing_items = []

for file_path in files:
    if not os.path.exists(file_path):
        continue
    try:
        xl = pd.ExcelFile(file_path)
        for sheet in xl.sheet_names:
            df = pd.read_excel(file_path, sheet_name=sheet, header=None)
            for i, row in df.iterrows():
                vals = [str(v).strip() for v in row if pd.notna(v) and str(v).strip() and str(v).strip() != 'nan']
                if not vals:
                    continue
                
                # The name is usually the first or second string.
                # Let's check the first string, if it's "Название", skip.
                name_candidate = None
                for v in vals[:2]:
                    # Ignore headers
                    if v.lower() in ['наименование', 'десерты и печенье', 'напитки', 'матча', 'название', 'состав', 'кбжу', 'белки']:
                        continue
                    # A reasonable dish name is usually between 3 and 50 characters, and doesn't contain a lot of numbers.
                    if 2 < len(v) < 60 and not v.replace('.','',1).isdigit():
                        name_candidate = v
                        break
                
                if name_candidate:
                    norm_name = name_candidate.lower()
                    if norm_name not in existing_items and norm_name not in [m.lower() for m in missing_items]:
                        # Quick heuristic to avoid adding pure compositions as names
                        if len(norm_name.split(',')) < 4:
                            missing_items.append(name_candidate)
    except Exception as e:
        pass

with open('missing.txt', 'w', encoding='utf-8') as f:
    f.write("=== ПОЗИЦИИ ИЗ EXCEL, КОТОРЫХ НЕТ В МЕНЮ БОТА ===\n")
    for item in missing_items:
        f.write(f"- {item}\n")
