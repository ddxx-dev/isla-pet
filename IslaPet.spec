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
    excludes=['PySide6.QtQml', 'PySide6.QtQuick', 'PySide6.QtQuick3D', 'PySide6.QtQuickWidgets', 'PySide6.QtCharts', 'PySide6.QtDataVisualization', 'PySide6.QtBluetooth', 'PySide6.QtNfc', 'PySide6.QtPositioning', 'PySide6.QtLocation', 'PySide6.QtSerialPort', 'PySide6.QtSerialBus', 'PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets', 'PySide6.QtWebEngineQuick', 'PySide6.QtWebSockets', 'PySide6.QtWebChannel', 'PySide6.Qt3DCore', 'PySide6.Qt3DRender', 'PySide6.Qt3DInput', 'PySide6.Qt3DLogic', 'PySide6.Qt3DAnimation', 'PySide6.Qt3DExtras', 'PySide6.QtDesigner', 'PySide6.QtHelp', 'PySide6.QtTest', 'PySide6.QtSql', 'PySide6.QtSpatialAudio', 'PySide6.QtTextToSpeech', 'PySide6.QtSensors', 'PySide6.QtRemoteObjects', 'PySide6.QtScxml', 'PySide6.QtStateMachine', 'PySide6.QtMultimediaWidgets'],
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
