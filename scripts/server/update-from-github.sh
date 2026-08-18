#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="${RSC_APP_DIR:-/opt/RemoteSessionControl}"
REPO_URL="${RSC_REPO_URL:-https://github.com/ahmed9461/RemoteSessionControl.git}"
BRANCH="${RSC_BRANCH:-main}"
SERVER_SERVICE="${RSC_SERVER_SERVICE:-rsc-server}"
TELEGRAM_SERVICE="${RSC_TELEGRAM_SERVICE:-rsc-telegram}"
HEALTH_URL="${RSC_HEALTH_URL:-http://127.0.0.1:8000/health}"

require_command() {
    command -v "$1" >/dev/null 2>&1 || {
        echo "Missing required command: $1" >&2
        exit 1
    }
}

require_command git
require_command rsync
require_command curl
require_command systemctl

if [[ ! -d "$APP_DIR" ]]; then
    echo "Application directory not found: $APP_DIR" >&2
    exit 1
fi
if [[ ! -x "$APP_DIR/.venv/bin/python" ]]; then
    echo "Existing virtual environment not found: $APP_DIR/.venv" >&2
    exit 1
fi
if [[ ! -f "$APP_DIR/.env" ]]; then
    echo "Existing .env not found: $APP_DIR/.env" >&2
    exit 1
fi

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_DIR="$APP_DIR/data/backups/update-$STAMP"
STAGE_DIR="$(mktemp -d /tmp/rsc-update.XXXXXX)"
mkdir -p "$BACKUP_DIR/source"

cleanup() {
    rm -rf "$STAGE_DIR"
}
trap cleanup EXIT

rollback() {
    echo "Update health check failed; restoring previous application source..." >&2
    rsync -a --delete \
        --exclude '.env' \
        --exclude '.venv/' \
        --exclude 'data/' \
        --exclude '.git/' \
        "$BACKUP_DIR/source/" "$APP_DIR/"
    systemctl restart "$SERVER_SERVICE" "$TELEGRAM_SERVICE" || true
    echo "Rollback completed. Backup: $BACKUP_DIR" >&2
}

echo "[1/7] Cloning $BRANCH from $REPO_URL"
git clone --depth 1 --branch "$BRANCH" "$REPO_URL" "$STAGE_DIR/source"

echo "[2/7] Backing up current source and local state"
rsync -a \
    --exclude '.env' \
    --exclude '.venv/' \
    --exclude 'data/' \
    --exclude '.git/' \
    "$APP_DIR/" "$BACKUP_DIR/source/"
cp -a "$APP_DIR/.env" "$BACKUP_DIR/.env"
if [[ -f "$APP_DIR/data/app.db" ]]; then
    cp -a "$APP_DIR/data/app.db" "$BACKUP_DIR/app.db"
fi

chmod 700 "$BACKUP_DIR"
chmod 600 "$BACKUP_DIR/.env"

PYTHON="$APP_DIR/.venv/bin/python"
PIP="$APP_DIR/.venv/bin/pip"

echo "[3/7] Updating Python dependencies in the existing virtual environment"
"$PIP" install -r "$STAGE_DIR/source/requirements.txt"

echo "[4/7] Validating staged source before deployment"
(
    cd "$STAGE_DIR/source"
    "$PYTHON" -m compileall -q apps core channels infrastructure protocol tests
    "$PYTHON" -m pytest -q
)

echo "[5/7] Stopping services for the short source swap"
systemctl stop "$TELEGRAM_SERVICE" "$SERVER_SERVICE"

echo "[6/7] Replacing application source while preserving .env, .venv and data"
rsync -a --delete \
    --exclude '.env' \
    --exclude '.venv/' \
    --exclude 'data/' \
    --exclude '.git/' \
    "$STAGE_DIR/source/" "$APP_DIR/"

mkdir -p "$APP_DIR/data/media" "$APP_DIR/data/downloads"

systemctl start "$SERVER_SERVICE"
sleep 1
systemctl start "$TELEGRAM_SERVICE"

for attempt in {1..20}; do
    if curl --fail --silent --show-error "$HEALTH_URL" >/dev/null; then
        echo "[7/7] Health check passed"
        echo "RemoteSessionControl updated successfully."
        echo "Backup retained at: $BACKUP_DIR"
        exit 0
    fi
    sleep 1
done

rollback
exit 1
