#!/usr/bin/env bash
set -euo pipefail

installer="${1:-dist/linux/ResearchAssistant-Linux-Installer.run}"
marker_line="$(grep -an '^__ARCHIVE_BELOW__$' "$installer" | cut -d: -f1)"
if [[ -z "$marker_line" ]]; then
  echo "Archive marker is missing." >&2
  exit 2
fi

archive_line=$((marker_line + 1))
entries="$(tail -n +"$archive_line" "$installer" | tar -tzf -)"
printf '%s\n' "$entries" | head -40

if printf '%s\n' "$entries" | grep -Eq '(^|/)instance/|(^|/)[.]env$|(^|/)credential_key$|(^|/)secret_key$'; then
  echo "Private local data was found in the installer." >&2
  exit 3
fi

for required in './linux_launcher.py' './requirements.txt' './app/templates/base.html'; do
  if ! printf '%s\n' "$entries" | grep -Fqx "$required"; then
    echo "Required payload entry is missing: $required" >&2
    exit 4
  fi
done

echo "Linux installer payload verified; private local data is not included."
