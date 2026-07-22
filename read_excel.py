"""Script to read Excel menu files and convert to JSON for the bot."""
import pandas as pd
import json
import os
import sys

# Force UTF-8
sys.stdout.reconfigure(encoding='utf-8')

output = {}

# File 1: Kitchen desserts
f1 = r"C:\Users\leshk\Downloads\Telegram Desktop\меню кухня и десерты корнер (5) (2).xlsx"
if os.path.exists(f1):
    print(f"Reading: {os.path.basename(f1)}")
    xl = pd.ExcelFile(f1)
    for sheet in xl.sheet_names:
        print(f"\n=== Sheet: {sheet} ===")
        df = pd.read_excel(f1, sheet_name=sheet, header=None)
        for i, row in df.iterrows():
            vals = [str(v) if pd.notna(v) else "" for v in row]
            if any(v.strip() for v in vals):
                print(f"Row {i}: {' | '.join(vals)}")

print("\n\n" + "="*80)

# File 2: Bar KBZHU
f2 = r"C:\Users\leshk\OneDrive\Desktop\Бефит\меню бар кбжу.xlsx"
if os.path.exists(f2):
    print(f"\nReading: {os.path.basename(f2)}")
    xl = pd.ExcelFile(f2)
    for sheet in xl.sheet_names:
        print(f"\n=== Sheet: {sheet} ===")
        df = pd.read_excel(f2, sheet_name=sheet, header=None)
        for i, row in df.iterrows():
            vals = [str(v) if pd.notna(v) else "" for v in row]
            if any(v.strip() for v in vals):
                print(f"Row {i}: {' | '.join(vals)}")

print("\n\n" + "="*80)

# File 3: New menu
f3 = r"C:\Users\leshk\Downloads\новое меню.xlsx"
if os.path.exists(f3):
    print(f"\nReading: {os.path.basename(f3)}")
    xl = pd.ExcelFile(f3)
    for sheet in xl.sheet_names:
        print(f"\n=== Sheet: {sheet} ===")
        df = pd.read_excel(f3, sheet_name=sheet, header=None)
        for i, row in df.iterrows():
            vals = [str(v) if pd.notna(v) else "" for v in row]
            if any(v.strip() for v in vals):
                print(f"Row {i}: {' | '.join(vals)}")

print("\n\n" + "="*80)

# File 4: New bar menu
f4 = r"C:\Users\leshk\Downloads\Telegram Desktop\новыя барная карта (2).xlsx"
if os.path.exists(f4):
    print(f"\nReading: {os.path.basename(f4)}")
    xl = pd.ExcelFile(f4)
    for sheet in xl.sheet_names:
        print(f"\n=== Sheet: {sheet} ===")
        df = pd.read_excel(f4, sheet_name=sheet, header=None)
        for i, row in df.iterrows():
            vals = [str(v) if pd.notna(v) else "" for v in row]
            if any(v.strip() for v in vals):
                print(f"Row {i}: {' | '.join(vals)}")
