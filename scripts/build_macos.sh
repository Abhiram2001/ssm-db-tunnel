#!/bin/bash
# build_macos.sh — Build a self-contained macOS .app for SsmDbTunnel
#
# Prerequisites:
#   brew install python@3.11   (or any Python 3.9+)
#   brew install awscli        (runtime dep, not bundled)
#   pip install -r requirements-dev.txt
#
# Output:  dist/SsmDbTunnel.app
# Package: dist/SsmDbTunnel.dmg   (optional, prompted at the end)

set -euo pipefail

# Always run from the project root regardless of where this script is invoked
cd "$(dirname "$0")/.."

APP_NAME="SsmDbTunnel"
ENTRY="launcher.py"
DIST_DIR="dist"
BUILD_DIR="build"

echo "==> Building ${APP_NAME}.app"
echo ""

# ---- Ensure PyInstaller is installed ----------------------------------------
if ! python -c "import PyInstaller" 2>/dev/null; then
    echo "Installing PyInstaller..."
    pip install "PyInstaller>=6.0"
fi

# ---- Clean previous build artifacts -----------------------------------------
rm -rf "${BUILD_DIR}" "${DIST_DIR}/${APP_NAME}.app" "${DIST_DIR}/${APP_NAME}.dmg" \
       "${APP_NAME}.spec"

# ---- Generate icon ----------------------------------------------------------
echo "==> Generating app icon..."
python scripts/build_icon.py
echo ""

# ---- Determine icon path ----------------------------------------------------
ICON_FLAG=""
if [ -f "SsmDbTunnel.icns" ]; then
    ICON_FLAG="--icon SsmDbTunnel.icns"
fi

# ---- Run PyInstaller --------------------------------------------------------
pyinstaller \
    --windowed \
    --onedir \
    --name "${APP_NAME}" \
    --osx-bundle-identifier "com.ssmtunnel.app" \
    --add-data "templates:templates" \
    --add-data "data/hostname_port_map.json:data" \
    --collect-all "bleach" \
    --collect-all "flask" \
    --collect-all "jinja2" \
    --hidden-import "rumps" \
    --hidden-import "pymysql" \
    --hidden-import "pymysql.cursors" \
    ${ICON_FLAG} \
    "${ENTRY}"

echo ""
echo "✅  Build complete: ${DIST_DIR}/${APP_NAME}.app"
echo ""

# ---- Code-sign (self-signed, allows running on the same machine) ------------
echo "==> Self-signing the .app bundle..."
codesign --deep --force --sign - "${DIST_DIR}/${APP_NAME}.app" 2>/dev/null \
    && echo "✅  Signed (ad-hoc)" \
    || echo "⚠️   codesign skipped (not critical for local use)"

echo ""
echo "To install: drag ${DIST_DIR}/${APP_NAME}.app into /Applications/"
echo ""

# ---- Optional: create a DMG for easy sharing --------------------------------
read -r -p "Create a distributable DMG? [y/N] " answer
if [[ "${answer}" =~ ^[Yy]$ ]]; then
    echo "==> Creating DMG..."
    hdiutil create \
        -volname "${APP_NAME}" \
        -srcfolder "${DIST_DIR}/${APP_NAME}.app" \
        -ov -format UDZO \
        "${DIST_DIR}/${APP_NAME}.dmg"
    echo "✅  DMG: ${DIST_DIR}/${APP_NAME}.dmg"
fi
