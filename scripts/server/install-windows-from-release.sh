#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="${RSC_APP_DIR:-/opt/RemoteSessionControl}"
REPO="${RSC_GITHUB_REPO:-ahmed9461/RemoteSessionControl}"
TAG="${RSC_CLIENT_RELEASE_TAG:-client-dev}"
DOWNLOADS_DIR="$APP_DIR/data/downloads"
BASE_URL="https://github.com/$REPO/releases/download/$TAG"

require_command() {
    command -v "$1" >/dev/null 2>&1 || {
        echo "Missing required command: $1" >&2
        exit 1
    }
}

require_command curl
require_command python3

mkdir -p "$DOWNLOADS_DIR"
STAGE_DIR="$(mktemp -d /tmp/rsc-windows-release.XXXXXX)"
trap 'rm -rf "$STAGE_DIR"' EXIT

FILES=(
    RemoteSessionControl-Client.exe
    RemoteSessionControl-Client.exe.sha256
    RemoteSessionControl-FFmpeg.exe
    RemoteSessionControl-Windows-Portable.zip
    Start-RemoteSession.ps1
    manifest.json
)

echo "Downloading Windows development distribution from GitHub release '$TAG'..."
for file in "${FILES[@]}"; do
    echo "  - $file"
    curl --fail --location \
        --retry 30 --retry-delay 5 --retry-all-errors \
        --connect-timeout 15 \
        "$BASE_URL/$file" \
        --output "$STAGE_DIR/$file"
done

python3 - "$STAGE_DIR" <<'PY'
from __future__ import annotations

import hashlib
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8-sig"))
files = manifest.get("files") or {}
expected_names = [
    "RemoteSessionControl-Client.exe",
    "RemoteSessionControl-FFmpeg.exe",
    "RemoteSessionControl-Windows-Portable.zip",
    "Start-RemoteSession.ps1",
]

for name in expected_names:
    expected = str((files.get(name) or {}).get("sha256") or "").lower()
    if len(expected) != 64:
        raise SystemExit(f"manifest is missing a valid SHA-256 for {name}")
    digest = hashlib.sha256((root / name).read_bytes()).hexdigest()
    if digest != expected:
        raise SystemExit(f"SHA-256 mismatch for {name}: expected {expected}, got {digest}")
    print(f"SHA-256 verified: {name}")

checksum_line = (root / "RemoteSessionControl-Client.exe.sha256").read_text(encoding="ascii").strip()
checksum_hash = checksum_line.split()[0].lower() if checksum_line else ""
manifest_hash = str(files["RemoteSessionControl-Client.exe"]["sha256"]).lower()
if checksum_hash != manifest_hash:
    raise SystemExit("EXE checksum file does not match manifest.json")

print(f"Source SHA: {manifest.get('source_sha', 'unknown')}")
print(f"Version: {manifest.get('version', 'unknown')}")
PY

install -m 0644 "$STAGE_DIR/RemoteSessionControl-Client.exe" "$DOWNLOADS_DIR/RemoteSessionControl-Client.exe"
install -m 0644 "$STAGE_DIR/RemoteSessionControl-FFmpeg.exe" "$DOWNLOADS_DIR/RemoteSessionControl-FFmpeg.exe"
install -m 0644 "$STAGE_DIR/RemoteSessionControl-Windows-Portable.zip" "$DOWNLOADS_DIR/RemoteSessionControl-Windows-Portable.zip"
install -m 0644 "$STAGE_DIR/Start-RemoteSession.ps1" "$DOWNLOADS_DIR/Start-RemoteSession.ps1"
install -m 0644 "$STAGE_DIR/RemoteSessionControl-Client.exe.sha256" "$DOWNLOADS_DIR/RemoteSessionControl-Client.exe.sha256"
install -m 0644 "$STAGE_DIR/manifest.json" "$DOWNLOADS_DIR/manifest.json"

printf '\nWindows client distribution installed successfully into:\n%s\n' "$DOWNLOADS_DIR"
