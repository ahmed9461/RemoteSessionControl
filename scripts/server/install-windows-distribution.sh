#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 || $# -gt 2 ]]; then
  echo "Usage: $0 <RemoteSessionControl-Windows-Distribution.zip> [target-dir]" >&2
  exit 2
fi

archive="$1"
target="${2:-/opt/RemoteSessionControl/data/downloads}"

if [[ ! -f "$archive" ]]; then
  echo "Archive not found: $archive" >&2
  exit 1
fi

command -v unzip >/dev/null 2>&1 || {
  echo "unzip is required" >&2
  exit 1
}
command -v sha256sum >/dev/null 2>&1 || {
  echo "sha256sum is required" >&2
  exit 1
}

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
unzip -q "$archive" -d "$tmp"

mkdir -p "$target"

copy_named() {
  local name="$1"
  local required="${2:-no}"
  local source
  source="$(find "$tmp" -type f -name "$name" -print -quit)"
  if [[ -z "$source" ]]; then
    if [[ "$required" == "yes" ]]; then
      echo "Required distribution file missing: $name" >&2
      exit 1
    fi
    return 0
  fi
  install -m 0644 "$source" "$target/$name"
}

copy_named "RemoteSessionControl-Client.exe" yes
copy_named "RemoteSessionControl-Client.exe.sha256"
copy_named "RemoteSessionControl-Windows-Portable.zip"
copy_named "Start-RemoteSession.ps1"
copy_named "manifest.json"

if [[ -f "$target/RemoteSessionControl-Client.exe.sha256" ]]; then
  (
    cd "$target"
    sha256sum -c RemoteSessionControl-Client.exe.sha256
  )
else
  echo "Warning: checksum file missing; client was copied without bundle checksum verification." >&2
fi

chmod 0755 "$target"

echo "Windows distribution installed in: $target"
echo "Published files:"
find "$target" -maxdepth 1 -type f -printf '  %f\n' | sort
