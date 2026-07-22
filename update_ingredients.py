import pandas as pd
import json
import os

menu_path = 'data/menu.json'
with open(menu_path, 'r', encoding='utf-8') as f:
    menu_data = json.load(f)

# Collect all items from excel files
items_dict = {}

def parse_excel(file_path):
    if not os.path.exists(file_path):
        print(f"Not found: {file_path}")
        return
    print(f"Parsing {file_path}")
    try:
        xl = pd.ExcelFile(file_path)
        for sheet in xl.sheet_names:
            df = pd.read_excel(file_path, sheet_name=sheet, header=None)
            for i, row in df.iterrows():
                vals = [str(v).strip() for v in row if pd.notna(v) and str(v).strip()]
                if len(vals) >= 2:
                    # heuristic: look for a known name, or assume col 0/1 is name and the longest string is composition
                    # We will just print them out for now to see the structure
                    pass
    except Exception as e:
        print(f"Error parsing {file_path}: {e}")

f1 = r"C:\Users\leshk\Downloads\Telegram Desktop\меню кухня и десерты корнер (5) (2).xlsx"
f2 = r"C:\Users\leshk\OneDrive\Desktop\Бефит\меню бар кбжу.xlsx"
f3 = r"C:\Users\leshk\Downloads\новое меню.xlsx"
f4 = r"C:\Users\leshk\Downloads\Telegram Desktop\новыя барная карта (2).xlsx"

parse_excel(f1)
parse_excel(f2)
parse_excel(f3)
parse_excel(f4)
