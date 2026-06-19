# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for a standalone, no-Python-needed Windows build.

Builds a one-folder app (dist/BiometricAttendance/) whose BiometricAttendance.exe
the user double-clicks. The ~300 MB face model is NOT bundled; insightface
downloads it once on first launch (needs internet that first time).

Build from the project root:
    .venv\\Scripts\\pyinstaller.exe packaging\\BiometricAttendance.spec --noconfirm
"""
import os
from PyInstaller.utils.hooks import collect_all, collect_submodules

# The spec lives in packaging/; the app lives one level up.
ROOT = os.path.dirname(SPECPATH)

datas, binaries, hiddenimports = [], [], []

# Heavy packages that ship data files / native libs PyInstaller must be told about.
for pkg in ("customtkinter", "insightface", "onnxruntime", "skimage", "scipy", "cv2"):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        pass

hiddenimports += collect_submodules("insightface")
hiddenimports += ["bcrypt", "requests", "openpyxl", "PIL.ImageTk"]

a = Analysis(
    [os.path.join(ROOT, "main.py")],
    pathex=[ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    # mediapipe is unused now; matplotlib/pytest pulled transitively but not needed.
    excludes=["mediapipe", "matplotlib", "pytest", "tkinter.test"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="BiometricAttendance",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # windowed app, no console window
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="BiometricAttendance",
)
