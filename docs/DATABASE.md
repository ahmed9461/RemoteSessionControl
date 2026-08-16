# Database

MVP uses SQLite; production can migrate to PostgreSQL.

## Tables

- `owners`
- `channel_identities`
- `devices`
- `sessions`
- `commands`
- `media`
- `audit_logs`

## Important invariants

- Pairing-token hashes are unique.
- Reconnect-token hashes are unique per session.
- `expires_at` is null until activation.
- A device's `current_session_id` identifies its live session.
- `ChannelIdentity(channel, external_id)` is unique.

## Migration policy

The MVP uses `create_all` while the schema is pre-release. Before production data exists, introduce Alembic and require forward/backward migration tests for every schema change.
