#!/usr/bin/env bash
set -euo pipefail

# Build macOS .app bundle using PyInstaller
# Prerequisites: Python 3, pip install -r requirements.txt PyInstaller

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

APP_NAME="ResearchAssistant"
DIST_DIR="dist/macos"
BUILD_DIR="build/macos"
ICON_SRC="packaging/linux/research-assistant.svg"
APP_BUNDLE="$DIST_DIR/$APP_NAME.app"

echo "=== Building macOS .app bundle ==="

# Clean previous builds
rm -rf "$DIST_DIR" "$BUILD_DIR"
mkdir -p "$DIST_DIR"

# Build with PyInstaller (one-file, windowed)
python3 -m PyInstaller \
  --noconfirm --clean --windowed \
  --name "$APP_NAME" \
  --distpath "$DIST_DIR" \
  --workpath "$BUILD_DIR" \
  --specpath "$BUILD_DIR/spec" \
  --add-data "app/templates:app/templates" \
  --add-data "app/static:app/static" \
  --add-data "migrations:migrations" \
  --add-data "scripts/build_weekly_presentation.mjs:scripts" \
  --hidden-import app.admin \
  --hidden-import app.auth \
  --hidden-import app.commands \
  --hidden-import app.export_service \
  --hidden-import app.main \
  --hidden-import app.migration_service \
  --hidden-import app.models \
  --hidden-import app.presentation_service \
  --hidden-import app.project_package \
  --hidden-import app.update_service \
  --hidden-import app.version \
  --hidden-import app.workspace \
  --hidden-import version_info \
  --hidden-import logging.config \
  --osx-bundle-identifier com.researchassistant.app \
  linux_launcher.py

echo "=== .app bundle created at $APP_BUNDLE ==="

# Create basic Info.plist additions if needed
if [ -d "$APP_BUNDLE" ]; then
  # Ensure macOS data directory
  defaults write "$APP_BUNDLE/Contents/Info" NSHighResolutionCapable -bool YES
  echo "=== macOS .app bundle ready ==="
else
  echo "ERROR: .app bundle not created"
  exit 1
fi
