# Security Model

## Principles

- Explicit local consent before activation.
- Server is the sole authority for session validity and expiry.
- Pairing codes are one-time and short-lived.
- Reconnect tokens are session-bound and stored only as keyed hashes on the server.
- Media is temporary by default.
- Telegram is owner-allowlisted.
- Commands are allowlisted; there is no arbitrary shell command.
- No hidden persistence, stealth mode, credential collection, or security-tool bypass.

## Secrets

Never commit `.env`, bot tokens, API keys, pairing codes, or reconnect tokens. `RSC_OWNER_API_KEY` must be long and random.

## TLS

Production deployments must use HTTPS/WSS. Do not send pairing or reconnect credentials over plaintext Internet connections.

## Pairing

Pairing-code TTL and session duration are independent. A pairing code that expires before activation does not consume session duration. A used pairing code cannot be reused.

## Reconnect

Reconnect is allowed only while the original session remains active. Reconnect does not modify `activated_at` or `expires_at`.

## Media

Uploads are limited to 100 MiB and are deleted after the configured TTL (10 minutes by default). Future production storage should use private object storage with short-lived signed URLs.

## Threats intentionally out of scope for MVP

- Multi-tenant adversarial hosting.
- Hardware-backed device attestation.
- Enterprise PKI.
- End-to-end media encryption independent of TLS.

These can be added without changing the fundamental session model.
