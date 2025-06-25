#!/bin/bash

set -e  # Stop on first error


APP_NAME="Anonymizer"
APP_ENTRY="src/anonymizer/anonymizer.py"
WIN_PYTHON="C:\users\fhartmann\AppData\Local\Programs\Python\Python312\python.exe"
PYINSTALLER="C:\users\fhartmann\AppData\Local\Programs\Python\Python312\\Scripts\\pyinstaller.exe"
INNO="C:\\\\Program Files (x86)\\\\Inno Setup 6\\\\ISCC.exe"

echo "[+] Cleaning previous builds..."
rm -rf build dist dist_installer *.spec

echo "[+] Building .whl with Poetry..."
poetry build -f wheel

echo "[+] Installing package in Wine's Python..."
WHEEL=$(ls dist/*.whl | head -n 1)
wine "$WIN_PYTHON" -m pip install --upgrade pip
wine "$WIN_PYTHON" -m pip install "$WHEEL" #--force-reinstall
wine "$WIN_PYTHON" -m pip install pyinstaller

echo "[+] Running PyInstaller inside Wine..."
wine "$PYINSTALLER" \
  --noconfirm \
  --onedir \
  --windowed \
  --icon="src/anonymizer/assets/icons/rsna_icon.ico" \
  --add-data="src/anonymizer/assets;assets" \
  --collect-all=xnat \
  --collect-all=scipy \
  --hidden-import=scipy \
  --hidden-import=scipy._cyutility \
  --hidden-import=easyocr \
  --hidden-import=PIL._tkinter_finder \
  --name="$APP_NAME" \
  --clean \
  "$APP_ENTRY"

echo "[+] Creating installer with Inno Setup..."
wine "$INNO" src/anonymizer.iss
echo "[✓] Installer created at dist_installer/${APP_NAME}_Installer.exe"
