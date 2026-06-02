#!/usr/bin/env python3
"""session_log.py — черновик записи в SESSION_LOG.md"""
from __future__ import annotations

import sys
import re
import subprocess
from pathlib import Path
from datetime import datetime

# Force UTF-8 на Windows
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

ROOT = Path(__file__).resolve().parent.parent
SESSION_LOG = ROOT / "SESSION_LOG.md"


def get_last_commit_message():
    try:
        result = subprocess.run(
            ['git', 'log', '-1', '--pretty=%s'],
            capture_output=True, text=True, cwd=ROOT
        )
        return result.stdout.strip()
    except Exception:
        return ""


def get_changed_files():
    try:
        result = subprocess.run(
            ['git', 'diff', '--name-only', 'HEAD~1', 'HEAD'],
            capture_output=True, text=True, cwd=ROOT
        )
        return result.stdout.strip().split('\n')
    except Exception:
        return []


def count_sessions():
    if not SESSION_LOG.exists():
        return 0
    text = SESSION_LOG.read_text(encoding='utf-8')
    return len(re.findall(r'^## \d{4}-\d{2}-\d{2}', text, re.MULTILINE))


def detect_type(commit_msg):
    msg_lower = commit_msg.lower()
    if msg_lower.startswith('fix'):
        return 'fix'
    elif msg_lower.startswith('feat'):
        return 'feat'
    elif msg_lower.startswith('refactor'):
        return 'refactor'
    elif msg_lower.startswith('docs'):
        return 'docs'
    elif msg_lower.startswith('chore'):
        return 'chore'
    return 'update'


def generate_entry():
    today = datetime.now().strftime('%Y-%m-%d')
    session_num = count_sessions() + 1
    commit_msg = get_last_commit_message()
    changed_files = get_changed_files()
    commit_type = detect_type(commit_msg)

    lines = [
        f"\n## {today} (сессия {session_num})\n",
        f"\n### {commit_msg or 'Работа над проектом'}\n",
        f"\n> [!{commit_type}] Сессия {session_num}\n",
        "\n**Что сделано:**",
        "- (опишите изменения)\n",
    ]

    if changed_files:
        lines.append("**Файлы:**")
        for f in changed_files:
            if f.strip():
                lines.append(f"- `{f}`")
        lines.append("")

    lines.append("**Команды:**")
    lines.append("- `pyinstaller WB_Packer.spec --clean`\n")
    lines.append("---\n")

    return '\n'.join(lines)


def main():
    auto = '--auto' in sys.argv
    dry_run = '--dry-run' in sys.argv

    entry = generate_entry()

    if dry_run:
        print(entry)
        return

    if auto:
        if not SESSION_LOG.exists():
            SESSION_LOG.write_text("# Журнал сессий — WB Packer\n", encoding='utf-8')

        with open(SESSION_LOG, 'a', encoding='utf-8') as f:
            f.write(entry)
        print(f"Added entry to {SESSION_LOG}")
    else:
        print("Draft entry (use --auto to append):\n")
        print(entry)


if __name__ == "__main__":
    main()
