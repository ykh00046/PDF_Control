# -*- mode: python ; coding: utf-8 -*-

"""
PyInstaller spec for PDF Control.

The app now launches a separate render worker process for previews, so onedir is
preferred over onefile. Re-spawning a onefile executable for every preview would
reintroduce unpack/startup overhead into the render path.

UPX is deliberately disabled (2026-07-20): compressing Qt/PySide6 DLLs is a
known source of loader crashes and antivirus false positives, and delivery is
a zip anyway (onedir 177MB -> 77MB zipped), so the size win doesn't justify
the risk for an unsigned in-house binary.
"""

block_cipher = None


a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=[
        ("app/i18n/*.json", "app/i18n"),
    ],
    hiddenimports=[
        "fitz",
        "PIL.Image",
        "PIL.JpegImagePlugin",
        "PIL.PngImagePlugin",
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
        "PySide6.QtPrintSupport",
        "app.batch_replace_dialog",
        "app.crop_dialog",
        "app.fonts",
        "app.pdf_engine",
        "app.remove_section_dialog",
        "app.render_worker",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "IPython",
        "black",
        "bcrypt",
        "certifi",
        "charset_normalizer",
        "cryptography",
        "dateutil",
        "fsspec",
        "gi",
        "jedi",
        "jinja2",
        "jsonschema",
        "jsonschema_specifications",
        "lxml",
        "matplotlib",
        "nbformat",
        "numpy",
        "pandas",
        "pandas.io.formats.style",
        "parso",
        "pyarrow",
        "psutil",
        "py",
        "pygments",
        "pytz",
        "scipy",
        "torch",
        "PyQt5",
        "PyQt5.QtCore",
        "PyQt5.QtGui",
        "PyQt5.QtWidgets",
        "PyQt6",
        "PyQt6.QtCore",
        "PyQt6.QtGui",
        "PyQt6.QtWidgets",
        "PySide2",
        "PySide2.QtCore",
        "PySide2.QtGui",
        "PySide2.QtWidgets",
        "pytest",
        "pytest-qt",
        "tests",
        "tkinter",
        "urllib3",
        "zmq",
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
    name="PDF_Control",
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

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="PDF_Control",
)
