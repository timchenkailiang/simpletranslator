# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent


a = Analysis(
    [str(PROJECT_DIR / 'main.py')],
    pathex=[str(PROJECT_DIR)],
    binaries=[],
    datas=[
        (str(PROJECT_DIR / 'config' / 'tools.json'), 'config'),
        (str(PROJECT_DIR / 'config' / 'merge_profiles.json'), 'config'),
        (str(PROJECT_DIR / 'converters'), 'converters'),
        (str(PROJECT_DIR / 'utils.py'), '.'),
    ],
    hiddenimports=['pandas', 'pdfplumber', 'openpyxl'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'scipy'],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SimpleTranslator',
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
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='SimpleTranslator',
)

app = BUNDLE(
    coll,
    name='SimpleTranslator.app',
    icon=None,
    bundle_identifier='com.simpletranslator.app',
)
