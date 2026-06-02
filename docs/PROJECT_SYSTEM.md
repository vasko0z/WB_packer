# Система проекта: документация, память, правила

**Версия:** 1.0
**Последнее обновление:** 2026-06-02

> [!info] Назначение
> Описание переносимой системы, которая ставится поверх любого git-репозитория:
> единая версия, журнал сессий, авто-генерация документации, проверки качества,
> git-хуки, долговременная память агента. Без привязки к конкретному стеку или
> домену — адаптируется подставляемыми именами файлов и скриптов.

---

## 1. Структура репозитория (шаблон)

```
<REPO_ROOT>/
├── VERSION                       # Единственный источник версии (semver)
├── AGENTS.md                     # Правила для агента (тонкий, только критика)
├── README.md                     # Главный входной документ
├── SESSION_LOG.md                # Журнал сессий (хронология изменений)
├── CONTRIBUTING.md               # Гайд для нового контрибьютора
├── docs/                         # Подробная документация
│   ├── README.md                 # Индекс/оглавление docs/
│   ├── _TEMPLATE.md              # Шаблоны и правила оформления .md
│   ├── _SUMMARY.md               # Авто-индекс (генерируется)
│   ├── CHANGELOG.md              # Авто из Conventional Commits
│   ├── API.md                    # Авто из OpenAPI/Swagger (опционально)
│   └── <TOPIC>.md                # Конкретные модули/фичи/интеграции
├── scripts/                      # Python-скрипты обслуживания (см. §7)
├── .githooks/                    # pre-commit, pre-push, post-commit
├── Makefile                      # Удобные таргеты (см. §8)
├── .editorconfig                 # Кодировка/отступы/EOL
├── .gitattributes                # Нормализация EOL по типам файлов
├── .markdownlint.json            # Правила markdownlint
├── .ruff.toml                    # Настройки ruff (если есть Python)
└── data/                         # История замеров (JSON), не в коммит кода
```

Принцип: всё, что не критично для запуска/понимания проекта — выносится в `docs/`.
В корне — только то, что должно быть на виду у каждого.

---

## 2. Единый источник версии — `VERSION`

Файл `VERSION` в корне содержит одну строку в semver-формате: `MAJOR.MINOR.PATCH`
(например, `1.4.0`). Это **единственное** место, где хранится версия.

Правила:
- Любые упоминания версии в `README.md`, `docs/README.md`, `docs/_SUMMARY.md`,
  в шапках документов и в ответах backend должны синхронизироваться с `VERSION`.
- Изменение делается через `scripts/bump_version.py {patch|minor|major|X.Y.Z}`
  или одноимённые `make`-таргеты. Скрипт сам правит синхронизируемые файлы
  (см. §7).
- В коде версию читают из файла, а не хардкодят. Типичный helper
  (`backend/core/version.py` и аналоги в других языках):

  ```python
  from pathlib import Path
  VERSION = (Path(__file__).resolve().parents[2] / "VERSION").read_text().strip()
  ```

---

## 3. AGENTS.md — тонкий файл правил

`AGENTS.md` в корне содержит **только критически важное** для агента:
- Команды деплоя (ssh/scp/docker), если есть сервер.
- Правила поведения (язык, кодировка, PowerShell/cmd ограничения).
- Архитектурные инварианты, нарушение которых ломает систему.
- Ссылка на эту систему (документация, скрипты, хуки).
- Раздел про долговременную память (§9).

Всё остальное (форматы API, описание модулей, troubleshooting) — в `docs/`.
Это защищает `AGENTS.md` от разрастания и устаревания.

Рекомендуемая шапка:

```markdown
# AGENTS.md — Правила для агента

**Версия:** X.Y | **Дата:** YYYY-MM-DD

## Общие правила
- <язык рассуждений, кодировка, ограничения shell>

## Деплой
- <команды или ссылка на docs/DEPLOY.md>

## Git
- <commit types, ежедневный push, прочее>

## Система документации
- Краткое описание + ссылка на docs/PROJECT_SYSTEM.md

## Память
- <использование SLM/MCP>
```

---

## 4. Документация — `docs/`

### 4.1. Правила оформления `.md` (универсальные)

Применяются ко всем файлам в `docs/`, `README.md`, `AGENTS.md`, `SESSION_LOG.md`.
Полные шаблоны — в `docs/_TEMPLATE.md`; здесь — нормативный минимум.

1. **Шапка** документа (для модулей/фич):
   ```markdown
   # <Название>

   **Версия:** X.Y
   **Последнее обновление:** YYYY-MM-DD
   ```
   Допускается также вариант `**Дата:**` вместо «Последнее обновление».
2. **Кодировка:** строго UTF-8 (без BOM). На Windows не использовать
   PowerShell redirection `>` / `>>` / `echo ... >>` для русского текста —
   применяется `Out-File -Encoding utf8`, `Add-Content -Encoding utf8` или
   инструменты `edit`/`write`.
3. **Длина строки:** ≤ 120 символов (настраивается в `.markdownlint.json`).
4. **Даты:** ISO `YYYY-MM-DD`. Форматы `DD.MM.YYYY` / `MM/DD/YYYY` запрещены.
5. **Версии:** semver `MAJOR.MINOR` или `MAJOR.MINOR.PATCH`.
6. **Ссылки:** относительные `docs/X.md` или `<topic>.md`.
   Внешние URL — только на стабильные внешние ресурсы.
7. **Имена файлов:** без эмодзи (`INVENTORY.md`, не `📦_INVENTORY.md`).
8. **Юникод в тексте:** допустимы Δ, ⚠, 🔒, ✅, ⬜ и т.п. — но аккуратно.

### 4.2. Структура `docs/`

- `docs/README.md` — оглавление (может быть коротким, ссылается на `_SUMMARY.md`).
- `docs/_TEMPLATE.md` — шаблоны «модуль», «фича», правила оформления.
  Не редактируется под конкретный проект, копируется как стартовая точка.
- `docs/_SUMMARY.md` — **авто-индекс** всех `.md` в `docs/`. Генерируется
  скриптом `scripts/gen_summary.py` (см. §7.4). Вручную не правится.
- `docs/CHANGELOG.md` — **авто** из Conventional Commits (см. §7.5).
- `docs/API.md` — **авто** из `/openapi.json` или иного источника (см. §7.6).
  Подходит для FastAPI, NestJS, Express+swagger-jsdoc, и т.д.
- Конкретные документы — по темам: `AUTH.md`, `DEPLOY.md`, `<MODULE>.md`,
  `integrations/<VENDOR>.md`. Имена — на латинице, CamelCase или CAPS.

### 4.3. Когда обновлять документацию

При значимых изменениях (новая фича, изменение API, деплой-процедуры):
1. **Конкретный файл** в `docs/` (по теме изменения).
2. **`README.md`** в корне — если меняются модули/возможности.
3. **`SESSION_LOG.md`** — запись о сессии (см. §5).
4. **Авто-генерируемые** (`_SUMMARY.md`, `CHANGELOG.md`, `API.md`) — не
   редактировать руками, а запустить соответствующий скрипт.

---

## 5. Журнал сессий — `SESSION_LOG.md`

Заменяет внешние журналы (Obsidian/Notion/бумажные). Хранится в репо,
коммитится в git, индексируется.

### 5.1. Формат записи

```markdown
## YYYY-MM-DD (сессия N)

### Краткий заголовок

> [!fix|feat|update|docs|chore|refactor|security] Суть одним предложением
> Что и почему

**Причина:** (если баг) корень проблемы
**Что сделано:** список изменений
**Файлы:** перечень изменённых файлов
**Команды:** команды деплоя (если были)
```

Где `N` — сквозной номер сессии (считается скриптом, см. §7.11).
Callout-теги Obsidian-совместимые: `info`, `fix`, `feat`, `update`, `docs`,
`chore`, `refactor`, `security`, `warn`, `tip`.

### 5.2. Правила ведения

- Запись добавляется **после каждой сессии** агента (перед `git push`).
- Если в коммит попадают изменения кода/docs, в `SESSION_LOG.md` должна
  быть запись за сегодня — иначе `pre-commit` блокирует коммит.
- Пропуск проверки: `git commit --no-verify` (использовать осознанно).
- Создание черновика записи: `python scripts/session_log.py --auto`
  (или `make session-log`). Скрипт сам подставит дату, номер сессии,
  список изменённых файлов, тип изменений (по последнему commit message).

---

## 6. Git-коммиты и Conventional Commits

### 6.1. Формат сообщения

```
<type>(<scope>): <subject>

<body>

<footer>
```

Допустимые типы: `feat`, `fix`, `refactor`, `chore`, `docs`, `perf`,
`security`, `test`, `build`, `ci`, `style`.

`<scope>` — опционально: модуль/файл/зона (`feat(auth): add JWT refresh`).

`!` после type или `BREAKING CHANGE:` в footer — индикатор ломающего
изменения (используется при генерации CHANGELOG).

### 6.2. Workflow

- При значимых изменениях — коммит в git: `git add .; git commit -m "..."`.
- **Сразу после коммита** — `git push origin main` (или рабочая ветка).
- **В конце сессии** — пуш выполнить даже если коммитов не было.

---

## 7. Скрипты обслуживания (`scripts/`)

Все скрипты — `python3`, минимум зависимостей (по возможности только stdlib),
Force-UTF-8 в stdout/stderr (см. шаблон ниже). Допускают `--help`, `--json`,
`--strict` (exit 1 при проблемах) — это упрощает интеграцию с хуками.

Стандартный заголовок Python-скрипта:

```python
#!/usr/bin/env python3
"""<краткое описание>"""
from __future__ import annotations

import sys
from pathlib import Path

# Force UTF-8 на Windows (stdout в CP1251 ломает кириллицу)
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

ROOT = Path(__file__).resolve().parent.parent
```

### 7.1. `bump_version.py` — версия + синхронизация

- `python scripts/bump_version.py {patch|minor|major|X.Y.Z}`.
- Меняет `VERSION`, обновляет `**Версия:**` и `**Последнее обновление:**`
  в `README.md`, `docs/README.md` (список файлов настраивается в скрипте).

### 7.2. `docs_freshness.py` — свежесть документации

- Сканирует `docs/*.md`, `README.md`, `AGENTS.md`, `SESSION_LOG.md`.
- Парсит `**Дата:**` / `**Последнее обновление:**` / `**Версия:**` в шапке.
- Сравнивает с датой последнего `git commit` файла.
- `--days N` (default 30), `--strict` (exit 1), `--json`,
  `--only-changed` (быстрый режим для pre-push).

### 7.3. `lint_md.py` — линтер markdown

- Без внешних зависимостей. Проверяет:
  - MD041: первая строка — `# Заголовок`.
  - MD025: один H1 в файле.
  - MD013: длина строки ≤ 120 (настраивается `--max-line-length`).
  - MD040: язык в code-блоках.
  - Внутреннее: `YYYY-MM-DD`, semver-версии.
- `--strict` (exit 1 при warning).

### 7.4. `gen_summary.py` — авто-индекс `_SUMMARY.md`

- Сканирует `docs/*.md`, извлекает заголовок, версию, дату, описание.
- Группирует по префиксу имени файла (GROUPS — настраивается в скрипте).
- `--output PATH`, `--check` (exit 1 при расхождении), `--stdout`.

### 7.5. `gen_changelog.py` — CHANGELOG из git

- Парсит `git log` в формате Conventional Commits.
- Группирует по типам (`feat`, `fix`, ...).
- `--limit N`, `--output PATH`.

### 7.6. `gen_api_docs.py` — API из OpenAPI/Swagger

- Забирает `/openapi.json` с живого backend (`--base URL`).
- Формирует таблицу эндпоинтов + модели.
- `--output PATH`. Если backend недоступен — печатает понятную ошибку
  (скрипт не критичен, запускается вручную или по CI).

### 7.7. `check_links.py` — битые ссылки

- Ищет `[text](file.md#anchor)` по `.md`, проверяет существование целей.
- `--strict` (exit 1). Игнорирует сгенерированные файлы.

### 7.8. `check_orphans.py` — orphan-файлы без документации

- Находит `.py`, `.html` и т.п. без упоминаний в `docs/*.md`.
- Полезно для планирования новых документов.

### 7.9. `check_secrets.py` — поиск секретов

- Grep по patterns: AWS, GitHub tokens, JWT, приватные ключи,
  DB URL с паролями, Bearer-токены.
- Запускается на staged-файлах в `pre-commit`.

### 7.10. `audit_deps.py` — уязвимости в зависимостях

- Парсит `requirements.txt` / `package.json` / `Cargo.toml` (адаптируется).
- Проверяет pin-версии.
- Запрос к OSV.dev / npm audit для известных CVE.
- `--strict`.

### 7.11. `session_log.py` — черновик записи в SESSION_LOG

- Считает существующие сессии в `SESSION_LOG.md`.
- Подставляет дату, номер сессии, тип (по последнему commit message),
  список изменённых файлов.
- `--auto` — дописывает без вопросов. `--dry-run` — только вывод.

### 7.12. Прочие (опционально)

`docs_metrics.py` — метрики качества (покрытие модулей документацией,
медианный возраст файлов). `sync_<VENDOR>_openapi.py` — сверка
документации конкретной интеграции с кодом (по аналогии с §7.6).

---

## 8. Git-хуки (`.githooks/`)

Включение: `git config core.hooksPath .githooks`.

### 8.1. `pre-commit` (блокирующий)

Проверки в порядке (любая ошибка = `exit 1`):

1. **SESSION_LOG обновлён** — если в staged есть изменения кода/docs
   (исключая `SESSION_LOG.md`, `docs/AUDIT_*.md`, `.githooks/`, `VERSION`,
   `.gitattributes`, `.gitignore`), то в `SESSION_LOG.md` должна быть
   запись `^## YYYY-MM-DD` за сегодня. Иначе — подсказка про
   `python scripts/session_log.py --auto`.
2. **Секреты** — `python scripts/check_secrets.py <staged_files>`.
   При срабатывании — список подозрительных мест и подсказка про
   `DEFAULT_IGNORE` в скрипте.
3. **Ruff** (если есть `.ruff.toml`) — лимитированно на `scripts/`,
   `tests/`, плюс критичные файлы. Legacy-код проекта не линтится.
4. **Авто-обновление `_SUMMARY.md`** — если в staged есть новые
   `docs/*.md`, перегенерировать индекс и добавить его в коммит.

Пропуск всего хука: `git commit --no-verify`.

### 8.2. `pre-push` (блокирующий)

1. **Версия синхронизирована** — `VERSION` встречается в `README.md`,
   `docs/README.md`, `docs/_SUMMARY.md`. Иначе — подсказка про
   `bump_version.py`.
2. **`SESSION_LOG.md` закоммичен** — иначе `git checkout SESSION_LOG.md`.
3. **`make quality-all`** (warning level) — не блокирует, но сигнализирует.

Пропуск: `git push --no-verify`.

### 8.3. `post-commit` (информационный)

Запускает `python scripts/docs_freshness.py --days 30 | tail -10` —
агент сразу видит, не устарела ли документация.

---

## 9. Долговременная память агента

Долговременная память в MCP (например, **superlocalmemory**) работает
поверх git-журнала проекта и не дублирует его. Использование — **автоматическое**,
без подтверждений:

- **Старт сессии** — `session_init(project_path=текущая_директория)`:
  подтягивает недавние решения, паттерны, активные assertion'ы.
- **После задач/решений** — `observe` сохраняет контекст автоматически.
- **При ошибках** — `recall` ищет похожие решения прошлых сессий.
- **Слабые сигналы** (стиль, предпочтения) — soft-prompts и assertions
  накапливаются и подмешиваются в контекст без явного вызова.

Дублировать содержимое `SESSION_LOG.md` в памяти **не нужно**:
SESSION_LOG — это авторитетный, коммитируемый, индексируемый источник.
Память нужна для черновиков, черных ходов и личных предпочтений пользователя.

---

## 10. Makefile — набор таргетов

Все таргеты — phony (`make help` для самодокументации). Раздел с
документацией и качеством — универсален и переносим целиком.

```makefile
.PHONY: docs-freshness docs-freshness-strict gen-changelog gen-api-docs \
        gen-summary docs-all check-links check-orphans lint-md \
        check-secrets audit-deps session-log docs-metrics test lint \
        quality-all quality-all-strict bump-patch bump-minor bump-major

bump-patch:        ## Bump patch version
	@python scripts/bump_version.py patch
bump-minor:        ## Bump minor version
	@python scripts/bump_version.py minor
bump-major:        ## Bump major version
	@python scripts/bump_version.py major

docs-freshness:        ## Check docs freshness
	@python scripts/docs_freshness.py
docs-freshness-strict: ## Same, exit 1 on stale
	@python scripts/docs_freshness.py --strict
gen-changelog:         ## Generate CHANGELOG.md
	@python scripts/gen_changelog.py --limit 200 --output docs/CHANGELOG.md
gen-api-docs:          ## Generate API.md (needs running backend)
	@python scripts/gen_api_docs.py --base http://localhost:8080 --output docs/API.md
gen-summary:           ## Generate _SUMMARY.md
	@python scripts/gen_summary.py --output docs/_SUMMARY.md
docs-all: docs-freshness gen-changelog gen-summary
check-links:           ## Check broken links in .md
	@python scripts/check_links.py
check-orphans:         ## Find source files without docs
	@python scripts/check_orphans.py
lint-md:               ## Markdown linter
	@python scripts/lint_md.py
check-secrets:         ## Scan staged files for secrets
	@python scripts/check_secrets.py
audit-deps:            ## Audit requirements/package manifests
	@python scripts/audit_deps.py
session-log:           ## Add today's session template
	@python scripts/session_log.py --auto
docs-metrics:          ## Show docs quality metrics
	@python scripts/docs_metrics.py
test:                  ## Run pytest
	@python -m pytest tests/ -v
lint:                  ## Ruff on scripts/ + tests/
	@ruff check scripts/ tests/
quality-all: check-links check-orphans lint-md audit-deps test
	@echo "=== quality-all complete (warnings only) ==="
quality-all-strict: check-links-strict check-orphans-strict lint-md-strict audit-deps-strict test
	@echo "=== quality-all-strict complete (all green) ==="
```

В Windows-Git-Bash: переопределить `SHELL` и `.SHELLFLAGS`, как в
исходном `Makefile` проекта-примера.

---

## 11. Конфиги форматирования

### 11.1. `.editorconfig`

```ini
root = true

[*]
charset = utf-8
end_of_line = lf
insert_final_newline = true
trim_trailing_whitespace = true
indent_style = space
indent_size = 4

[*.{md,markdown}]
trim_trailing_whitespace = false
indent_size = 2

[*.{yml,yaml,json,toml}]
indent_size = 2

[*.{sh,bash}]
end_of_line = lf

[*.ps1]
end_of_line = crlf

[Makefile]
indent_style = tab

[*.{ts,js,tsx,jsx}]
indent_size = 2
quote_type = single
```

### 11.2. `.gitattributes`

Нормализация EOL — `*.md`, `*.py`, `*.yml`, `*.json`, `*.toml`, `*.sh`,
`Makefile`, `.env*`, `Dockerfile*`, `VERSION` и т.д. — все `lf`. Исключения:
`*.ps1`, `*.bat` — `crlf`. Это критично для Windows + Git, иначе
диффы ломаются на `\r\n`.

### 11.3. `.markdownlint.json`

```json
{
  "default": true,
  "MD013": false,
  "MD024": { "siblings_only": true },
  "MD033": false,
  "MD041": false,
  "MD046": { "style": "fenced" },
  "MD007": { "indent": 2 },
  "line-length": 120
}
```

### 11.4. `.ruff.toml` (если есть Python)

Минимальный конфиг для `scripts/`, `tests/` и точечных production-файлов.
Legacy-код в `backend/`, `frontend/` и т.д. — отключён per-path:
`[tool.ruff.lint.per-file-ignores]`.

---

## 12. Чек-лист переноса в новый проект

1. **Создать `VERSION`** (`0.1.0`), `AGENTS.md` (тонкий), `README.md`,
   `SESSION_LOG.md`, `CONTRIBUTING.md`, `docs/` (с пустыми `README.md`,
   `_TEMPLATE.md`, `_SUMMARY.md`).
2. **Скопировать `scripts/`** из шаблона, адаптировать пути
   (`ROOT = Path(...).parent.parent` остаётся, `SYNC_TARGETS` —
   поправить под проект).
3. **Скопировать `.githooks/`**, выполнить `git config core.hooksPath .githooks`.
4. **Скопировать `Makefile`** (только универсальные таргеты из §10;
   deploy/server — свои).
5. **Скопировать конфиги** `.editorconfig`, `.gitattributes`,
   `.markdownlint.json`, `.ruff.toml` (если есть Python).
6. **Создать `tests/test_scripts.py`** с базовыми smoke-тестами
   (запускаются без зависимостей).
7. **Сделать первый коммит**: `chore: bootstrap project system`.
8. **Сделать первый `git push origin main`**.
9. **Запустить `make quality-all`** — всё должно быть зелёным.
10. **Заполнить `AGENTS.md`** — добавить проект-специфичные
    команды деплоя, архитектурные инварианты.

После этого система готова: каждое изменение сопровождается записью
в `SESSION_LOG.md`, документация остаётся свежей благодаря
`docs_freshness.py`, качество контролируется `pre-commit`/`pre-push`/
`make quality-all`.

---

## 13. Файлы

- `docs/PROJECT_SYSTEM.md` — этот документ.
- `docs/_TEMPLATE.md` — шаблоны и правила оформления `.md`.
- `docs/_SUMMARY.md` — авто-индекс документации.
- `VERSION` — единственный источник версии.
- `SESSION_LOG.md` — журнал сессий.
- `AGENTS.md` — тонкий набор правил для агента.
- `scripts/` — обслуживающие Python-скрипты (§7).
- `.githooks/` — pre-commit, pre-push, post-commit (§8).
- `Makefile` — таргеты (§10).
- `.editorconfig`, `.gitattributes`, `.markdownlint.json`, `.ruff.toml` — §11.

## 14. История

- 2026-06-02 — создан документ (выделено универсальное ядро из проекта-примера).
