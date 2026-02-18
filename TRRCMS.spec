# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file for TRRCMS Desktop Application

import os
import sys

block_cipher = None
project_root = os.path.abspath('.')

a = Analysis(
    ['main.py'],
    pathex=[project_root],
    binaries=[],
    datas=[
        # Data files (JSON, GeoJSON — NOT trrcms.db, it gets recreated at startup)
        ('data/administrative_divisions.json', 'data'),
        ('data/neighborhoods.json', 'data'),
        ('data/sample_buildings.geojson', 'data'),

        # Assets: images, fonts, leaflet
        ('assets/images', 'assets/images'),
        ('assets/fonts', 'assets/fonts'),
        ('assets/leaflet', 'assets/leaflet'),

        # Translations
        ('services/translations/ar.py', 'services/translations'),
        ('services/translations/en.py', 'services/translations'),
        ('services/translations/__init__.py', 'services/translations'),

        # Environment config
        ('.env', '.'),
    ],
    hiddenimports=[
        'PyQt5',
        'PyQt5.QtWidgets',
        'PyQt5.QtCore',
        'PyQt5.QtGui',
        'PyQt5.QtWebEngineWidgets',
        'PyQt5.QtWebChannel',
        'PyQt5.QtPrintSupport',
        'psycopg2',
        'reportlab',
        'arabic_reshaper',
        'bidi',
        'qrcode',
        'PIL',
        'openpyxl',
        'pandas',
        'geojson',
        'flask',
        'cryptography',
        'bcrypt',
        'jwt',
        'dateutil',
        'dotenv',
        'zeroconf',
        'colorama',
        # App modules
        'app',
        'app.config',
        'app.main_window_v2',
        'controllers',
        'models',
        'repositories',
        'services',
        'ui',
        'utils',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tests',
        'tools',
        'scripts',
        'tkinter',
        'unittest',
        'pytest',
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
    name='TRRCMS',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # No black CMD window
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='TRRCMS',
)
