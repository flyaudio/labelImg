# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['labelImg.py'],
    pathex=['./libs', './'],
    binaries=[
        # conda 环境下 lxml/ssl/ctypes 等模块的动态依赖 DLL（Library\bin）
        (r'D:\software\miniconda3\envs\labelme\Library\bin\libxml2.dll', '.'),
        (r'D:\software\miniconda3\envs\labelme\Library\bin\libxslt.dll', '.'),
        (r'D:\software\miniconda3\envs\labelme\Library\bin\libexslt.dll', '.'),
        (r'D:\software\miniconda3\envs\labelme\Library\bin\iconv.dll', '.'),
        (r'D:\software\miniconda3\envs\labelme\Library\bin\zlib.dll', '.'),
        (r'D:\software\miniconda3\envs\labelme\Library\bin\liblzma.dll', '.'),
        (r'D:\software\miniconda3\envs\labelme\Library\bin\libbz2.dll', '.'),
        (r'D:\software\miniconda3\envs\labelme\Library\bin\libssl-3-x64.dll', '.'),
        (r'D:\software\miniconda3\envs\labelme\Library\bin\libcrypto-3-x64.dll', '.'),
        (r'D:\software\miniconda3\envs\labelme\Library\bin\ffi.dll', '.'),
    ],
    datas=[],
    hiddenimports=['lxml'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PySide6', 'PyQt5'],
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
    name='labelImg',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
