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
- Rate limits and richer audit queries
- Recovery/load/integration tests
- Signed release process
- Download/release retention policy

## Phase 3 — Client packaging 🚧

### Windows connection methods

- ✅ Portable one-file EXE
- ✅ PowerShell launcher that starts the same temporary visible client
- ✅ Portable `--onedir` runtime fallback
- ✅ SHA-256 generation and verification for the Windows one-file client
- ✅ Safe allowlisted HTTPS distribution endpoints
- ✅ Owner-only distribution metadata endpoint
- ✅ Complete Windows distribution build artifact
- ✅ Telegram connection-method chooser after session creation
- ✅ Session-specific PowerShell launcher generation
- ✅ systemd deployment templates
- ✅ Caddy HTTPS/WSS reverse-proxy template
- 🚧 Deploy latest source and Windows artifacts to the VPS
- 🚧 Configure a real DNS name and HTTPS/WSS
- 🚧 End-to-end Windows test for all three methods without an SSH tunnel

All Windows launch methods keep the same Protocol v1, command allowlist, explicit consent, server-authoritative expiry, and non-persistent security boundaries. See `docs/CONNECTION_METHODS.md` and `docs/DEPLOYMENT.md`.

### Later packaging hardening

- Signed Windows release strategy
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
