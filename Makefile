# Makefile — набор таргетов для WB Packer

.PHONY: help bump-patch bump-minor bump-major gen-summary check-secrets session-log docs-freshness quality-all

help:  ## Показать справку
	@echo "Доступные таргеты:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'

bump-patch:  ## Увеличить patch версию
	@python scripts/bump_version.py patch

bump-minor:  ## Увеличить minor версию
	@python scripts/bump_version.py minor

bump-major:  ## Увеличить major версию
	@python scripts/bump_version.py major

gen-summary:  ## Сгенерировать _SUMMARY.md
	@python scripts/gen_summary.py

check-secrets:  ## Проверить на секреты
	@python scripts/check_secrets.py

session-log:  ## Добавить запись в SESSION_LOG.md
	@python scripts/session_log.py --auto

docs-freshness:  ## Проверить свежесть документации
	@echo "Документация в актуальном состоянии (проверка не реализована)"

quality-all: check-secrets gen-summary  ## Полная проверка качества
	@echo "=== quality-all complete ==="
