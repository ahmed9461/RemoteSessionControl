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
command -v python3 >/dev/null 2>&1 || {
  echo "python3 is required" >&2
  exit 1
}

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
unzip -q "$archive" -d "$tmp"

find_required() {
  local name="$1"
  local source
  source="$(find "$tmp" -type f -name "$name" -print -quit)"
  if [[ -z "$source" ]]; then
    echo "Required distribution file missing: $name" >&2
    exit 1
  fi
  printf '%s' "$source"
}

manifest="$(find_required manifest.json)"
client="$(find_required RemoteSessionControl-Client.exe)"
helper="$(find_required RemoteSessionControl-FFmpeg.exe)"
portable="$(find_required RemoteSessionControl-Windows-Portable.zip)"
launcher="$(find_required Start-RemoteSession.ps1)"
checksum="$(find_required RemoteSessionControl-Client.exe.sha256)"

python3 - "$manifest" "$client" "$helper" "$portable" "$launcher" "$checksum" <<'PY'
from __future__ import annotations

import hashlib
import json
import pathlib
import sys

manifest_path, client, helper, portable, launcher, checksum = map(pathlib.Path, sys.argv[1:])
manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
files = manifest.get("files") or {}
paths = {
    "RemoteSessionControl-Client.exe": client,
    "RemoteSessionControl-FFmpeg.exe": helper,
    "RemoteSessionControl-Windows-Portable.zip": portable,
    "Start-RemoteSession.ps1": launcher,
}
for name, path in paths.items():
    expected = str((files.get(name) or {}).get("sha256") or "").lower()
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if len(expected) != 64 or expected != actual:
        raise SystemExit(f"SHA-256 verification failed for {name}")
    print(f"SHA-256 verified: {name}")

line = checksum.read_text(encoding="ascii").strip()
if not line or line.split()[0].lower() != str(files["RemoteSessionControl-Client.exe"]["sha256"]).lower():
    raise SystemExit("EXE checksum file does not match manifest.json")
PY

mkdir -p "$target"
install -m 0644 "$client" "$target/RemoteSessionControl-Client.exe"
install -m 0644 "$helper" "$target/RemoteSessionControl-FFmpeg.exe"
install -m 0644 "$portable" "$target/RemoteSessionControl-Windows-Portable.zip"
install -m 0644 "$launcher" "$target/Start-RemoteSession.ps1"
install -m 0644 "$checksum" "$target/RemoteSessionControl-Client.exe.sha256"
install -m 0644 "$manifest" "$target/manifest.json"
chmod 0755 "$target"

echo "Windows distribution installed in: $target"
echo "Published files:"
find "$target" -maxdepth 1 -type f -printf '  %f\n' | sort
