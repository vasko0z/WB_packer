#!/usr/bin/env python3
"""check_secrets.py — поиск секретов в staged-файлах"""
from __future__ import annotations

import sys
import re
from pathlib import Path

# Force UTF-8 на Windows
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

PATTERNS = [
    (r'AKIA[0-9A-Z]{16}', 'AWS Access Key'),
    (r'ghp_[a-zA-Z0-9]{36}', 'GitHub Personal Token'),
    (r'sk-[a-zA-Z0-9]{48}', 'OpenAI API Key'),
    (r'Bearer\s+[a-zA-Z0-9_\-\.]+', 'Bearer Token'),
    (r'-----BEGIN (RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----', 'Private Key'),
    (r'postgresql://[^:]+:[^@]+@', 'PostgreSQL URL with password'),
    (r'mongodb(\+srv)?://[^:]+:[^@]+@', 'MongoDB URL with password'),
]

DEFAULT_IGNORE = [
    'check_secrets.py',
    'bump_version.py',
    'gen_summary.py',
    'gen_changelog.py',
    'session_log.py',
]


def check_file(filepath):
    findings = []
    try:
        text = filepath.read_text(encoding='utf-8')
    except Exception:
        return findings

    for pattern, name in PATTERNS:
        for match in re.finditer(pattern, text):
            line_num = text[:match.start()].count('\n') + 1
            snippet = text[max(0, match.start()-20):match.end()+20].replace('\n', ' ')
            findings.append((filepath.name, line_num, name, snippet))

    return findings


def main():
    files = sys.argv[1:] if len(sys.argv) > 1 else []
    if not files:
        # Проверяем все .py файлы
        root = Path(__file__).resolve().parent.parent
        files = [str(f) for f in root.rglob("*.py")]

    all_findings = []
    for f in files:
        if any(ign in f for ign in DEFAULT_IGNORE):
            continue
        findings = check_file(Path(f))
        all_findings.extend(findings)

    if all_findings:
        print("⚠️  Potential secrets found:\n")
        for fname, line, name, snippet in all_findings:
            print(f"  {fname}:{line} — {name}")
            print(f"    {snippet}\n")
        sys.exit(1)
    else:
        print("✅ No secrets found.")


if __name__ == "__main__":
    main()
