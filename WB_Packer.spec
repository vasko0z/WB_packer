# -*- mode: python ; coding: utf-8 -*-

import os
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# Получаем базовую директорию проекта
if getattr(sys, 'frozen', False):
    base_dir = Path(sys._MEIPASS)
else:
    base_dir = Path('.').resolve()

# Автоматически увеличиваем номер сборки при компиляции
version_file = Path('version.py')
exe_version = "1.0.0"
if version_file.exists():
    try:
        with open(version_file, 'r', encoding='utf-8') as f:
            content = f.read()
            if 'VERSION_BUILD' in content:
                import re
                match = re.search(r'VERSION_BUILD\s*=\s*(\d+)', content)
                if match:
                    current_build = int(match.group(1))
                    new_build = current_build + 1
                    content = re.sub(
                        r'(VERSION_BUILD\s*=\s*)\d+',
                        f'\\g<1>{new_build}',
                        content
                    )
                    with open(version_file, 'w', encoding='utf-8') as f:
                        f.write(content)
                    exe_version = f"1.0.{new_build}"
                    print(f"Версия обновлена: {exe_version}")
    except Exception as e:
        print(f"Не удалось обновить версию: {e}")

# Собираем datas только из существующих папок
datas = []

# Проверяем наличие папок и файлов
for folder_name in ['Res']:
    folder_path = base_dir / folder_name
    if folder_path.exists():
        datas.append((str(folder_path), folder_name))

for file_name in ['config.ini']:
    file_path = base_dir / file_name
    if file_path.exists():
        datas.append((str(file_path), '.'))

# Добавляем credentials файл для Google Sheets (в корень bundle)
credentials_file = base_dir / "e-object-470910-p6-3500f3ddbdd3.json"
if credentials_file.exists():
    datas.append((str(credentials_file), '.'))

# Добавляем данные reportlab (шрифты и т.д.)
try:
    reportlab_data = collect_data_files('reportlab')
    datas.extend(reportlab_data)
except Exception:
    pass

# Добавляем данные PyQt6 (плагины и т.д.)
try:
    pyqt6_data = collect_data_files('PyQt6')
    datas.extend(pyqt6_data)
except Exception:
    pass

# Собираем подмодули для критичных пакетов (исключая тесты)
pandas_submodules = [m for m in collect_submodules('pandas') if 'test' not in m.lower()]
openpyxl_submodules = [m for m in collect_submodules('openpyxl') if 'test' not in m.lower()]
reportlab_submodules = [m for m in collect_submodules('reportlab') if 'test' not in m.lower()]

# Бинарные файлы (DLL) — только необходимые
binaries = []

# Добавляем DLL из нужных пакетов (исключая Qt3D, QtWebEngine, QtQuick и др.)
try:
    from PyInstaller.utils.hooks import collect_dynamic_libs
    # PyQt6 — только нужные модули: QtWidgets, QtCore, QtGui, QtPrintSupport
    for pkg in ['pandas', 'numpy', 'psycopg2', 'sqlalchemy', 'PIL', 'reportlab', 'psutil', 'pymupdf']:
        try:
            pkg_binaries = collect_dynamic_libs(pkg)
            binaries.extend(pkg_binaries)
        except Exception:
            pass
except Exception:
    pass

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=list(set([
        # GUI
        'PyQt6', 'PyQt6.QtWidgets', 'PyQt6.QtCore', 'PyQt6.QtGui', 'PyQt6.QtPrintSupport',
        # Данные
        'pandas', 'pandas.io.formats', 'pandas.io.formats.style', 'pandas.plotting', 'pandas.io.clipboard',
        'numpy', 'numpy.random',
        # Excel
        'openpyxl', 'openpyxl.cell._writer', 'openpyxl.styles.stylesheet', 'openpyxl.xml.functions',
        # PDF
        'reportlab', 'reportlab.pdfgen', 'reportlab.lib.units', 'reportlab.lib.pagesizes',
        'reportlab.pdfbase', 'reportlab.pdfbase.ttfonts', 'reportlab.pdfbase.pdfmetrics',
        'reportlab.lib.utils', 'reportlab.graphics', 'reportlab.graphics.barcode',
        'reportlab.platypus', 'reportlab.graphics.shapes',
        # Изображения
        'PIL', 'PIL.Image', 'PIL.ImageTk', 'PIL.ImageFilter', 'PIL.ImageDraw', 'PIL.ImageFont',
        # PostgreSQL
        'psycopg2', 'psycopg2._psycopg', 'psycopg2.pool',
        'psycopg', 'psycopg_pool',
        # ORM
        'sqlalchemy', 'sqlalchemy.orm', 'sqlalchemy.orm.sessionmaker',
        # HTTP
        'requests', 'requests.adapters', 'requests.auth',
        'urllib3', 'urllib3.contrib', 'urllib3.util', 'urllib3.poolmanager',
        # Документы
        'docx', 'docx.shared', 'docx.enum.text',
        # Система
        'psutil',
        # Криптография
        'cryptography', 'cryptography.fernet',
        'charset_normalizer', 'certifi',
        'dateutil', 'dateutil.relativedelta', 'dateutil.parser',
        'zoneinfo',
        'backports',
        # Tkinter (для labelprint)
        'tkinter', 'tkinter.ttk', 'tkinter.scrolledtext', 'tkinter.messagebox', 'tkinter.filedialog',
        'pymupdf', 'fitz',
        # Локальные модули
        'database', 'db_connection', 'models', 'utils', 'version', 'config',
        'app_constants', 'themes', 'dialogs', 'common_utils',
        'shipment_manager', 'shipment_operations', 'ui_updater', 'main_window',
        'data_controller', 'data_cache', 'async_operations', 'async_worker',
        'boxes_window', 'archive_window', 'custom_table_widget',
        'check_stock_dialog', 'db_settings_dialog', 'label_print_dialog',
        'label_settings_dialog', 'labelprint', 'moysklad_api', 'moysklad_logger',
        'moysklad_settings_dialog', 'simplified_dialog', 'shipment_check_dialog',
        'shipment_controller', 'shipment_data_fetcher', 'shipment_tracking_widget',
        'final_corrected_stock_manager', 'get_stock_quantity_for_item',
        'improved_moysklad_sync', 'optimized_get_stock_quantity', 'progress_dialog',
        'memory_manager', 'local_db', 'lock_manager', 'logging_config',
        'image_cache', 'image_check_box', 'create_test_label', 'check_size',
        'editing_delegate', 'minimal_shipment_dialog', 'security_utils',
        'db_discovery', 'splash_screen', 'mvc_controller',
        # Скрытые зависимости
        'sqlite3', 'multiprocessing', 'concurrent.futures',
        'xml.etree.cElementTree', 'xml.dom.domreg',
        'html', 'html.parser',
        'typing_extensions', 'importlib_metadata',
    ] + pandas_submodules + openpyxl_submodules + reportlab_submodules)),
    excludes=[
        # Тесты pandas — основная причина большого размера
        'pandas.tests', 'numpy.tests', 'numpy.lib.tests',
        'openpyxl.tests', 'PIL.tests', 'reportlab.tests',
        'sqlalchemy.tests', 'psycopg2.tests', 'psycopg.tests',
        'tkinter.tests', 'urllib3.tests', 'requests.tests',
        # Исключаем неиспользуемые модули PyQt6
        'PyQt6.Qt3DCore', 'PyQt6.Qt3DRender', 'PyQt6.Qt3DExtras', 'PyQt6.Qt3DAnimation',
        'PyQt6.Qt3DInput', 'PyQt6.Qt3DLogic',
        'PyQt6.QtBluetooth', 'PyQt6.QtDBus', 'PyQt6.QtDesigner',
        'PyQt6.QtHelp', 'PyQt6.QtMultimedia', 'PyQt6.QtMultimediaWidgets',
        'PyQt6.QtNfc', 'PyQt6.QtPositioning', 'PyQt6.QtLocation',
        'PyQt6.QtQuick', 'PyQt6.QtQuickWidgets', 'PyQt6.QtQuick3D',
        'PyQt6.QtQml', 'PyQt6.QtWebEngine', 'PyQt6.QtWebEngineWidgets',
        'PyQt6.QtWebChannel', 'PyQt6.QtWebView',
        'PyQt6.QtRemoteObjects', 'PyQt6.QtSensors',
        'PyQt6.QtSerialPort', 'PyQt6.QtSpatialAudio',
        'PyQt6.QtSql', 'PyQt6.QtStateMachine',
        'PyQt6.QtSvg', 'PyQt6.QtSvgWidgets',
        'PyQt6.QtTest', 'PyQt6.QtTextToSpeech',
        'PyQt6.QtXml', 'PyQt6.QtPdf', 'PyQt6.QtPdfWidgets',
        'PyQt6.QAxContainer', 'PyQt6.lupdate',
        # Исключаем ML/AI библиотеки (не нужны для проекта)
        'torch', 'torchvision', 'torchaudio',
        'onnx', 'onnxruntime', 'onnx.reference',
        'transformers', 'huggingface_hub', 'tokenizers',
        'tensorflow', 'keras', 'scipy', 'sklearn', 'scikit-learn',
        'sympy', 'networkx', 'optimum',
        'mcp', 'starlette', 'uvicorn', 'fastapi',
        'pydantic', 'pydantic_settings',
        'jinja2', 'markupsafe',
        'rich', 'pygments', 'markdown_it',
        'aiohttp', 'httpx', 'httpcore', 'websockets',
        'jsonschema', 'referencing', 'jsonschema_specifications',
        'dns', 'dnspython',
        'dotenv', 'python-dotenv',
        'fsspec', 'orjson', 'annotated_doc',
        'sse_starlette', 'multipart', 'python-multipart',
        'win32com', 'pywin32', 'pywin',
        'lxml', 'bs4', 'soupsieve',
        'docx', 'python-docx',
        'pytesseract',
        'google.protobuf', 'protobuf',
        'ml_dtypes',
        'safetensors',
        'einops',
        'colorama',
        'regex',
        'tqdm',
        'filelock',
        'functorch',
        'torchgen',
        'sympy',
        'mpmath',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

# Путь к иконке - используем текущий каталог
import os
icon_path = 'Res/icon.ico'
print(f"Icon path: {icon_path}")
print(f"Icon exists: {os.path.exists(icon_path)}")

if not os.path.exists(icon_path):
    icon_path = str(spec_dir / 'icon.ico')
if not os.path.exists(icon_path):
    print("WARNING: Icon not found!")
    icon_path = None

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    exclude_binaries=False,
    name='WB_packer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[icon_path] if icon_path else [],
)
