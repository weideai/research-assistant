#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
build_root="$project_root/build/linux-source"
dist_root="$project_root/dist/linux"
payload="$build_root/research-assistant-source.tar.gz"
output="$dist_root/ResearchAssistant-Linux-Installer.run"

rm -rf "$build_root"
mkdir -p "$build_root" "$dist_root"

tar \
  --exclude='./.git' \
  --exclude='./.venv' \
  --exclude='./.pytest_cache' \
  --exclude='./__pycache__' \
  --exclude='./instance' \
  --exclude='./build' \
  --exclude='./dist' \
  --exclude='./.env' \
  --exclude='./.env.production' \
  -czf "$payload" -C "$project_root" .

cat "$project_root/packaging/linux/source-installer-header.sh" "$payload" > "$output"
chmod 0755 "$output"
echo "Linux source installer created: $output"
sha256sum "$output"
