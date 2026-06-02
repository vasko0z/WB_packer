#!/usr/bin/env python3
"""bump_version.py — обновление VERSION и синхронизация файлов"""
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
VERSION_FILE = ROOT / "VERSION"

# Файлы, в которых нужно обновлять версию
SYNC_TARGETS = [
    ROOT / "README.md",
    ROOT / "docs" / "README.md",
]


def read_version():
    text = VERSION_FILE.read_text(encoding='utf-8').strip()
    parts = text.split('.')
    return [int(p) for p in parts]


def write_version(major, minor, patch):
    VERSION_FILE.write_text(f"{major}.{minor}.{patch}\n", encoding='utf-8')


def update_file_version(filepath, new_version):
    if not filepath.exists():
        return False
    text = filepath.read_text(encoding='utf-8')
    # Обновляем **Версия:** X.Y.Z
    pattern = r'(\*\*Версия:\*\*\s*)\d+\.\d+(\.\d+)?'
    replacement = r'\g<1>' + new_version
    new_text = re.sub(pattern, replacement, text)
    # Обновляем **Последнее обновление:**
    date_pattern = r'(\*\*Последнее обновление:\*\*\s*)\d{4}-\d{2}-\d{2}'
    date_replacement = r'\g<1>' + datetime.now().strftime('%Y-%m-%d')
    new_text = re.sub(date_pattern, date_replacement, new_text)
    if new_text != text:
        filepath.write_text(new_text, encoding='utf-8')
        return True
    return False


def main():
    if len(sys.argv) < 2:
        print("Usage: python bump_version.py {patch|minor|major|X.Y.Z}")
        sys.exit(1)

    arg = sys.argv[1]
    major, minor, patch = read_version()

    if arg == 'patch':
        patch += 1
    elif arg == 'minor':
        minor += 1
        patch = 0
    elif arg == 'major':
        major += 1
        minor = 0
        patch = 0
    elif re.match(r'^\d+\.\d+\.\d+$', arg):
        major, minor, patch = [int(p) for p in arg.split('.')]
    else:
        print(f"Unknown argument: {arg}")
        sys.exit(1)

    new_version = f"{major}.{minor}.{patch}"
    write_version(major, minor, patch)
    print(f"VERSION updated: {new_version}")

    updated = []
    for target in SYNC_TARGETS:
        if update_file_version(target, new_version):
            updated.append(target.name)
            print(f"  Synced: {target.name}")

    if updated:
        print(f"\nDon't forget to commit: git add VERSION {' '.join(updated)}")


if __name__ == "__main__":
    main()
