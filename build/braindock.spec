# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for BrainDock

This creates standalone executables for macOS and Windows.
Run with: pyinstaller build/braindock.spec

For macOS: Creates BrainDock.app bundle
For Windows: Creates BrainDock.exe
"""

import sys
import os
from pathlib import Path

# Get the project root directory
SPEC_DIR = Path(SPECPATH)
PROJECT_ROOT = SPEC_DIR.parent

# Platform detection
IS_MACOS = sys.platform == 'darwin'
IS_WINDOWS = sys.platform == 'win32'

# Icon paths
ICON_ICNS = str(SPEC_DIR / 'icon.icns')
ICON_ICO = str(SPEC_DIR / 'icon.ico')

# Choose icon based on platform
if IS_MACOS:
    ICON = ICON_ICNS if os.path.exists(ICON_ICNS) else None
else:
    ICON = ICON_ICO if os.path.exists(ICON_ICO) else None

# Data files to include
# Format: (source_path, destination_folder)
datas = [
    # Data files
    (str(PROJECT_ROOT / 'data' / 'focus_statements.json'), 'data'),
    (str(PROJECT_ROOT / 'data' / 'braindock_alert_sound.mp3'), 'data'),
    (str(PROJECT_ROOT / 'data' / 'license_keys.json'), 'data'),
    # Assets
    (str(PROJECT_ROOT / 'assets'), 'assets'),
    # Legal documents
    (str(PROJECT_ROOT / 'legal'), 'legal'),
]

# Note: SSL certificates are handled automatically by PyInstaller's certifi hook
# (hook-certifi.py from pyinstaller-hooks-contrib)

# Hidden imports - modules that PyInstaller might miss
hiddenimports = [
    # Bundled API keys module (generated at build time)
    'bundled_keys',
    
    # OpenAI and HTTP clients
    'openai',
    'openai.resources',
    'openai._streaming',
    'httpx',
    'httpcore',
    'h11',
    'anyio',
    'sniffio',
    'certifi',
    'httpx._transports',
    'httpx._transports.default',
    
    # Google Generative AI
    'google.generativeai',
    'google.ai.generativelanguage',
    'google.api_core',
    'google.auth',
    'google.protobuf',
    'proto',
    
    # Image processing
    'PIL',
    'PIL.Image',
    'PIL.ImageTk',
    'cv2',
    'numpy',
    
    # PDF generation
    'reportlab',
    'reportlab.lib',
    'reportlab.lib.colors',
    'reportlab.lib.pagesizes',
    'reportlab.lib.styles',
    'reportlab.lib.units',
    'reportlab.platypus',
    'reportlab.graphics',
    
    # Stripe
    'stripe',
    
    # Environment
    'dotenv',
    
    # Standard library that might be missed
    'json',
    'logging',
    'threading',
    'queue',
    'tkinter',
    'tkinter.messagebox',
    'tkinter.filedialog',
    'tkinter.font',
]

# Platform-specific hidden imports
if IS_MACOS:
    hiddenimports.extend([
        'AppKit',
        'Foundation',
        'objc',
        'PyObjCTools',
    ])

# Exclude unnecessary modules to reduce size
excludes = [
    'matplotlib',
    'scipy',
    'pandas',
    'notebook',
    'jupyter',
    'IPython',
    'test',
    'tests',
    'unittest',
    'pytest',
]

# No runtime hooks needed - API keys are embedded via bundled_keys.py module
runtime_hooks = []

# Analysis step
a = Analysis(
    [str(PROJECT_ROOT / 'main.py')],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=runtime_hooks,
    excludes=excludes,
    noarchive=False,
)

# Remove duplicate data files
pyz = PYZ(a.pure)

# Create the executable
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='BrainDock',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # No console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON,
)

# Collect all files
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='BrainDock',
)

# macOS-specific: Create app bundle
if IS_MACOS:
    app = BUNDLE(
        coll,
        name='BrainDock.app',
        icon=ICON_ICNS if os.path.exists(ICON_ICNS) else None,
        bundle_identifier='com.braindock.app',
        info_plist={
            'CFBundleName': 'BrainDock',
            'CFBundleDisplayName': 'BrainDock',
            'CFBundleVersion': '1.0.0',
            'CFBundleShortVersionString': '1.0.0',
            'CFBundleExecutable': 'BrainDock',
            'CFBundleIdentifier': 'com.braindock.app',
            'CFBundlePackageType': 'APPL',
            'CFBundleSignature': '????',
            'LSMinimumSystemVersion': '10.13.0',
            'NSHighResolutionCapable': True,
            'NSCameraUsageDescription': 'BrainDock needs camera access to monitor your focus and detect distractions.',
            'NSMicrophoneUsageDescription': 'BrainDock may use the microphone for future features.',
            'LSApplicationCategoryType': 'public.app-category.productivity',
        },
    )
