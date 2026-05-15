# -*- mode: python ; coding: utf-8 -*-


import glob, os
import texture2ddecoder
_t2d_dir = os.path.dirname(texture2ddecoder.__file__)
_t2d_binaries = [(p, 'texture2ddecoder') for p in glob.glob(os.path.join(_t2d_dir, '*.pyd'))]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=_t2d_binaries,
    datas=[('icon.ico', '.')],
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
    name='EZDDSViewer',
    icon='icon.ico',
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
)
