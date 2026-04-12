# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


PROJECT_DIR = Path(globals().get('SPECPATH', '.')).resolve().parent
SRC_DIR = PROJECT_DIR / 'src'


a = Analysis(
    [str(PROJECT_DIR / 'main.py')],
    pathex=[str(PROJECT_DIR), str(SRC_DIR)],
    binaries=[],
    datas=[
        (str(PROJECT_DIR / 'config' / 'tools.json'), 'config'),
        (str(PROJECT_DIR / 'config' / 'merge_profiles.json'), 'config'),
        (str(SRC_DIR / 'converters'), 'converters'),
        (str(SRC_DIR / 'utils.py'), '.'),
        (str(SRC_DIR / 'i18n.py'), '.'),
    ],
    hiddenimports=[
        'pandas',
        'pdfplumber',
        'openpyxl',
        'charset_normalizer.md',
        'charset_normalizer.cd',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'scipy'],
    noarchive=False,
    optimize=0,
)

# Avoid bundling charset_normalizer compiled extensions on Windows/Python 3.14.
# The pure-Python md/cd modules are bundled via hiddenimports above.
a.binaries = [
    entry for entry in a.binaries
    if 'charset_normalizer\\md.' not in entry[0].lower()
    and 'charset_normalizer\\cd.' not in entry[0].lower()
]

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
