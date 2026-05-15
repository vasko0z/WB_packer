# -*- coding: utf-8 -*-
"""
Скрипт для компиляции WB_packer в EXE файл
С автоматическим обновлением версии
"""
import subprocess
import sys
import os
import shutil
import re
from pathlib import Path


def increment_version():
    """Увеличить номер сборки и вернуть строку версии"""
    from version import VERSION_BUILD, get_version_string
    
    # Увеличиваем VERSION_BUILD в файле version.py
    version_file_path = Path("version.py")
    if version_file_path.exists():
        with open(version_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Находим и увеличиваем VERSION_BUILD
        new_build = VERSION_BUILD + 1
        content = re.sub(
            r'VERSION_BUILD\s*=\s*\d+',
            f'VERSION_BUILD = {new_build}',
            content
        )
        
        with open(version_file_path, 'w', encoding='utf-8') as f:
            f.write(content)
    
    # Перезагружаем модуль version для получения новой версии
    import importlib
    import version
    importlib.reload(version)
    
    version_str = version.get_version_string()
    print(f"[OK] Версия обновлена: {version_str} (сборка №{new_build})")
    return version_str


def clean_dist_folder():
    """Очистить папку dist перед компиляцией"""
    dist_folder = Path("dist")

    # Удаляем папку build если существует
    build_folder = Path("build")
    if build_folder.exists():
        shutil.rmtree(build_folder)
        print("  - Удалена папка build")

    if dist_folder.exists():
        print("[INFO] Очистка папки dist...")
        # Удаляем старую папку WB_packer если существует
        old_app_folder = dist_folder / "WB_packer"
        if old_app_folder.is_dir():
            shutil.rmtree(old_app_folder)
            print(f"  - Удалена папка {old_app_folder}")

        # Удаляем старый exe файл в корне dist если существует
        exe_file = dist_folder / "WB_packer.exe"
        if exe_file.exists():
            exe_file.unlink()
            print(f"  - Удален {exe_file}")
    else:
        dist_folder.mkdir(parents=True, exist_ok=True)


def copy_version_to_dist():
    """Не используется - версия вшита в код"""
    pass


def generate_spec_file():
    """Создать или обновить spec-файл с иконкой"""
    spec_content = '''# -*- mode: python ; coding: utf-8 -*-
import sys
sys.setrecursionlimit(10000)

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('Res', 'Res'),
        ('sounds', 'sounds'),
        ('version.py', '.'),
    ],
    hiddenimports=[
        'PyQt6',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'pandas',
        'numpy',
        'sqlalchemy',
        'psycopg2',
        'psycopg2_binary',
        'docx',
        'docx.shared',
        'docx.enum.text',
        'docx.enum.table',
        'PIL',
        'PIL.Image',
        'PIL.ImageQt',
        'openpyxl',
        'requests',
        'socketio',
        'engineio',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'scipy',
        'unittest',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='WB_packer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='Res/icon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='WB_packer',
)
'''
    
    spec_file = "WB_packer.spec"
    with open(spec_file, 'w', encoding='utf-8') as f:
        f.write(spec_content)
    
    print(f"[OK] Spec-файл создан: {spec_file}")
    return spec_file


def main():
    print("=" * 60)
    print("Компиляция WB_packer в EXE файл")
    print("=" * 60)

    # Проверяем наличие PyInstaller
    try:
        import PyInstaller
        print(f"[OK] PyInstaller установлен: версия {PyInstaller.__version__}")
    except ImportError:
        print("[ERROR] PyInstaller не установлен!")
        print("Установите: pip install PyInstaller")
        sys.exit(1)

    # Проверяем наличие spec-файла, если нет - создаём
    spec_file = "WB_packer.spec"
    if not os.path.exists(spec_file):
        print(f"[INFO] Spec-файл не найден, создаём...")
        spec_file = generate_spec_file()
    else:
        print(f"[OK] Spec-файл найден: {spec_file}")

    # Обновляем версию
    print()
    version = increment_version()

    # Очищаем dist перед компиляцией
    print()
    clean_dist_folder()

    # Запускаем PyInstaller
    print("\nЗапуск компиляции...")
    print("-" * 60)

    cmd = [sys.executable, "-m", "PyInstaller", "--clean", spec_file]

    try:
        result = subprocess.run(cmd, check=True, capture_output=False)

        print("-" * 60)
        print("\n[OK] Компиляция завершена успешно!")
        print(f"\nEXE файл создан: dist\\WB_packer.exe")
        print(f"Версия: {version}")
        print(f"\nГотовый файл для распространения:")
        print("  - dist/WB_packer.exe")

    except subprocess.CalledProcessError as e:
        print("-" * 60)
        print(f"\n[ERROR] Ошибка компиляции: {e}")
        sys.exit(1)
    except FileNotFoundError:
        print("\n[ERROR] PyInstaller не найден! Установите: pip install PyInstaller")
        sys.exit(1)

if __name__ == "__main__":
    main()
