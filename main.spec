# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [('C:\\Users\\lihb\\PycharmProjects\\QPE_GUI\\resources', 'resources'), ('C:\\Users\\lihb\\PycharmProjects\\QPE_GUI\\gui', 'gui'), ('C:\\Users\\lihb\\PycharmProjects\\QPE_GUI\\iodata', 'iodata'), ('C:\\Users\\lihb\\PycharmProjects\\QPE_GUI\\visualization', 'visualization'), ('C:\\Users\\lihb\\anaconda3\\envs\\qpe_gui\\Lib\\site-packages\\matplotlib\\mpl-data', 'matplotlib\\mpl-data')]
binaries = []
hiddenimports = ['cinrad', 'cinrad.io', 'matplotlib', 'matplotlib.pyplot', 'matplotlib.backends.backend_qt5agg']
tmp_ret = collect_all('cinrad')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
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
    name='main',
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
    icon=['C:\\Users\\lihb\\PycharmProjects\\QPE_GUI\\resources\\radar.ico'],
)
