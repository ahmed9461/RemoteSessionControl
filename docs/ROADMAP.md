# Roadmap

## Phase 0 — Foundation ✅

- Repository structure
- Core session model
- Pairing/reconnect
- SQLite schema
- Protocol v1
- Security baseline
- Audit and media TTL
- Tests and CI

## Phase 1 — MVP integration ✅ / hardening ongoing

- FastAPI server
- Telegram adapter
- Windows/macOS Python client
- Device info
- Screenshot
- 30-second screen recording from Telegram
- Session status
- Disconnect

## Phase 2 — Production hardening

- Alembic migrations
- PostgreSQL option
- Structured logging and metrics
- Reverse-proxy deployment templates
- Rate limits and richer audit queries
- Recovery/load/integration tests
- Signed release process

## Phase 3 — Client packaging

- Signed Windows installer strategy
- Notarized macOS app strategy
- Native visible session-status UI
- Capture-permission diagnostics

## Phase 4 — WhatsApp adapter

- Channel identity binding
- Same canonical commands
- Result return to origin channel
- No session/core redesign

## Phase 5 — Optional interfaces

- Web dashboard
- Mobile web/app
- REST clients
- Natural-language command parser that maps only to canonical allowlisted commands
