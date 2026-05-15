# -*- coding: utf-8 -*-
r"""
Скрипт для обновления EXE файла WB_packer из сетевой папки
Копирует файл из \\mini\WORK\Поставки\WB_Packer\WB_packer.exe в папку запуска скрипта
"""
import shutil
import sys
import os
from pathlib import Path
from datetime import datetime


def get_script_dir():
    """Получить папку, в которой находится запущенный скрипт/EXE файл"""
    if getattr(sys, 'frozen', False):
        # Запущен как EXE файл
        return Path(sys.executable).parent.resolve()
    else:
        # Запущен как Python скрипт
        return Path(__file__).parent.resolve()


def main():
    print("=" * 60)
    print("Обновление WB_packer.exe из сетевой папки")
    print("=" * 60)

    # Пути
    script_dir = get_script_dir()
    network_dir = Path(r"\\mini\WORK\Поставки\WB_Packer")
    source_exe = network_dir / "WB_packer.exe"
    dest_exe = script_dir / "WB_packer.exe"

    # Проверяем сетевую папку
    if not network_dir.exists():
        print(f"\n[ERROR] Сетевая папка не найдена: {network_dir}")
        print("Проверьте подключение к сети и доступность сервера \\mini")
        sys.exit(1)

    print(f"[OK] Сетевая папка: {network_dir}")

    # Проверяем исходный файл
    if not source_exe.exists():
        print(f"\n[ERROR] Исходный файл не найден: {source_exe}")
        sys.exit(1)

    print(f"\n[OK] Исходный файл: {source_exe}")
    print(f"    Размер: {source_exe.stat().st_size:,} байт")
    print(f"    Дата изменения: {datetime.fromtimestamp(source_exe.stat().st_mtime)}")

    # Проверяем, существует ли файл назначения
    if dest_exe.exists():
        print(f"\n[INFO] Существующий файл: {dest_exe}")
        print(f"    Размер: {dest_exe.stat().st_size:,} байт")
        print(f"    Дата изменения: {datetime.fromtimestamp(dest_exe.stat().st_mtime)}")
        
        # Создаем резервную копию
        backup_exe = script_dir / f"WB_packer_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.exe"
        print(f"\n[INFO] Создание резервной копии: {backup_exe.name}")
        try:
            shutil.copy2(dest_exe, backup_exe)
            print(f"[OK] Резервная копия создана")
        except Exception as e:
            print(f"[WARNING] Не удалось создать резервную копию: {e}")

    # Копируем файл с заменой
    print(f"\n[INFO] Копирование файла...")
    try:
        shutil.copy2(source_exe, dest_exe)
        print(f"[OK] Файл успешно скопирован!")
        print(f"\n[INFO] Новый файл: {dest_exe}")
        print(f"    Размер: {dest_exe.stat().st_size:,} байт")
        print(f"    Дата изменения: {datetime.fromtimestamp(dest_exe.stat().st_mtime)}")
    except PermissionError as e:
        print(f"\n[ERROR] Ошибка доступа: {e}")
        print("Возможно, файл используется другим процессом.")
        print("Закройте WB_packer и повторите попытку.")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Ошибка при копировании: {e}")
        sys.exit(1)

    # Копируем недостающие PDF файлы из сетевой папки PDF
    print(f"\n[INFO] Синхронизация PDF файлов...")
    network_pdf_dir = network_dir / "PDF"
    local_pdf_dir = script_dir / "PDF"

    if network_pdf_dir.exists():
        # Создаём локальную папку PDF если нет
        local_pdf_dir.mkdir(parents=True, exist_ok=True)
        print(f"[OK] Локальная папка PDF: {local_pdf_dir}")

        pdf_files = list(network_pdf_dir.glob("*.pdf"))
        if not pdf_files:
            print("[INFO] PDF файлы в сетевой папке не найдены")
        else:
            copied_count = 0
            skipped_count = 0
            error_count = 0

            for src_pdf in pdf_files:
                dest_pdf = local_pdf_dir / src_pdf.name

                if dest_pdf.exists():
                    # Проверяем по дате и размеру - нужно ли обновлять
                    src_stat = src_pdf.stat()
                    dest_stat = dest_pdf.stat()

                    if (src_stat.st_size == dest_stat.st_size and
                            abs(src_stat.st_mtime - dest_stat.st_mtime) < 2):
                        skipped_count += 1
                        continue

                try:
                    shutil.copy2(src_pdf, dest_pdf)
                    copied_count += 1
                    print(f"  + {src_pdf.name}")
                except Exception as e:
                    error_count += 1
                    print(f"  [ERROR] {src_pdf.name}: {e}")

            print(f"\n[OK] PDF файлы: скопировано={copied_count}, пропущено={skipped_count}, ошибок={error_count}")
    else:
        print(f"[INFO] Сетевая папка PDF не найдена: {network_pdf_dir}")

    print("\n" + "=" * 60)
    print("Обновление завершено успешно!")
    print("=" * 60)


if __name__ == "__main__":
    main()
