#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python_bin="${PYTHON:-python3}"
build_root="$project_root/build/linux"
dist_root="$project_root/dist/linux"
app_dist="$dist_root/app"
package_root="$build_root/deb/root"

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "This script must run on Linux. Use Ubuntu, WSL, Docker, or GitHub Actions." >&2
  exit 2
fi

cd "$project_root"
"$python_bin" -c "import PyInstaller" 2>/dev/null || {
  echo "PyInstaller is missing. Install requirements and PyInstaller first." >&2
  exit 3
}

rm -rf "$build_root" "$dist_root"
mkdir -p "$build_root/spec" "$app_dist"

"$python_bin" -m PyInstaller \
  --noconfirm --clean --onefile \
  --name ResearchAssistant \
  --distpath "$app_dist" \
  --workpath "$build_root/app" \
  --specpath "$build_root/spec" \
  --add-data "$project_root/app/templates:app/templates" \
  --add-data "$project_root/app/static:app/static" \
  --add-data "$project_root/migrations:migrations" \
  --add-data "$project_root/scripts/build_weekly_presentation.mjs:scripts" \
  --hidden-import app.admin \
  --hidden-import app.auth \
  --hidden-import app.commands \
  --hidden-import app.main \
  --hidden-import app.models \
  --hidden-import app.presentation_service \
  --hidden-import logging.config \
  "$project_root/linux_launcher.py"

mkdir -p \
  "$package_root/DEBIAN" \
  "$package_root/opt/research-assistant" \
  "$package_root/usr/bin" \
  "$package_root/usr/share/applications" \
  "$package_root/usr/share/icons/hicolor/scalable/apps"

install -m 0755 "$app_dist/ResearchAssistant" "$package_root/opt/research-assistant/ResearchAssistant"
install -m 0644 "$project_root/packaging/linux/control" "$package_root/DEBIAN/control"
install -m 0644 "$project_root/packaging/linux/research-assistant.desktop" "$package_root/usr/share/applications/research-assistant.desktop"
install -m 0644 "$project_root/packaging/linux/research-assistant.svg" "$package_root/usr/share/icons/hicolor/scalable/apps/research-assistant.svg"
ln -s /opt/research-assistant/ResearchAssistant "$package_root/usr/bin/research-assistant"

if command -v dpkg-deb >/dev/null 2>&1; then
  dpkg-deb --root-owner-group --build "$package_root" "$dist_root/research-assistant_1.0.0_amd64.deb"
else
  echo "dpkg-deb is unavailable; skipping .deb output." >&2
fi

tar -C "$app_dist" -czf "$dist_root/research-assistant_1.0.0_linux_amd64.tar.gz" ResearchAssistant
echo "Linux packages created in $dist_root"
find "$dist_root" -maxdepth 1 -type f -printf '%f %s bytes\n'
