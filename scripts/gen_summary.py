#!/usr/bin/env python3
"""gen_summary.py — авто-генерация _SUMMARY.md"""
from __future__ import annotations

import sys
import re
from pathlib import Path
from datetime import datetime

# Force UTF-8 на Windows
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = ROOT / "docs"
OUTPUT_FILE = DOCS_DIR / "_SUMMARY.md"


def extract_metadata(text):
    """Извлекает заголовок, версию, дату из текста .md файла"""
    lines = text.split('\n')
    title = ""
    version = ""
    date = ""

    for line in lines[:10]:
        if line.startswith('# ') and not title:
            title = line[2:].strip()
        if '**Версия:**' in line:
            m = re.search(r'\*\*Версия:\*\*\s*([\d.]+)', line)
            if m:
                version = m.group(1)
        if '**Последнее обновление:**' in line or '**Дата:**' in line:
            m = re.search(r'\*\*(?:Последнее обновление|Дата):\*\*\s*(\d{4}-\d{2}-\d{2})', line)
            if m:
                date = m.group(1)

    return title, version, date


def main():
    docs = []
    for md_file in sorted(DOCS_DIR.glob("*.md")):
        if md_file.name.startswith('_'):
            continue
        text = md_file.read_text(encoding='utf-8')
        title, version, date = extract_metadata(text)
        if not title:
            title = md_file.stem
        docs.append((md_file.name, title, version, date))

    lines = [
        "# Авто-индекс документации\n",
        f"**Сгенерировано:** {datetime.now().strftime('%Y-%m-%d')}\n",
        "\n> Этот файл генерируется автоматически. Не редактировать вручную.\n",
        "\n## Документы\n",
    ]

    for name, title, version, date in docs:
        meta = []
        if version:
            meta.append(f"v{version}")
        if date:
            meta.append(date)
        meta_str = f" ({', '.join(meta)})" if meta else ""
        lines.append(f"- [{title}]({name}){meta_str}\n")

    OUTPUT_FILE.write_text(''.join(lines), encoding='utf-8')
    print(f"Generated: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
