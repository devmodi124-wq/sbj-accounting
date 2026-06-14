# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec — builds a single Khata executable.
# Build with:  pyinstaller khata.spec   (run on the target OS, e.g. Windows in CI).
from PyInstaller.utils.hooks import collect_submodules

datas = [
    ("app/templates", "app/templates"),
    ("app/static", "app/static"),
]

hiddenimports = (
    collect_submodules("app")
    + collect_submodules("uvicorn")
    + [
        "sqlcipher3",
        "sqlcipher3.dbapi2",
        "bcrypt",
        "openpyxl",
        "anyio",
        "click",
        "h11",
    ]
)

a = Analysis(
    ["app/launcher.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Khata",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # no terminal window; the app opens in the browser
    disable_windowed_traceback=False,
)
