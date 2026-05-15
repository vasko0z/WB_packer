# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# Collect pandas submodules excluding tests
pandas_submodules = collect_submodules('pandas')
pandas_submodules = [m for m in pandas_submodules if '.tests.' not in m and 'test_' not in m]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[(r'Res', 'Res')],
    hiddenimports=pandas_submodules + [
        'PyQt6.QtCore',
        'PyQt6.QtGui', 
        'PyQt6.QtWidgets',
        'PyQt6.QtPrintSupport',
        'psycopg',
        'psycopg_pool',
        'openpyxl',
        'pandas',
        'numpy',
        'cryptography',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'unittest',
        'json.tests',
        'pandas.tests',
        'PyQt6.Qt3D',
        'PyQt6.QtBluetooth',
        'PyQt6.QtDBus',
        'PyQt6.QtDesigner',
        'PyQt6.QtHelp',
        'PyQt6.QtMultimedia',
        'PyQt6.QtNetwork',
        'PyQt6.QtPositioning',
        'PyQt6.QtQml',
        'PyQt6.QtQuick',
        'PyQt6.QtSensors',
        'PyQt6.QtSerialPort',
        'PyQt6.QtSql',
        'PyQt6.QtTest',
        'PyQt6.QtWebChannel',
        'PyQt6.QtWebEngine',
        'PyQt6.QtWebSockets',
        'PyQt6.QtXml',
        'PyQt6.QtXmlPatterns',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='WB_packer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
