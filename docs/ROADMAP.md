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
- Optional signed release process
- Download/release retention policy

## Phase 3 — Client packaging 🚧

### Windows connection methods

- ✅ Portable one-file EXE
- ✅ One-click BAT launcher that downloads/verifies/runs the client without PowerShell
- ✅ One-click CMD compatibility launcher that applies PowerShell `ExecutionPolicy Bypass` only to its child process
- ✅ PowerShell launcher that starts the same temporary visible client
- ✅ Portable `--onedir` runtime fallback
- ✅ SHA-256 generation and verification for downloaded Windows components
- ✅ Safe allowlisted HTTPS distribution endpoints
- ✅ Owner-only distribution metadata endpoint
- ✅ Public allowlisted build manifest for lazy verified client components
- ✅ Complete Windows distribution build artifact
- ✅ Telegram connection-method chooser after session creation
- ✅ Session-specific BAT/CMD/PowerShell launcher generation
- ✅ systemd deployment templates
- ✅ Caddy HTTPS/WSS reverse-proxy template
- ✅ Secure HTTPS ingress currently validated through Tailscale Funnel
- ✅ Remove NumPy, ImageIO, and Pillow from the Windows core capture path
- ✅ Split FFmpeg into a separately verified lazy screen-recording helper for Windows builds
- ✅ Guard mutable development releases against stale workflow runs
- 🚧 Deploy the latest source and rebuilt lightweight Windows artifacts to the VPS
- 🚧 Measure the rebuilt EXE size against the previous ~63 MB development build
- 🚧 End-to-end Windows test for BAT, CMD, EXE, PowerShell, Portable, screenshot, and video without an SSH tunnel

All Windows launch methods keep the same Protocol v1, command allowlist, explicit consent, server-authoritative expiry, and non-persistent security boundaries. See `docs/CONNECTION_METHODS.md` and `docs/DEPLOYMENT.md`.

### macOS packaging

- ✅ macOS client build exists
- 🚧 Add macOS-specific Telegram distribution buttons/launcher flow
- 🚧 Add production-friendly permission diagnostics for Screen Recording
- 🚧 Evaluate a lightweight/lazy recorder component for macOS without regressing current recording behavior

### Later packaging hardening

- Optional signed Windows release strategy
- Optional notarized macOS app strategy
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
