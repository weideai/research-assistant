#!/usr/bin/env bash
set -euo pipefail

# Create macOS DMG installer from .app bundle
# Requires: create-dmg (brew install create-dmg) or hdiutil

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

APP_NAME="ResearchAssistant"
DIST_DIR="dist/macos"
APP_BUNDLE="$DIST_DIR/$APP_NAME.app"

if [ ! -d "$APP_BUNDLE" ]; then
  echo "ERROR: .app bundle not found at $APP_BUNDLE. Run build_macos_app.sh first."
  exit 1
fi

VERSION="${1:-$(python3 -c "from app.version import APP_VERSION; print(APP_VERSION)" 2>/dev/null || echo '2.5.2')}"
DMG_NAME="${APP_NAME}-${VERSION}.dmg"
DMG_PATH="$DIST_DIR/$DMG_NAME"

echo "=== Creating macOS DMG: $DMG_NAME ==="

# Remove old DMG
rm -f "$DMG_PATH"

# Create DMG using hdiutil
hdiutil create -volname "$APP_NAME" \
  -srcfolder "$APP_BUNDLE" \
  -ov -format UDZO \
  "$DMG_PATH"

echo "=== DMG created at $DMG_PATH ==="
echo "=== For notarization, run:"
echo "  codesign --deep --force --verify --verbose --sign 'Developer ID Application' '$APP_BUNDLE'"
echo "  xcrun notarytool submit '$DMG_PATH' --apple-id 'your@email.com' --team-id 'TEAMID' --wait"
