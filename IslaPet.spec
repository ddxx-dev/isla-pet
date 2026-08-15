# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['isla_pet.py'],
    pathex=[],
    binaries=[],
    datas=[('assets/idle.png', 'assets'), ('assets/blink.png', 'assets'), ('assets/shy.png', 'assets'), ('assets/panic.png', 'assets'), ('assets/sleep.png', 'assets'), ('assets/tea.png', 'assets'), ('assets/icon.ico', 'assets'), ('dialogues.json', '.')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='IslaPet',
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
    icon=['assets\\icon.ico'],
)
