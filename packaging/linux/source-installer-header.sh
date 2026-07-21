#!/usr/bin/env bash
set -euo pipefail

app_name="R/LAB Research Assistant"
app_root="${XDG_DATA_HOME:-$HOME/.local/share}/research-assistant"
install_dir="$app_root/source-app"
staging_dir="$app_root/source-app.installing"
previous_dir="$app_root/source-app.previous"
bin_dir="$HOME/.local/bin"
desktop_dir="${XDG_DATA_HOME:-$HOME/.local/share}/applications"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 is required. Install python3 and python3-venv first." >&2
  exit 2
fi

archive_line="$(awk '/^__ARCHIVE_BELOW__$/ {print NR + 1; exit 0;}' "$0")"
if [[ -z "$archive_line" ]]; then
  echo "Installer payload is missing." >&2
  exit 3
fi

mkdir -p "$app_root" "$bin_dir" "$desktop_dir"
rm -rf "$staging_dir" "$previous_dir"
mkdir -p "$staging_dir"
tail -n +"$archive_line" "$0" | tar -xzf - -C "$staging_dir"

python3 -m venv "$staging_dir/.venv"
"$staging_dir/.venv/bin/python" -m pip install --upgrade pip
"$staging_dir/.venv/bin/python" -m pip install -r "$staging_dir/requirements.txt"

if [[ -d "$install_dir" ]]; then
  mv "$install_dir" "$previous_dir"
fi
mv "$staging_dir" "$install_dir"
rm -rf "$previous_dir"

cat > "$bin_dir/research-assistant" <<EOF
#!/usr/bin/env bash
exec "$install_dir/.venv/bin/python" "$install_dir/linux_launcher.py" "\$@"
EOF
chmod 0755 "$bin_dir/research-assistant"

cat > "$bin_dir/research-assistant-uninstall" <<EOF
#!/usr/bin/env bash
"$bin_dir/research-assistant" --stop >/dev/null 2>&1 || true
rm -rf "$install_dir"
rm -f "$bin_dir/research-assistant" "$desktop_dir/research-assistant.desktop"
echo "Program removed. Research data was preserved in $app_root/data"
rm -f "\$0"
EOF
chmod 0755 "$bin_dir/research-assistant-uninstall"

cat > "$desktop_dir/research-assistant.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=$app_name
Comment=Medical research planning and experiment records
Exec=$bin_dir/research-assistant
Icon=$install_dir/packaging/linux/research-assistant.svg
Terminal=false
Categories=Science;Education;Office;
StartupNotify=true
EOF
chmod 0644 "$desktop_dir/research-assistant.desktop"

echo "$app_name installed successfully."
echo "Program: $install_dir"
echo "Data: $app_root/data"
echo "Command: $bin_dir/research-assistant"
"$bin_dir/research-assistant"
exit 0

__ARCHIVE_BELOW__
